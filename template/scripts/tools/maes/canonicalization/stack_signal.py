"""Canonical stack signal builder — pure pass-through from agent stack.json.

Converts the agent-produced stack.json into a boolean presence map.

Design contract:
- Every key the agent wrote is preserved — no renaming, no filtering.
- Value is True when the agent listed at least one item in that category.
- Value is False when the agent provided an empty list.
- Non-list values (strings, bools, nulls) are skipped — only explicit lists count.
- No new categories are added by the framework.

Invariant (I1): absent information is not invented.
"""
from __future__ import annotations


def build_stack_signal(stack: dict) -> dict:
    """Convert agent stack dict to a boolean presence map.

    Parameters
    ----------
    stack:
        The parsed contents of stack.json as produced by the agent.
        Expected structure: ``{"category_name": ["item_a", "item_b"], ...}``.
        Only keys whose values are lists are included in the output.

    Returns
    -------
    dict
        ``{"category_name": bool, ...}`` — True when the list is non-empty.
        Preserves the exact category names the agent used.
    """
    return {
        k: bool(v)
        for k, v in stack.items()
        if isinstance(v, list)
    }
