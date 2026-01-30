from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from web_search_mcp.weather import (
    get_current_weather,
    get_forecast,
    make_openmeteo_request,
)


@pytest.mark.asyncio
async def test_get_current_weather_success():
    """Test successful current weather fetch."""
    mock_response = {
        "latitude": 40.71,
        "longitude": -74.01,
        "current": {
            "time": "2023-10-27T12:00",
            "interval": 900,
            "temperature_2m": 15.5,
            "relative_humidity_2m": 60,
            "apparent_temperature": 14.2,
            "precipitation": 0.0,
            "weather_code": 1,
            "wind_speed_10m": 12.5,
        },
    }

    # Mock the make_openmeteo_request function since that's where the API call happens
    with patch("web_search_mcp.weather.make_openmeteo_request") as mock_make_request:
        mock_make_request.return_value = mock_response

        result = await get_current_weather(40.7128, -74.0060)

        assert result == mock_response
        mock_make_request.assert_called_once()
        # Check that it was called with the correct client and parameters
        call_args = mock_make_request.call_args
        # args[0] is client, args[1] is endpoint, args[2] is params
        assert call_args[0][1] == "forecast"  # endpoint
        params = call_args[0][2]  # params
        assert params["latitude"] == 40.7128
        assert params["longitude"] == -74.0060
        assert "temperature_2m" in params["current"]


@pytest.mark.asyncio
async def test_get_forecast_success():
    """Test successful forecast fetch."""
    mock_response = {
        "daily": {
            "time": ["2023-10-27"],
            "temperature_2m_max": [18.0],
            "temperature_2m_min": [10.0],
            "precipitation_sum": [0.0],
            "weather_code": [1],
            "uv_index_max": [4.5],
        }
    }

    with patch("web_search_mcp.weather.make_openmeteo_request") as mock_make_request:
        mock_make_request.return_value = mock_response

        result = await get_forecast(40.7128, -74.0060, days=10)

        assert result == mock_response
        mock_make_request.assert_called_once()
        call_args = mock_make_request.call_args
        params = call_args[0][2]  # params
        assert params["forecast_days"] == 10


@pytest.mark.asyncio
async def test_api_failure():
    """Test handling of API failure."""
    with patch("web_search_mcp.weather.make_openmeteo_request") as mock_make_request:
        # Simulate None return (failed API call)
        mock_make_request.return_value = None

        result = await get_current_weather(40.7128, -74.0060)

        assert "error" in result
        assert result["error"] == "Unable to fetch weather data."
