"""Shared helpers for the reddit package."""

from __future__ import annotations

import html as _html
import re
from typing import Any


def extract_attr(tag: str, name: str) -> str:
    """Extract an attribute value from an HTML tag. Returns empty string on miss."""
    m = re.search(rf'\b{name}="([^"]*)"', tag)
    return _html.unescape(m.group(1)) if m else ""


def dedupe_by(items: list[dict[str, Any]], key: str = "url") -> list[dict[str, Any]]:
    """Return items with duplicates by *key* removed (first occurrence wins)."""
    seen: set[Any] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        value = item.get(key, "")
        if value and value not in seen:
            seen.add(value)
            out.append(item)
    return out


def assign_ids(items: list[dict[str, Any]], prefix: str) -> None:
    """In-place assign sequential ids ``{prefix}{i+1}`` to each item."""
    for i, item in enumerate(items):
        item["id"] = f"{prefix}{i + 1}"
