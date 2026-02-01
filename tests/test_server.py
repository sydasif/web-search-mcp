from unittest.mock import patch
import pytest
import pytest_asyncio
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport

# Import the server instance
from web_search_mcp.server import mcp, main


@pytest_asyncio.fixture
async def client():
    """Fixture to create an in-memory client for the server."""
    transport = FastMCPTransport(mcp)
    async with Client(transport) as client:
        yield client


@pytest.mark.asyncio
async def test_search_web_tool(client):
    """Test that the search_web tool calls ddg_search correctly."""
    with patch("web_search_mcp.server.ddg_search") as mock_ddg_search:
        mock_ddg_search.return_value = {"results": []}
        await client.call_tool("search_web", {"query": "test", "max_results": 10})

        mock_ddg_search.assert_called_once()
        call_args = mock_ddg_search.call_args[0][0]
        assert call_args.query == "test"
        assert call_args.max_results == 10


@pytest.mark.asyncio
async def test_get_weather_tool_current_mode(client):
    """Test the get_weather tool in current mode."""
    with patch("web_search_mcp.server.weather_current") as mock_weather_current:
        mock_weather_current.return_value = {"temp": 15}
        await client.call_tool(
            "get_weather", {"latitude": 40.0, "longitude": -70.0, "mode": "current"}
        )
        mock_weather_current.assert_called_once_with(40.0, -70.0)


@pytest.mark.asyncio
async def test_get_weather_tool_forecast_mode(client):
    """Test the get_weather tool in forecast mode (default)."""
    with patch("web_search_mcp.server.weather_forecast") as mock_weather_forecast:
        mock_weather_forecast.return_value = {"forecast": []}
        await client.call_tool(
            "get_weather", {"latitude": 40.0, "longitude": -70.0, "mode": "forecast", "days": 5}
        )
        mock_weather_forecast.assert_called_once_with(40.0, -70.0, 5)


@pytest.mark.asyncio
async def test_get_weather_tool_forecast_default_days(client):
    """Test the get_weather tool uses default days=7 in forecast mode."""
    with patch("web_search_mcp.server.weather_forecast") as mock_weather_forecast:
        mock_weather_forecast.return_value = {"forecast": []}
        await client.call_tool("get_weather", {"latitude": 40.0, "longitude": -70.0})
        mock_weather_forecast.assert_called_once_with(40.0, -70.0, 7)


@pytest.mark.asyncio
async def test_fetch_page_tool(client):
    """Test the fetch_page tool."""
    with patch("web_search_mcp.server._fetch_page") as mock_fetch_page:
        mock_fetch_page.return_value = {"content": "..."}
        await client.call_tool("fetch_page", {"url": "https://example.com"})
        mock_fetch_page.assert_called_once_with(
            url="https://example.com",
            output_format="text",
            include_metadata=False,
            include_tables=False,
            include_comments=False,
            include_images=False,
            deduplicate=True,
            max_length=15000,
            timeout=30,
        )


@pytest.mark.asyncio
async def test_search_docs_tool(client):
    """Test the search_docs tool."""
    with patch("web_search_mcp.server._search_docs") as mock_search_docs:
        mock_search_docs.return_value = {"results": []}
        await client.call_tool("search_docs", {"query": "testing", "tech_stack": "react"})
        mock_search_docs.assert_called_once_with("testing", tech_stack="react")


@patch("web_search_mcp.server.mcp")
def test_main_function(mock_mcp_instance):
    """Test that the main function calls mcp.run()."""
    main()
    mock_mcp_instance.run.assert_called_once_with(transport="stdio")
