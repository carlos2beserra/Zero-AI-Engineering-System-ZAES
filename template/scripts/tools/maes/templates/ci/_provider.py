#!/usr/bin/env python3
"""Standalone LLM provider abstraction for MAES CI scripts.

Drop-in for scripts that cannot import the `maes` package.
Supports gateway (LiteLLM/OpenAI-compatible proxy), Anthropic, OpenAI, GitHub Models, and Gemini.

Provider auto-detected from env vars; MAES_PROVIDER overrides:
  gateway   — MAES_BASE_URL + MAES_API_KEY  (OpenAI-compatible proxy; checked first)
  anthropic — ANTHROPIC_API_KEY             (checked first among direct providers)
  openai    — OPENAI_API_KEY                (OpenAI / ChatGPT)
  github    — GITHUB_TOKEN                  (GitHub Models / Copilot)
  gemini    — GEMINI_API_KEY                (Google Gemini, via OpenAI-compatible endpoint)

Gateway mode (LiteLLM, Portkey, OpenRouter, etc.):
  Set MAES_BASE_URL to your proxy URL and MAES_API_KEY to your virtual key.
  The model name is passed through as-is; use MAES_SUGGEST_MODEL to control it.

Usage in CI scripts:
    import sys, os
    sys.path.insert(0, str(Path(__file__).parent))
    from _provider import make_client, has_any_provider

    if not has_any_provider():
        print("No LLM provider configured — skipping", file=sys.stderr)
        sys.exit(0)

    client = make_client(model_env="MAES_SUGGEST_MODEL")
    resp = client.create(system_prompt, user_content, max_tokens=2048)
    text = resp.text
"""

from __future__ import annotations

import os
import sys

_PROVIDERS: dict[str, dict] = {
    "gateway": {
        "env": "MAES_API_KEY",
        "base_url": None,  # read from MAES_BASE_URL at runtime
        "model_default": "claude-sonnet-4-6",
    },
    "anthropic": {
        "env": "ANTHROPIC_API_KEY",
        "base_url": None,
        "model_default": "claude-haiku-4-5-20251001",
    },
    "openai": {
        "env": "OPENAI_API_KEY",
        "base_url": None,
        "model_default": "gpt-5.5",
    },
    "github": {
        "env": "GITHUB_TOKEN",
        "base_url": "https://models.inference.ai.azure.com",
        "model_default": "gpt-4o-mini",
    },
    "gemini": {
        "env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model_default": "gemini-2.0-flash",
    },
}

_DETECT_ORDER = ["anthropic", "openai", "github", "gemini"]


class LLMResponse:
    """Normalized response from any provider."""

    def __init__(
        self,
        text: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read: int = 0,
        cache_creation: int = 0,
        provider: str = "",
    ) -> None:
        self.text = text
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_read_input_tokens = cache_read
        self.cache_creation_input_tokens = cache_creation
        self.provider = provider


class LLMClient:
    def __init__(self, provider: str, api_key: str, model: str) -> None:
        self._provider = provider
        self._api_key = api_key
        self._model = model

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    def create(self, system: str, user: str, max_tokens: int) -> LLMResponse:
        """Non-streaming call — returns normalized response."""
        if self._provider == "anthropic":
            return self._anthropic_create(system, user, max_tokens)
        return self._openai_create(system, user, max_tokens)

    def create_cached(
        self, system: str, stable: str, volatile: str, max_tokens: int
    ) -> LLMResponse:
        """Call with Anthropic cache_control on system+stable parts.

        For non-Anthropic providers, falls back to plain create() by
        concatenating stable and volatile content.
        """
        if self._provider == "anthropic":
            return self._anthropic_cached(system, stable, volatile, max_tokens)
        return self.create(system, stable + "\n\n" + volatile, max_tokens)

    # ── Anthropic ─────────────────────────────────────────────────────────────

    def _anthropic_client(self):
        try:
            import anthropic
        except ImportError:
            print("✗ anthropic not installed. Run: pip install anthropic", file=sys.stderr)
            sys.exit(1)
        return anthropic.Anthropic(api_key=self._api_key)

    def _fail(self, exc: Exception) -> None:
        msg = str(exc).lower()
        label = self._provider.capitalize()
        env_var = _PROVIDERS.get(self._provider, {}).get("env", "API key")

        if "credit balance is too low" in msg or "exceeded your current quota" in msg or "insufficient_quota" in msg:
            billing = {
                "anthropic": "console.anthropic.com → Plans & Billing",
                "openai": "platform.openai.com → Billing",
            }.get(self._provider, "your provider's billing page")
            others = [
                f"  export {_PROVIDERS[p]['env']}=..."
                for p in _DETECT_ORDER
                if p != self._provider
            ]
            print(
                f"\n✗ {label}: insufficient credits.\n"
                f"  → Add credits at {billing}\n"
                f"  → Or switch to another provider:\n" + "\n".join(others),
                file=sys.stderr,
            )
        elif "authentication" in msg or "invalid_api_key" in msg or "invalid x-api-key" in msg:
            print(
                f"\n✗ {label}: authentication failed.\n"
                f"  → Check that {env_var} is set correctly.",
                file=sys.stderr,
            )
        elif "rate limit" in msg or "rate_limit" in msg:
            print(
                f"\n✗ {label}: rate limit reached.\n"
                f"  → Wait a moment and retry, or set MAES_PROVIDER to use a different provider.",
                file=sys.stderr,
            )
        else:
            print(f"\n✗ {label} API error: {exc}", file=sys.stderr)
        sys.exit(1)

    def _anthropic_create(self, system: str, user: str, max_tokens: int) -> LLMResponse:
        client = self._anthropic_client()
        try:
            msg = client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            u = msg.usage
            return LLMResponse(
                text=msg.content[0].text,
                input_tokens=u.input_tokens,
                output_tokens=u.output_tokens,
                cache_read=getattr(u, "cache_read_input_tokens", 0),
                cache_creation=getattr(u, "cache_creation_input_tokens", 0),
                provider="anthropic",
            )
        except Exception as exc:
            self._fail(exc)

    def _anthropic_cached(
        self, system: str, stable: str, volatile: str, max_tokens: int
    ) -> LLMResponse:
        client = self._anthropic_client()
        try:
            msg = client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": stable, "cache_control": {"type": "ephemeral"}},
                        {"type": "text", "text": volatile},
                    ],
                }],
            )
            u = msg.usage
            return LLMResponse(
                text=msg.content[0].text,
                input_tokens=u.input_tokens,
                output_tokens=u.output_tokens,
                cache_read=getattr(u, "cache_read_input_tokens", 0),
                cache_creation=getattr(u, "cache_creation_input_tokens", 0),
                provider="anthropic",
            )
        except Exception as exc:
            self._fail(exc)

    # ── OpenAI-compatible (GitHub Models, Gemini, OpenAI) ─────────────────────

    def _openai_client(self):
        try:
            import openai
        except ImportError:
            print("✗ openai not installed. Run: pip install openai", file=sys.stderr)
            sys.exit(1)
        cfg = _PROVIDERS[self._provider]
        base_url = os.environ.get("MAES_BASE_URL") if self._provider == "gateway" else cfg["base_url"]
        return openai.OpenAI(base_url=base_url, api_key=self._api_key)

    def _openai_token_args(self, max_tokens: int) -> dict[str, int]:
        # OpenAI gpt-5.x chat-completions expects max_completion_tokens.
        if self._provider == "openai":
            return {"max_completion_tokens": max_tokens}
        return {"max_tokens": max_tokens}

    def _openai_create(self, system: str, user: str, max_tokens: int) -> LLMResponse:
        client = self._openai_client()
        try:
            resp = client.chat.completions.create(
                model=self._model,
                **self._openai_token_args(max_tokens),
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            u = resp.usage
            return LLMResponse(
                text=resp.choices[0].message.content or "",
                input_tokens=u.prompt_tokens if u else 0,
                output_tokens=u.completion_tokens if u else 0,
                provider=self._provider,
            )
        except Exception as exc:
            self._fail(exc)


def has_any_provider() -> bool:
    """Return True if at least one provider key is configured."""
    if os.environ.get("MAES_BASE_URL", ""):
        return True
    forced = os.environ.get("MAES_PROVIDER", "").strip().lower()
    if forced:
        return bool(os.environ.get(_PROVIDERS.get(forced, {}).get("env", ""), ""))
    return any(os.environ.get(_PROVIDERS[p]["env"], "") for p in _DETECT_ORDER)


def detect_provider() -> tuple[str, str]:
    """Return (provider_name, api_key). MAES_PROVIDER overrides auto-detection."""
    forced = os.environ.get("MAES_PROVIDER", "").strip().lower()
    if forced:
        if forced == "gateway":
            if not os.environ.get("MAES_BASE_URL", ""):
                print("✗ MAES_PROVIDER=gateway but MAES_BASE_URL is not set.", file=sys.stderr)
                sys.exit(1)
            return "gateway", os.environ.get("MAES_API_KEY", "not-required")
        if forced not in _PROVIDERS:
            print(
                f"✗ Unknown MAES_PROVIDER='{forced}'. "
                f"Valid: {', '.join(_PROVIDERS)}",
                file=sys.stderr,
            )
            sys.exit(1)
        key = os.environ.get(_PROVIDERS[forced]["env"], "")
        if not key:
            print(
                f"✗ MAES_PROVIDER={forced} but "
                f"{_PROVIDERS[forced]['env']} is not set.",
                file=sys.stderr,
            )
            sys.exit(1)
        return forced, key

    if os.environ.get("MAES_BASE_URL", ""):
        return "gateway", os.environ.get("MAES_API_KEY", "not-required")

    for p in _DETECT_ORDER:
        key = os.environ.get(_PROVIDERS[p]["env"], "")
        if key:
            return p, key

    keys = ", ".join(_PROVIDERS[p]["env"] for p in _DETECT_ORDER)
    print(
        f"✗ No LLM provider found. Set one of: {keys}"
        " (or set MAES_BASE_URL for gateway mode)",
        file=sys.stderr,
    )
    sys.exit(1)


def make_client(
    model: str | None = None,
    *,
    model_env: str = "MAES_SUGGEST_MODEL",
) -> LLMClient:
    """Detect provider, return ready LLMClient.

    Args:
        model: explicit model name; overrides env var and provider default.
        model_env: env var name to read model from (default: MAES_SUGGEST_MODEL).
    """
    provider, api_key = detect_provider()
    if model is None:
        model = os.environ.get(model_env) or _PROVIDERS[provider]["model_default"]
    return LLMClient(provider, api_key, model)
