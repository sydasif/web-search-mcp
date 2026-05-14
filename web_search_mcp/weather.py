import logging
import ssl
from typing import Any

import httpx

from .config import settings
from .http_client import http_client
from .utils import format_error

logger = logging.getLogger("web-search-mcp")


def make_openmeteo_request(
    client: httpx.Client, endpoint: str, params: dict
) -> dict[str, Any] | None:
    """Make request to OpenMeteo API with proper error handling."""
    url = f"{settings.weather_api_base}/{endpoint}"
    headers = {"Accept": "application/json"}

    try:
        response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except (ssl.SSLError, httpx.HTTPStatusError) as e:
        logger.error(f"Weather API error: {e}")
        return None


def _fetch_weather_data(params: dict[str, Any]) -> dict[str, Any]:
    """Execute weather API request using shared client configuration."""
    data = make_openmeteo_request(http_client, "forecast", params)

    if not data:
        return format_error(
            "Unable to fetch weather data.",
            "No response received from OpenMeteo API. Check network connectivity.",
        )

    if "current" not in data and "daily" not in data and "error" not in data:
        logger.warning(f"Weather API response missing expected keys: {list(data.keys())}")
        return format_error(
            "Weather API returned unexpected response format.",
            f"Response contained keys: {list(data.keys())}",
        )

    return data


def get_current_weather(latitude: float, longitude: float) -> dict[str, Any]:
    """Get current weather for a specific location."""
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
    """Get daily weather forecast for a location."""
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
