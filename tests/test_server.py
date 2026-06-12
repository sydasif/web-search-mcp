from unittest.mock import patch
import pytest
import pytest_asyncio
from fastmcp.client import Client
from fastmcp.client.transports import FastMCPTransport
from web_search_mcp.models import SearchResponse, PageResponse

# Import the server instance
from web_search_mcp.server import mcp, main


@pytest_asyncio.fixture
async def client():
    """Fixture to create an in-memory client for the server."""
    transport = FastMCPTransport(mcp)
    async with Client(transport) as client:
        yield client


@pytest.mark.asyncio
async def test_web_search_tool(client):
    """Test that the web_search tool calls ddg_search correctly."""
    with patch("web_search_mcp.server.ddg_search") as mock_ddg_search:
        mock_ddg_search.return_value = SearchResponse(
            query="test", search_type="text", total_results=0, results=[], has_more=False
        )
        await client.call_tool("web_search", {"query": "test", "max_results": 10})

        mock_ddg_search.assert_called_once()
        call_args = mock_ddg_search.call_args[0][0]
        assert call_args.query == "test"
        assert call_args.max_results == 10


@pytest.mark.asyncio
async def test_fetch_page_tool(client):
    """Test the fetch_page tool."""
    with patch("web_search_mcp.server._fetch_page") as mock_fetch_page:
        mock_fetch_page.return_value = PageResponse(
            url="https://example.com", length=3, content="..."
        )
        await client.call_tool("fetch_page", {"url": "https://example.com"})
        mock_fetch_page.assert_called_once_with(
            url="https://example.com",
            output_format="txt",
            include_metadata=False,
            include_tables=False,
            include_comments=False,
            include_images=False,
            deduplicate=True,
            max_length=15000,
            timeout=30,
            backend="auto",
        )


@pytest.mark.asyncio
async def test_web_search_domain_scoping(client):
    """Test web_search with domain parameter scopes results."""
    with patch("web_search_mcp.server.ddg_search") as mock_ddg_search:
        mock_ddg_search.return_value = SearchResponse(
            query="site:react.dev testing",
            search_type="text",
            total_results=0,
            results=[],
            has_more=False,
        )
        await client.call_tool("web_search", {"query": "testing", "domain": "react.dev"})
        mock_ddg_search.assert_called_once()
        call_args = mock_ddg_search.call_args[0][0]
        assert call_args.query == "site:react.dev testing"
        assert call_args.search_type == "text"


@pytest.mark.asyncio
async def test_groq_search_tool(client):
    """Test the groq_search tool."""
    with patch("web_search_mcp.server._groq_search") as mock_groq_search:
        mock_groq_search.return_value = "Deep research results..."
        await client.call_tool("groq_search", {"query": "AI trends"})
        mock_groq_search.assert_called_once_with(
            query="AI trends", model="groq/compound-mini", reasoning_effort="low"
        )


@pytest.mark.asyncio
async def test_groq_analyze_tool(client):
    """Test the groq_analyze tool."""
    with patch("web_search_mcp.server._groq_analyze") as mock_analyze:
        mock_analyze.return_value = "Page analysis..."
        await client.call_tool(
            "groq_analyze",
            {"url": "https://example.com"},
        )
        mock_analyze.assert_called_once_with(
            url="https://example.com",
            query="Summarize the key points of this page.",
            model="groq/compound-mini",
        )


@patch("web_search_mcp.server.mcp")
def test_main_function(mock_mcp_instance):
    """Test that the main function calls mcp.run()."""
    main()
    mock_mcp_instance.run.assert_called_once_with(transport="stdio")


@pytest.mark.asyncio
async def test_groq_search_with_gpt_oss_model(client):
    """Test groq_search with GPT-OSS model passes reasoning_effort."""
    with patch("web_search_mcp.server._groq_search") as mock_groq_search:
        mock_groq_search.return_value = "Search results about AI trends..."
        await client.call_tool(
            "groq_search",
            {"query": "AI trends", "model": "openai/gpt-oss-120b", "reasoning_effort": "low"},
        )
        mock_groq_search.assert_called_once_with(
            query="AI trends", model="openai/gpt-oss-120b", reasoning_effort="low"
        )


@pytest.mark.asyncio
async def test_groq_search_default_reasoning(client):
    """Test groq_search uses default reasoning_effort."""
    with patch("web_search_mcp.server._groq_search") as mock_groq_search:
        mock_groq_search.return_value = "result"
        await client.call_tool("groq_search", {"query": "test"})
        mock_groq_search.assert_called_once_with(
            query="test", model="groq/compound-mini", reasoning_effort="low"
        )
