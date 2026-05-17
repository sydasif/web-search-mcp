from unittest.mock import patch, Mock
from web_search_mcp.geocode import geocode_location


def test_geocode_location_basic():
    """Test basic geocoding functionality."""
    # Arrange
    mock_response = {"display_name": "New York, USA", "lat": 40.7128, "lon": -74.0060}
    mock_resp_obj = Mock()
    mock_resp_obj.json.return_value = [mock_response]
    mock_resp_obj.raise_for_status.return_value = None

    with patch("httpx.Client.get", return_value=mock_resp_obj):
        # Act
        result = geocode_location("New York")

        # Assert
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["display_name"] == "New York, USA"


def test_geocode_location_empty_query():
    """Test geocoding with empty query."""
    # Act
    result = geocode_location("")

    # Assert
    assert "error" in result
    assert result["error"] == "Query parameter is required and cannot be empty"


def test_geocode_location_limit_validation():
    """Test that limit is properly validated."""
    # Arrange
    mock_response = {"display_name": "London, UK", "lat": 51.5074, "lon": -0.1278}
    mock_resp_obj = Mock()
    mock_resp_obj.json.return_value = [mock_response]
    mock_resp_obj.raise_for_status.return_value = None

    with patch("httpx.Client.get", return_value=mock_resp_obj):
        # Act
        result = geocode_location("London", limit=10)

        # Assert
        assert "results" in result
        assert isinstance(result["results"], list)
