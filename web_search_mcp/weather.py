import logging
import ssl

import httpx

from .config import settings
from .http_client import http_client
from .utils import format_error

logger = logging.getLogger("web-search-mcp")


def make_openmeteo_request(
    client: httpx.Client, endpoint: str, params: dict[str, str | int | float]
) -> dict[str, str | int | float | list | dict] | None:
    """Makes a request to the OpenMeteo API with proper error handling.

    Args:
        client: The httpx client used to make the request.
        endpoint: The API endpoint to call.
        params: A dictionary of query parameters.

    Returns:
        The JSON response from the API as a dictionary, or None if an error occurs.

    Raises:
        httpx.HTTPStatusError: If the request returns a non-2xx status code.
    """
    url = f"{settings.weather_api_base}/{endpoint}"
    headers = {"Accept": "application/json"}

    try:
        response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except (ssl.SSLError, httpx.HTTPStatusError) as e:
        logger.error(f"Weather API error: {e}")
        return None


def _fetch_weather_data(
    params: dict[str, str | int | float],
) -> dict[str, str | int | float | list | dict]:
    """Executes a weather API request using the shared client configuration.

    Args:
        params: A dictionary of query parameters for the API request.

    Returns:
        The validated weather data from the API.

    Raises:
        ValueError: If the API returns an unexpected response format.
    """
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


def get_current_weather(
    latitude: float, longitude: float
) -> dict[str, str | int | float | list | dict]:
    """Gets the current weather for a specific geographic location.

    Args:
        latitude: The latitude of the location.
        longitude: The longitude of the location.

    Returns:
        A dictionary containing the current weather data.
    """
    fields = [
        "temperature_2m",
        "relative_humidity_2m",
        "apparent_temperature",
        "precipitation",
        "weather_code",
        "wind_speed_10m",
    ]

    params: dict[str, str | int | float] = {
        "latitude": latitude,
        "longitude": longitude,
        "current": ",".join(fields),
    }

    return _fetch_weather_data(params)


def get_forecast(
    latitude: float,
    longitude: float,
    days: int = 7,
) -> dict[str, str | int | float | list | dict]:
    """Gets the daily weather forecast for a location.

    Args:
        latitude: The latitude of the location.
        longitude: The longitude of the location.
        days: The number of days for the forecast. Defaults to 7.

    Returns:
        A dictionary containing the daily weather forecast.
    """
    days = max(1, min(16, days))

    fields = [
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
        "weather_code",
        "uv_index_max",
    ]

    params: dict[str, str | int | float] = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": ",".join(fields),
        "forecast_days": days,
        "timezone": "auto",
    }

    return _fetch_weather_data(params)
