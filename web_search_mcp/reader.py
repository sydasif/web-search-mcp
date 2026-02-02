import trafilatura
import logging
import httpx
from typing import Literal

logger = logging.getLogger("web-search-mcp")


def fetch_page(
    url: str,
    output_format: Literal["csv", "html", "json", "markdown", "python", "txt", "xml", "xmltei"] = "txt",
    include_metadata: bool = False,
    include_tables: bool = False,
    include_comments: bool = False,
    include_images: bool = False,
    deduplicate: bool = True,
    max_length: int = 15000,
    timeout: int = 30,
) -> dict:
    """Extracts the full text content from a web page URL.

    Args:
        url: The URL to fetch and extract content from
        output_format: Format for extracted content ('csv', 'html', 'json', 'markdown', 'python', 'txt', 'xml', 'xmltei')
        include_metadata: Whether to include document metadata (title, author, date, etc.)
        include_tables: Whether to include table content in extraction
        include_comments: Whether to include comment content in extraction
        include_images: Whether to include image descriptions in extraction
        deduplicate: Whether to remove duplicated content
        max_length: Maximum length of content to return (default 15000)
        timeout: Request timeout in seconds (default 30)
    """
    try:
        # Download the content with timeout control using proper client management
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, headers={"User-Agent": "web-search-mcp/1.0"})
            response.raise_for_status()
            html_content = response.text

        if not html_content:
            return {"error": "Could not download content."}

        # Perform extraction with specified parameters
        extracted_data = trafilatura.extract(
            html_content,
            output_format=output_format,
            with_metadata=include_metadata,
            include_tables=include_tables,
            include_comments=include_comments,
            include_links=True,
            include_images=include_images,
            deduplicate=deduplicate,
        )

        content = None
        metadata = None

        if include_metadata:
            if isinstance(extracted_data, tuple):
                content, metadata = extracted_data
            else:  # It's a string or None
                content = extracted_data
        else:
            content = extracted_data

        if not content:
            return {"error": "No readable text found."}

        # Determine the actual length before truncation
        actual_length = len(str(content))

        # Structure the response based on format
        response_data = {"url": url, "length": actual_length}

        # Handle content truncation
        response_data["content"] = str(content)[:max_length]

        # Add metadata if requested and available
        if include_metadata:
            if metadata:
                response_data["metadata"] = {
                    "title": getattr(metadata, "title", None),
                    "author": getattr(metadata, "author", None),
                    "date": getattr(metadata, "date", None),
                    "description": getattr(metadata, "description", None),
                    "fingerprint": getattr(metadata, "fingerprint", None),
                }
            else:
                response_data["warning"] = "Could not extract metadata."

        return response_data

    except httpx.TimeoutException as e:
        logger.error(f"Timeout during fetch: {e}")
        return {"error": f"Request timed out after {timeout}s: {str(e)}"}
    except httpx.RequestError as e:
        logger.error(f"HTTP error during fetch: {e}")
        return {"error": f"HTTP request failed: {str(e)}"}
    except Exception as e:
        logger.error(f"Reader error: {e}")
        return {"error": str(e)}
