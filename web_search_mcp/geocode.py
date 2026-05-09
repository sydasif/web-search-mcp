import logging
from typing import Any

import httpx

from .config import settings
from .http_client import http_client

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
    # Validate inputs
    if not query or not query.strip():
        return {"error": "Query parameter is required and cannot be empty"}

    # Enforce API limit
    limit = max(1, min(40, limit))

    # Nominatim API endpoint
    url = "https://nominatim.openstreetmap.org/search"

    # Prepare parameters
    params: dict[str, str | int] = {
        "q": query,
        "format": "json",
        "limit": limit,
        "addressdetails": 1,  # Include detailed address information
        "extratags": 1,  # Include extra tags
        "namedetails": 1,  # Include name details
    }

    # Headers required by Nominatim usage policy
    headers = {
        "User-Agent": settings.user_agent,  # Required by Nominatim policy
        "Accept": "application/json",
    }

    try:
        # Use shared client
        response = http_client.get(url, params=params, headers=headers)

        # Check for HTTP errors
        response.raise_for_status()

        # Parse JSON response
        data = response.json()

        # Validate response structure
        if not isinstance(data, list):
            return {
                "error": "Unexpected response format from geocoding service",
                "details": f"Expected list, got {type(data)}",
            }

        # Process results to ensure consistent structure
        processed_results = []
        for item in data:
            if not isinstance(item, dict):
                continue

            # Extract essential fields
            processed_item = {
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

            processed_results.append(processed_item)

        return {
            "query": query,
            "total_results": len(processed_results),
            "results": processed_results,
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"Geocoding API HTTP error {e.response.status_code}: {e}")
        return {
            "error": f"Geocoding API returned error {e.response.status_code}",
            "details": str(e),
        }
    except httpx.RequestError as e:
        logger.error(f"Geocoding API request failed: {e}")
        return {"error": "Network error occurred during geocoding request", "details": str(e)}
    except ValueError as e:  # JSON decode error
        logger.error(f"Geocoding API response parsing failed: {e}")
        return {"error": "Invalid response format from geocoding service", "details": str(e)}
    except Exception as e:
        logger.error(f"Geocoding failed unexpectedly: {e}")
        return {"error": "Geocoding failed", "details": str(e)}
