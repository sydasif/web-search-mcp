import trafilatura
import logging
import httpx
from typing import Literal

from .http_client import http_client

logger = logging.getLogger("web-search-mcp")


def fetch_page(
    url: str,
    output_format: Literal[
        "csv", "html", "json", "markdown", "python", "txt", "xml", "xmltei"
    ] = "txt",
    include_metadata: bool = False,
    include_tables: bool = False,
    include_comments: bool = False,
    include_images: bool = False,
    deduplicate: bool = True,
    max_length: int = 15000,
    timeout: int = 30,
) -> dict:
    """Extracts the full text content from a web page URL."""
    try:
        # Download the content using shared client
        response = http_client.get(url, timeout=timeout)
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

        metadata = None

        if include_metadata:
            if isinstance(extracted_data, tuple):
                content, metadata = extracted_data
            else:
                content = extracted_data
        else:
            content = extracted_data

        if not content:
            return {"error": "No readable text found."}

        actual_length = len(str(content))
        response_data = {"url": url, "length": actual_length, "content": str(content)[:max_length]}

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
