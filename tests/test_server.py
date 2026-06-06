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
async def test_search_docs_tool(client):
    """Test the search_docs tool."""
    with patch("web_search_mcp.server.ddg_search") as mock_ddg_search:
        mock_ddg_search.return_value = SearchResponse(
            query="site:react.dev testing",
            search_type="text",
            total_results=0,
            results=[],
            has_more=False,
        )
        await client.call_tool("search_docs", {"query": "testing", "domain": "react.dev"})
        mock_ddg_search.assert_called_once()
        call_args = mock_ddg_search.call_args[0][0]
        assert call_args.query == "site:react.dev testing"
        assert call_args.search_type == "text"
        assert call_args.max_results == 5


@pytest.mark.asyncio
async def test_groq_research_tool(client):
    """Test the groq_research tool."""
    with patch("web_search_mcp.server._groq_research") as mock_groq_research:
        mock_groq_research.return_value = "Deep research results..."
        await client.call_tool("groq_research", {"query": "AI trends"})
        mock_groq_research.assert_called_once_with(query="AI trends", model="groq/compound")


@pytest.mark.asyncio
async def test_groq_analyze_page_tool(client):
    """Test the groq_analyze_page tool."""
    with patch("web_search_mcp.server._groq_analyze_page") as mock_groq_analyze:
        mock_groq_analyze.return_value = "Page analysis..."
        await client.call_tool(
            "groq_analyze_page",
            {"url": "https://example.com"},
        )
        mock_groq_analyze.assert_called_once_with(
            url="https://example.com",
            query="Summarize the key points of this page.",
            model="groq/compound",
        )


@patch("web_search_mcp.server.mcp")
def test_main_function(mock_mcp_instance):
    """Test that the main function calls mcp.run()."""
    main()
    mock_mcp_instance.run.assert_called_once_with(transport="stdio")


@pytest.mark.asyncio
async def test_groq_browse_tool(client):
    """Test the groq_browse tool calls browse correctly."""
    with patch("web_search_mcp.server._groq_browse") as mock_browse:
        mock_browse.return_value = "Search results about AI trends..."
        await client.call_tool(
            "groq_browse",
            {"query": "AI trends", "model": "openai/gpt-oss-120b", "reasoning_effort": "low"},
        )
        mock_browse.assert_called_once_with(
            query="AI trends", model="openai/gpt-oss-120b", reasoning_effort="low"
        )


@pytest.mark.asyncio
async def test_groq_browse_tool_default_reasoning(client):
    """Test groq_browse uses default reasoning_effort."""
    with patch("web_search_mcp.server._groq_browse") as mock_browse:
        mock_browse.return_value = "result"
        await client.call_tool("groq_browse", {"query": "test"})
        mock_browse.assert_called_once_with(
            query="test", model="openai/gpt-oss-20b", reasoning_effort="low"
        )
