"""Centralized configuration and constants for web-search-mcp."""

from .limits import DEPTH_LIMITS, ENRICH_LIMITS, FEED_TIMEOUT
from .settings import settings

__all__ = ["DEPTH_LIMITS", "ENRICH_LIMITS", "FEED_TIMEOUT", "settings"]
