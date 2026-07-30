"""Shared Literal type aliases used across modules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Depth = Literal["quick", "default", "deep"]
FetchOutputFormat = Literal["csv", "html", "json", "markdown", "python", "txt", "xml", "xmltei"]
ResponseFormat = Literal["json", "markdown"]
SearchType = Literal["text", "news"]


@dataclass(frozen=True)
class FetchPageParams:
    """Parameters for fetch_page operation."""

    output_format: FetchOutputFormat = "txt"
    include_metadata: bool = False
    include_tables: bool = False
    deduplicate: bool = True
    max_length: int = 15000
    timeout: int = 30
