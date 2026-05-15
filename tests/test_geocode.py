import unittest
from unittest.mock import patch
from web_search_mcp.geocode import geocode_location


class TestGeocode(unittest.TestCase):
    def test_geocode_location_basic(self):
        """Test basic geocoding functionality"""
        # This is a mock test since we can't make actual API calls in tests
        with patch("httpx.Client.get") as mock_get:
            # Mock response data
            mock_response = {"display_name": "New York, USA", "lat": 40.7128, "lon": -74.0060}

            mock_resp_obj = unittest.mock.Mock()
            mock_resp_obj.json.return_value = [mock_response]
            mock_resp_obj.raise_for_status.return_value = None

            mock_get.return_value = mock_resp_obj

            result = geocode_location("New York")

            self.assertIn("results", result)
            self.assertEqual(len(result["results"]), 1)
            self.assertEqual(result["results"][0]["display_name"], "New York, USA")

    def test_geocode_location_empty_query(self):
        """Test geocoding with empty query"""
        result = geocode_location("")

        self.assertIn("error", result)
        self.assertEqual(result["error"], "Query parameter is required and cannot be empty")

    def test_geocode_location_limit_validation(self):
        """Test that limit is properly validated"""
        with patch("httpx.Client.get") as mock_get:
            # Mock response data
            mock_response = {"display_name": "London, UK", "lat": 51.5074, "lon": -0.1278}

            mock_resp_obj = unittest.mock.Mock()
            mock_resp_obj.json.return_value = [mock_response]
            mock_resp_obj.raise_for_status.return_value = None

            mock_get.return_value = mock_resp_obj

            # Test with a valid limit
            result = geocode_location("London", limit=10)

            # Verify the function processes the request without error
            self.assertIn("results", result)
            self.assertIsInstance(result["results"], list)


if __name__ == "__main__":
    unittest.main()
