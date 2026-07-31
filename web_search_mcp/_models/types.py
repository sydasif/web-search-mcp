"""Shared Literal type aliases used across modules."""
from __future__ import annotations

from typing import Literal

Depth = Literal["quick", "default", "deep"]
FetchOutputFormat = Literal["csv", "html", "json", "markdown", "python", "txt", "xml", "xmltei"]
ResponseFormat = Literal["json", "markdown"]
SearchType = Literal["text", "news"]

