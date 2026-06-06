from typing import Literal
from pydantic import BaseModel, Field


FetchOutputFormat = Literal["csv", "html", "json", "markdown", "python", "txt", "xml", "xmltei"]


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str
    details: str


class SearchResult(BaseModel):
    """A single search result item."""

    title: str | None = None
    href: str | None = None
    url: str | None = None
    body: str | None = None


class SearchResponse(BaseModel):
    """Structured response for search operations."""

    query: str
    search_type: Literal["text", "news"]
    total_results: int
    results: list[SearchResult]
    has_more: bool
    next_page: int | None = None
    error: str | None = None
    details: str | None = None


class PageResponse(BaseModel):
    """Structured response for page extraction."""

    url: str
    length: int
    content: str
    metadata: dict[str, str | None] | None = None
    warning: str | None = None


class SearchRequest(BaseModel):
    """Request schema for web and news searches.

    Attributes:
        query: The search query string.
        search_type: The type of search to perform ('text' or 'news'). Defaults to 'text'.
        max_results: Maximum number of results to return. Must be >= 1. Defaults to 5.
        time_range: Time filter for results (e.g., 'd', 'w', 'm', 'y').
        region: Geographic region for search (e.g., 'us-en').
        safesearch: Safe search level ('moderate', 'off', 'on'). Defaults to 'moderate'.
        page: Page number for pagination. Must be >= 1. Defaults to 1.
        backend: Search backend to use ('auto', 'legacy', 'api'). Defaults to 'auto'.
        response_format: Desired response format ('json', 'markdown'). Defaults to 'markdown'.
    """

    query: str
    search_type: Literal["text", "news"] = "text"
    max_results: int = Field(default=5, ge=1)
    time_range: str | None = None
    region: str | None = None
    safesearch: Literal["moderate", "off", "on"] = "moderate"
    page: int = Field(default=1, ge=1)
    backend: Literal["auto", "legacy", "api"] = "auto"
    response_format: Literal["json", "markdown"] = "markdown"


class GroqBrowseInput(BaseModel):
    """Input model for groq_browse tool.

    Attributes:
        query: Search question or topic for interactive browsing.
        model: Groq model to use ('openai/gpt-oss-20b' or 'openai/gpt-oss-120b').
        reasoning_effort: Reasoning intensity ('low', 'medium', 'high').
            'low' is recommended for most queries to balance quality and token usage.
    """

    query: str = Field(
        ...,
        min_length=1,
        description="Search question or topic for the model to browse",
    )
    model: Literal["openai/gpt-oss-20b", "openai/gpt-oss-120b"] = Field(
        default="openai/gpt-oss-20b",
        description="Groq model to use. 'openai/gpt-oss-20b' is faster; 'openai/gpt-oss-120b' has larger context window (131K)",
    )
    reasoning_effort: Literal["low", "medium", "high"] = Field(
        default="low",
        description="Reasoning intensity. 'low' saves tokens, 'high' explores more pages",
    )


class GroqResearchInput(BaseModel):
    """Input model for groq_research tool.

    Attributes:
        query: Research question or topic for deep investigation.
        model: Compound system to use ('groq/compound' or 'groq/compound-mini').
    """

    query: str = Field(
        ...,
        min_length=1,
        description="Research question or topic for deep investigation",
    )
    model: Literal["groq/compound", "groq/compound-mini"] = Field(
        default="groq/compound",
        description="Compound system. 'groq/compound' supports up to 10 tool calls; 'groq/compound-mini' has ~3x lower latency but 1 tool call max",
    )


class GroqAnalyzePageInput(BaseModel):
    """Input model for groq_analyze_page tool.

    Attributes:
        url: The URL to visit and analyze.
        query: What to do with the page content.
        model: Compound system to use.
    """

    url: str = Field(..., min_length=1, description="The URL to visit and analyze")
    query: str = Field(
        default="Summarize the key points of this page.",
        description="What to do with the page content (e.g. 'Extract the data table', 'Find the author's argument')",
    )
    model: Literal["groq/compound", "groq/compound-mini"] = Field(
        default="groq/compound",
        description="Compound system. 'groq/compound' for full analysis, 'groq/compound-mini' for faster results",
    )
