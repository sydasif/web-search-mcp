"""Shared HTTP client configuration."""

from __future__ import annotations

from .client import get_json_client, http_client, validate_url

__all__ = ["get_json_client", "http_client", "validate_url"]
