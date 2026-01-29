import ssl
from typing import Any

import httpx

API_BASE = "https://api.open-meteo.com/v1"
USER_AGENT = "web-search-mcp/1.0"

# Create a custom SSL context that allows for potential proxy/corporate firewall issues
# while still maintaining security where possible.
try:
    SSL_CONTEXT = ssl.create_default_context()
except Exception:
    # Fallback if default creation fails
    SSL_CONTEXT = ssl._create_unverified_context()


async def make_openmeteo_request(url: str) -> dict[str, Any] | None:
    """
    Make request to OpenMeteo API with proper error handling.

    Args:
        url: Full API URL to fetch

    Returns:
        JSON response as dict or None if request fails
    """
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

    try:
        # We use a reasonably long timeout as weather APIs can sometimes be slow
        # verify=SSL_CONTEXT handles the certificate verification
        async with httpx.AsyncClient(verify=SSL_CONTEXT, timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
    except ssl.SSLError as e:
        # This is often the specific error in corporate environments
        print(f"Weather API SSL error: {e}")
        return None
    except httpx.HTTPStatusError as e:
        print(f"Weather API HTTP error {e.response.status_code}")
        return None
    except Exception as e:
        print(f"Weather API Request failed: {e}")
        return None


async def get_current_weather(latitude: float, longitude: float) -> dict[str, Any]:
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

    url = (
        f"{API_BASE}/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        f"&current={','.join(fields)}"
    )

    data = await make_openmeteo_request(url)

    if not data:
        return {"error": "Unable to fetch weather data."}

    # Return the raw structure which is already well-formatted JSON
    # The LLM can interpret "temperature_2m": 15.5 easily.
    return data


async def get_forecast(
    latitude: float, longitude: float, days: int = 7
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

    url = (
        f"{API_BASE}/forecast"
        f"?latitude={latitude}&longitude={longitude}"
        f"&daily={','.join(fields)}"
        f"&forecast_days={days}"
        "&timezone=auto"
    )

    data = await make_openmeteo_request(url)

    if not data:
        return {"error": "Unable to fetch forecast data."}

    return data
