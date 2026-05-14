import logging
from typing import Any

import httpx

from .config import settings
from .http_client import http_client
from .utils import format_error

logger = logging.getLogger("web-search-mcp")


def geocode_location(query: str, limit: int = 5) -> dict[str, Any]:
    """
    Convert location names/addresses to geographic coordinates using Nominatim (OpenStreetMap) API.

    Args:
        query: Location name or address to geocode
        limit: Maximum number of results to return (max 40 as per API limit)

    Returns:
        Dict containing geocoding results or error message
    """
    if not query or not query.strip():
        return format_error("Query parameter is required and cannot be empty")

    limit = max(1, min(40, limit))

    url = "https://nominatim.openstreetmap.org/search"

    params: dict[str, str | int] = {
        "q": query,
        "format": "json",
        "limit": limit,
        "addressdetails": 1,
        "extratags": 1,
        "namedetails": 1,
    }

    headers = {
        "User-Agent": settings.user_agent,
        "Accept": "application/json",
    }

    try:
        response = http_client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list):
            return format_error(
                "Unexpected response format from geocoding service",
                f"Expected list, got {type(data)}",
            )

        processed_results = []
        for item in data:
            if not isinstance(item, dict):
                continue

            processed_results.append(
                {
                    "display_name": item.get("display_name", ""),
                    "latitude": float(item.get("lat") or 0),
                    "longitude": float(item.get("lon") or 0),
                    "bounding_box": item.get("boundingbox", []),
                    "class": item.get("class", ""),
                    "type": item.get("type", ""),
                    "importance": item.get("importance", 0),
                    "address": item.get("address", {}),
                    "namedetails": item.get("namedetails", {}),
                }
            )

        return {
            "query": query,
            "total_results": len(processed_results),
            "results": processed_results,
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"Geocoding API HTTP error {e.response.status_code}: {e}")
        return format_error(f"Geocoding API returned error {e.response.status_code}", str(e))
    except httpx.RequestError as e:
        logger.error(f"Geocoding API request failed: {e}")
        return format_error("Network error occurred during geocoding request", str(e))
    except Exception as e:
        logger.error(f"Geocoding failed unexpectedly: {e}")
        return format_error("Geocoding failed", str(e))
