import logging
import ssl
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger("web-search-mcp")


# SSL context for secure connections
def _get_ssl_context():
    """Get SSL context, with safe fallback for development environments."""
    try:
        return ssl.create_default_context()
    except Exception as e:
        logger.warning(f"Failed to create default SSL context: {e}")
        # In production, SSL verification should always be enforced.
        # For development/corporate environments with certificate issues,
        # better to let the user configure environment variables or settings
        # rather than silently disabling verification.
        # We'll let httpx use its own default behavior by returning None
        # which will be handled specially later
        return None


SSL_CONTEXT = _get_ssl_context()


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
    headers = {"User-Agent": settings.user_agent, "Accept": "application/json"}

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
    # Handle SSL context - if SSL_CONTEXT is None, use httpx default behavior
    if SSL_CONTEXT is None:
        client = httpx.Client(timeout=30.0)
    else:
        client = httpx.Client(verify=SSL_CONTEXT, timeout=30.0)

    with client:
        data = make_openmeteo_request(client, "forecast", params)

        if not data:
            return {
                "error": "Unable to fetch weather data.",
                "details": "No response received from OpenMeteo API. Check network connectivity."
            }

        # Validate expected top-level keys exist in the response
        # Current weather requests expect 'current', forecasts expect 'daily'
        # Allow API-level errors to pass through
        if "current" not in data and "daily" not in data and "error" not in data:
            logger.warning(f"Weather API response missing expected keys: {list(data.keys())}")
            return {
                "error": "Weather API returned unexpected response format.",
                "details": f"Response contained keys: {list(data.keys())}"
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
