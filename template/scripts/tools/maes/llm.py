#!/usr/bin/env python3
"""Unified LLM provider abstraction for MAES CI scripts.

Supported providers (auto-detected from env vars):
  anthropic — ANTHROPIC_API_KEY             (default if set)
  openai    — OPENAI_API_KEY                (OpenAI / ChatGPT)
  github    — GITHUB_TOKEN                  (GitHub Models / Copilot)
  gemini    — GEMINI_API_KEY                (Google Gemini, via OpenAI-compatible endpoint)

Override with MAES_PROVIDER=anthropic|openai|github|gemini.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Iterator

PROVIDER_DEFAULTS: dict[str, dict] = {
    "anthropic": {
        "env": "ANTHROPIC_API_KEY",
        "model_default": "claude-sonnet-4-6",
        "model_analyze": "claude-sonnet-4-6",
        "base_url": None,
    },
    "openai": {
        "env": "OPENAI_API_KEY",
        "model_default": "gpt-5.5",
        "model_analyze": "gpt-5.5",
        "base_url": None,
    },
    "github": {
        "env": "GITHUB_TOKEN",
        "model_default": "gpt-4o-mini",
        "model_analyze": "gpt-4o",
        "base_url": "https://models.inference.ai.azure.com",
    },
    "gemini": {
        "env": "GEMINI_API_KEY",
        "model_default": "gemini-2.0-flash",
        "model_analyze": "gemini-2.5-pro",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
    },
}

_DETECT_ORDER = ["anthropic", "openai", "github", "gemini"]


def _debug(msg: str) -> None:
    """Print structured debug message to stderr when MAES_DEBUG env var is set."""
    if os.environ.get("MAES_DEBUG"):
        print(f"[maes:llm] {msg}", file=sys.stderr, flush=True)


def detect_provider() -> tuple[str, str]:
    """Return (provider_name, api_key). MAES_PROVIDER overrides auto-detection."""
    forced = os.environ.get("MAES_PROVIDER", "").strip().lower()
    if forced:
        if forced not in PROVIDER_DEFAULTS:
            print(
                f"✗ Unknown MAES_PROVIDER '{forced}'. "
                f"Valid: {', '.join(PROVIDER_DEFAULTS)}",
                file=sys.stderr,
            )
            sys.exit(1)
        key = os.environ.get(PROVIDER_DEFAULTS[forced]["env"], "")
        if not key:
            print(
                f"✗ MAES_PROVIDER={forced} but "
                f"{PROVIDER_DEFAULTS[forced]['env']} is not set.",
                file=sys.stderr,
            )
            sys.exit(1)
        return forced, key

    # No MAES_PROVIDER set: detect provider keys present in env.
    # If 2+ keys are configured, refuse to guess and require explicit selection
    # (avoids silent surprises when multiple secrets are exported at once).
    present = [
        p for p in _DETECT_ORDER
        if os.environ.get(PROVIDER_DEFAULTS[p]["env"], "")
    ]
    if len(present) >= 2:
        names = ", ".join(present)
        envs = ", ".join(PROVIDER_DEFAULTS[p]["env"] for p in present)
        print(
            f"✗ Multiple LLM providers detected ({names}) but MAES_PROVIDER is unset. "
            f"Set MAES_PROVIDER to one of: {names} (keys present: {envs}).",
            file=sys.stderr,
        )
        sys.exit(1)

    for provider in _DETECT_ORDER:
        key = os.environ.get(PROVIDER_DEFAULTS[provider]["env"], "")
        if key:
            return provider, key

    keys_list = ", ".join(PROVIDER_DEFAULTS[p]["env"] for p in _DETECT_ORDER)
    print(
        f"✗ No LLM provider found. Set one of: {keys_list}",
        file=sys.stderr,
    )
    sys.exit(1)


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

    def create(self, system: str, user: str, max_tokens: int) -> str:
        """Non-streaming call, returns full text."""
        _debug(
            f"provider={self._provider} model={self._model} max_tokens={max_tokens}"
            f" call=create chars_in={len(system) + len(user)}"
        )
        t0 = time.monotonic()
        result = (
            self._anthropic_create(system, user, max_tokens)
            if self._provider == "anthropic"
            else self._openai_create(system, user, max_tokens)
        )
        _debug(f"elapsed={time.monotonic() - t0:.1f}s chars_out={len(result)}")
        return result

    def stream(self, system: str, user: str, max_tokens: int) -> Iterator[str]:
        """Streaming call, yields text chunks."""
        _debug(
            f"provider={self._provider} model={self._model} max_tokens={max_tokens}"
            f" call=stream chars_in={len(system) + len(user)}"
        )
        t0 = time.monotonic()
        total = 0
        gen = (
            self._anthropic_stream(system, user, max_tokens)
            if self._provider == "anthropic"
            else self._openai_stream(system, user, max_tokens)
        )
        for chunk in gen:
            total += len(chunk)
            yield chunk
        _debug(f"elapsed={time.monotonic() - t0:.1f}s chars_out={total}")

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
        env_var = PROVIDER_DEFAULTS.get(self._provider, {}).get("env", "API key")

        if "credit balance is too low" in msg or "exceeded your current quota" in msg or "insufficient_quota" in msg:
            billing = {
                "anthropic": "console.anthropic.com → Plans & Billing",
                "openai": "platform.openai.com → Billing",
            }.get(self._provider, "your provider's billing page")
            others = [
                f"  export {PROVIDER_DEFAULTS[p]['env']}=..."
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

    def _anthropic_create(self, system: str, user: str, max_tokens: int) -> str:
        client = self._anthropic_client()
        try:
            msg = client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return msg.content[0].text
        except Exception as exc:
            self._fail(exc)

    def _anthropic_stream(self, system: str, user: str, max_tokens: int) -> Iterator[str]:
        client = self._anthropic_client()
        try:
            with client.messages.stream(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            ) as stream:
                yield from stream.text_stream
        except Exception as exc:
            self._fail(exc)

    # ── OpenAI-compatible (GitHub Models, Gemini, OpenAI) ─────────────────────

    def _openai_client(self):
        try:
            import openai
        except ImportError:
            print("✗ openai not installed. Run: pip install openai", file=sys.stderr)
            sys.exit(1)
        cfg = PROVIDER_DEFAULTS[self._provider]
        base_url = cfg["base_url"]
        return openai.OpenAI(base_url=base_url, api_key=self._api_key)

    def _openai_token_args(self, max_tokens: int) -> dict[str, int]:
        # OpenAI gpt-5.x chat-completions expects max_completion_tokens.
        if self._provider == "openai":
            return {"max_completion_tokens": max_tokens}
        return {"max_tokens": max_tokens}

    def _openai_create(self, system: str, user: str, max_tokens: int) -> str:
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
            return resp.choices[0].message.content or ""
        except Exception as exc:
            self._fail(exc)

    def _openai_stream(self, system: str, user: str, max_tokens: int) -> Iterator[str]:
        client = self._openai_client()
        try:
            stream = client.chat.completions.create(
                model=self._model,
                **self._openai_token_args(max_tokens),
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as exc:
            self._fail(exc)


def make_client(model: str | None = None, *, for_analyze: bool = False) -> LLMClient:
    """Detect provider, validate key, return ready LLMClient.

    Args:
        model: explicit model name; falls back to MAES_AGENT_MODEL env var,
               then to provider default.
        for_analyze: use the provider's larger analysis model as default.
    """
    provider, api_key = detect_provider()
    cfg = PROVIDER_DEFAULTS[provider]
    if model is None:
        env_model = os.environ.get("MAES_AGENT_MODEL", "")
        if env_model:
            model = env_model
        elif for_analyze:
            model = cfg["model_analyze"]
        else:
            model = cfg["model_default"]
    return LLMClient(provider, api_key, model)
