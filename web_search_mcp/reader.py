import trafilatura
import logging
import httpx
from typing import Literal

logger = logging.getLogger("web-search-mcp")


def fetch_page(
    url: str,
    output_format: Literal["text", "markdown", "json"] = "text",
    include_metadata: bool = False,
    include_tables: bool = False,
    include_comments: bool = False,
    include_images: bool = False,
    deduplicate: bool = True,
    max_length: int = 15000,
    timeout: int = 30,
) -> dict:
    """Extracts clean text from a URL without ads/clutter."""
    try:
        # Download the content with timeout control
        response = httpx.get(url, headers={"User-Agent": "web-search-mcp/1.0"}, timeout=timeout)
        response.raise_for_status()

        html_content = response.text

        if not html_content:
            return {"error": "Could not download content."}

        # Prepare extraction parameters based on settings
        extraction_params = {
            "output_format": output_format,
            "with_metadata": include_metadata,
            "include_tables": include_tables,
            "include_comments": include_comments,
            "include_links": True,
            "include_images": include_images,
            "deduplicate": deduplicate,
        }

        # Perform extraction with specified parameters
        result = trafilatura.extract(html_content, **extraction_params)

        if not result:
            return {"error": "No readable text found."}

        # Determine the actual length before truncation
        actual_length = len(str(result))  # Convert to string to get actual length for any format

        # Structure the response based on format
        response_data = {"url": url, "length": actual_length}

        # Handle content truncation properly for all formats
        content_str = str(result) if isinstance(result, (str, bytes)) else str(result)
        response_data["content"] = content_str[:max_length]

        # Add metadata if requested and available
        if include_metadata:
            try:
                metadata = trafilatura.extract_metadata(html_content)
                if metadata:
                    # Convert metadata to dict, accessing only available attributes
                    meta_dict = {"title": getattr(metadata, "title", None)}
                    if hasattr(metadata, "author"):
                        meta_dict["author"] = getattr(metadata, "author", None)
                    if hasattr(metadata, "date"):
                        meta_dict["date"] = getattr(metadata, "date", None)
                    if hasattr(metadata, "description"):
                        meta_dict["description"] = getattr(metadata, "description", None)
                    if hasattr(metadata, "fingerprint"):
                        meta_dict["fingerprint"] = getattr(metadata, "fingerprint", None)

                    response_data["metadata"] = meta_dict
            except Exception as metadata_error:
                # Log the metadata extraction error for debugging
                logger.debug(f"Metadata extraction failed: {metadata_error}")

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
