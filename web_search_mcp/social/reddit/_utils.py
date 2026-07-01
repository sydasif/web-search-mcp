"""Shared helpers for the reddit package."""

from __future__ import annotations

import html as _html
import re


def extract_attr(tag: str, name: str) -> str:
    """Extract an attribute value from an HTML tag. Returns empty string on miss."""
    m = re.search(rf'\b{name}="([^"]*)"', tag)
    return _html.unescape(m.group(1)) if m else ""
