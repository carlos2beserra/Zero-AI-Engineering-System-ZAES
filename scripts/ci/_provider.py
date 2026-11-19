#!/usr/bin/env python3
"""Standalone LLM provider abstraction for MAES CI scripts.

Drop-in for scripts that cannot import the `maes` package.
Supports Anthropic, GitHub Models (Copilot), and Gemini.

Provider auto-detected from env vars; MAES_PROVIDER overrides:
  anthropic — ANTHROPIC_API_KEY  (checked first)
  github    — GITHUB_TOKEN       (GitHub Models / Copilot)
  gemini    — GEMINI_API_KEY     (Google Gemini, via OpenAI-compatible endpoint)

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
    "anthropic": {
        "env": "ANTHROPIC_API_KEY",
        "base_url": None,
        "model_default": "claude-haiku-4-5-20251001",
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

_DETECT_ORDER = ["anthropic", "github", "gemini"]


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

    def _anthropic_create(self, system: str, user: str, max_tokens: int) -> LLMResponse:
        client = self._anthropic_client()
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

    def _anthropic_cached(
        self, system: str, stable: str, volatile: str, max_tokens: int
    ) -> LLMResponse:
        client = self._anthropic_client()
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

    # ── OpenAI-compatible (GitHub Models, Gemini) ─────────────────────────────

    def _openai_client(self):
        try:
            import openai
        except ImportError:
            print("✗ openai not installed. Run: pip install openai", file=sys.stderr)
            sys.exit(1)
        cfg = _PROVIDERS[self._provider]
        return openai.OpenAI(base_url=cfg["base_url"], api_key=self._api_key)

    def _openai_create(self, system: str, user: str, max_tokens: int) -> LLMResponse:
        client = self._openai_client()
        resp = client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
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


def has_any_provider() -> bool:
    """Return True if at least one provider key is configured."""
    forced = os.environ.get("MAES_PROVIDER", "").strip().lower()
    if forced:
        return bool(os.environ.get(_PROVIDERS.get(forced, {}).get("env", ""), ""))
    return any(os.environ.get(_PROVIDERS[p]["env"], "") for p in _DETECT_ORDER)


def detect_provider() -> tuple[str, str]:
    """Return (provider_name, api_key). MAES_PROVIDER overrides auto-detection."""
    forced = os.environ.get("MAES_PROVIDER", "").strip().lower()
    if forced:
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

    # No MAES_PROVIDER set: detect provider keys present in env.
    # If 2+ keys are configured, refuse to guess and require explicit selection
    # (avoids silent surprises when CI exports multiple secrets at once).
    present = [p for p in _DETECT_ORDER if os.environ.get(_PROVIDERS[p]["env"], "")]
    if len(present) >= 2:
        names = ", ".join(present)
        envs = ", ".join(_PROVIDERS[p]["env"] for p in present)
        print(
            f"✗ Multiple LLM providers detected ({names}) but MAES_PROVIDER is unset. "
            f"Set MAES_PROVIDER to one of: {names} (keys present: {envs}).",
            file=sys.stderr,
        )
        sys.exit(1)

    for p in _DETECT_ORDER:
        key = os.environ.get(_PROVIDERS[p]["env"], "")
        if key:
            return p, key

    keys = ", ".join(_PROVIDERS[p]["env"] for p in _DETECT_ORDER)
    print(f"✗ No LLM provider found. Set one of: {keys}", file=sys.stderr)
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
