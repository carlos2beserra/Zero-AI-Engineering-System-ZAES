"""Tests for StackContext normalization (C2: stable schema from LLM output)."""

from maes.compiler import _normalize_stack
from maes.models import StackContext


def test_normalize_flat_lists():
    raw = {
        "languages": ["Python", "TypeScript"],
        "frameworks": ["FastAPI", "Next.js"],
        "runtimes": ["Node.js"],
        "package_managers": ["pip", "npm"],
    }
    s = _normalize_stack(raw)
    assert s.languages == ("Python", "TypeScript")
    assert s.frameworks == ("FastAPI", "Next.js")
    assert s.runtimes == ("Node.js",)
    assert s.package_managers == ("npm", "pip")


def test_normalize_nested_backend_frontend():
    raw = {
        "backend": {"language": "Python", "framework": "FastAPI"},
        "frontend": {"language": "TypeScript", "framework": "Next.js"},
    }
    s = _normalize_stack(raw)
    assert s.languages == ("Python", "TypeScript")
    assert s.frameworks == ("FastAPI", "Next.js")


def test_normalize_primary_language_singular():
    raw = {
        "primary_language": "Python",
        "framework": "Django",
        "runtime": "CPython",
    }
    s = _normalize_stack(raw)
    assert s.languages == ("Python",)
    assert s.frameworks == ("Django",)
    assert s.runtimes == ("CPython",)


def test_normalize_empty_and_invalid():
    assert _normalize_stack({}).is_empty()
    assert _normalize_stack(None).is_empty()
    assert _normalize_stack("garbage").is_empty()
    assert _normalize_stack([]).is_empty()


def test_normalize_dedup_and_sort():
    raw = {
        "languages": ["Python", "python", "Python"],
        "backend": {"language": "Python"},
    }
    s = _normalize_stack(raw)
    # Case-sensitive dedup; sorted
    assert s.languages == ("Python", "python")


def test_normalize_drops_empty_strings():
    raw = {"languages": ["", "  ", "Python"]}
    s = _normalize_stack(raw)
    assert s.languages == ("Python",)


def test_normalize_ignores_unknown_keys():
    raw = {
        "languages": ["Go"],
        "unknown_field": "ignored",
        "weirdo": {"x": "y"},
    }
    s = _normalize_stack(raw)
    assert s.languages == ("Go",)
    assert s.frameworks == ()


def test_stack_context_is_empty():
    assert StackContext().is_empty()
    assert not StackContext(languages=("Go",)).is_empty()
