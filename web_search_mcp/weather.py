import logging
import ssl
from typing import Any

import httpx

from .config import settings
from .http_client import http_client

logger = logging.getLogger("web-search-mcp")


def make_openmeteo_request(
    client: httpx.Client, endpoint: str, params: dict
) -> dict[str, Any] | None:
    """
    Make request to OpenMeteo API with proper error handling.

    Args:
        client: Shared httpx.Client instance
        endpoint: API endpoint to call
        params: Query parameters for the request

    Returns:
        JSON response as dict or None if request fails
    """
    url = f"{settings.weather_api_base}/{endpoint}"
    # Client has User-Agent; just add Accept header
    headers = {"Accept": "application/json"}

    try:
        response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except ssl.SSLError as e:
        # This is often the specific error in corporate environments
        logger.error(f"Weather API SSL error: {e}")
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"Weather API HTTP error {e.response.status_code}: {e}")
        return None
    except Exception as e:
        logger.error(f"Weather API Request failed: {e}")
        return None


def _fetch_weather_data(params: dict[str, Any]) -> dict[str, Any]:
    """
    Execute weather API request using shared client configuration.

    Args:
        params: Query parameters for the request

    Returns:
        Dict containing weather data or error message
    """
    data = make_openmeteo_request(http_client, "forecast", params)

    if not data:
        return {
            "error": "Unable to fetch weather data.",
            "details": "No response received from OpenMeteo API. Check network connectivity.",
        }

    # Validate expected top-level keys exist in the response
    # Current weather requests expect 'current', forecasts expect 'daily'
    # Allow API-level errors to pass through
    if "current" not in data and "daily" not in data and "error" not in data:
        logger.warning(f"Weather API response missing expected keys: {list(data.keys())}")
        return {
            "error": "Weather API returned unexpected response format.",
            "details": f"Response contained keys: {list(data.keys())}",
        }

    return data


def get_current_weather(latitude: float, longitude: float) -> dict[str, Any]:
    """
    Get current weather for a specific location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location

    Returns:
        Dict containing current weather data or error message
    """
    fields = [
        "temperature_2m",
        "relative_humidity_2m",
        "apparent_temperature",
        "precipitation",
        "weather_code",
        "wind_speed_10m",
    ]

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join(fields),
    }

    return _fetch_weather_data(params)


def get_forecast(
    latitude: float,
    longitude: float,
    days: int = 7,
) -> dict[str, Any]:
    """
    Get daily weather forecast for a location.

    Args:
        latitude: Latitude of the location
        longitude: Longitude of the location
        days: Number of days for forecast (1-16, default 7)

    Returns:
        Dict containing forecast data or error message
    """
    # Enforce API limits
    days = max(1, min(16, days))

    fields = [
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
        "weather_code",
        "uv_index_max",
    ]

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join(fields),
        "forecast_days": days,
        "timezone": "auto",
    }

    return _fetch_weather_data(params)
