from unittest.mock import patch, MagicMock
from web_search_mcp.finance import get_finance


def test_get_finance_success():
    """Test successful fetch of finance data."""
    with patch("web_search_mcp.finance.yf.Ticker") as mock_ticker:
        mock_info = {
            "currentPrice": 150.75,
            "currency": "USD",
            "longBusinessSummary": "This is a long summary of a test company.",
            "website": "https://test.com",
        }
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = mock_info
        mock_ticker.return_value = mock_ticker_instance

        symbol = "TEST"
        result = get_finance(symbol)

        assert result["symbol"] == symbol
        assert result["price"] == 150.75
        assert result["currency"] == "USD"
        assert "long summary" in result["business_summary"]
        mock_ticker.assert_called_once_with(symbol)


def test_get_finance_invalid_symbol():
    """Test handling of an invalid stock symbol."""
    with patch("web_search_mcp.finance.yf.Ticker") as mock_ticker:
        mock_ticker.side_effect = Exception("Invalid ticker")

        symbol = "INVALID"
        result = get_finance(symbol)

        assert "error" in result
        assert "Invalid ticker" in result["error"]


def test_get_finance_missing_keys():
    """Test robustness against missing keys in the API response."""
    with patch("web_search_mcp.finance.yf.Ticker") as mock_ticker:
        mock_info = {
            # No price, no summary, no website
            "currency": "USD",
        }
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = mock_info
        mock_ticker.return_value = mock_ticker_instance

        symbol = "TEST"
        result = get_finance(symbol)

        assert result.get("price") is None
        assert result.get("business_summary") == ""
        assert result.get("website") is None
        assert result["currency"] == "USD"


def test_get_finance_price_fallback():
    """Test that it correctly falls back to regularMarketPrice."""
    with patch("web_search_mcp.finance.yf.Ticker") as mock_ticker:
        mock_info = {
            "regularMarketPrice": 148.25,
            "currency": "USD",
            "longBusinessSummary": "Summary here.",
            "website": "https://fallback.com",
        }
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.info = mock_info
        mock_ticker.return_value = mock_ticker_instance

        symbol = "FALLBACK"
        result = get_finance(symbol)

        assert result["price"] == 148.25
