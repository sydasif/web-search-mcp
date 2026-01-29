from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from web_search_mcp.weather import get_current_weather, get_forecast


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

    # Mock the context manager returned by httpx.AsyncClient
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_resp_obj = MagicMock()
        mock_resp_obj.status_code = 200
        mock_resp_obj.json.return_value = mock_response
        mock_client.get.return_value = mock_resp_obj

        result = await get_current_weather(40.7128, -74.0060)

        assert result == mock_response
        mock_client.get.assert_called_once()
        # Verify URL contains correct parameters
        call_args = mock_client.get.call_args
        assert "latitude=40.7128" in call_args[0][0]
        # Python float formatting might drop trailing zeros, so check for partial match
        # or just check the value we passed
        assert "longitude=-74.006" in call_args[0][0]
        assert "current=" in call_args[0][0]


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

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_resp_obj = MagicMock()
        mock_resp_obj.status_code = 200
        mock_resp_obj.json.return_value = mock_response
        mock_client.get.return_value = mock_resp_obj

        result = await get_forecast(40.7128, -74.0060, days=10)

        assert result == mock_response
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "forecast_days=10" in call_args[0][0]


@pytest.mark.asyncio
async def test_api_failure():
    """Test handling of API failure."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        # Simulate an exception
        mock_client.get.side_effect = Exception("Connection error")

        result = await get_current_weather(40.7128, -74.0060)

        assert "error" in result
        assert result["error"] == "Unable to fetch weather data."
