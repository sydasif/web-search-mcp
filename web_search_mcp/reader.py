import trafilatura
import logging

logger = logging.getLogger("web-search-mcp")


def fetch_page(url: str) -> dict:
    """Extracts clean text from a URL without ads/clutter."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return {"error": "Could not download content."}

        result = trafilatura.extract(downloaded, include_links=True)
        if not result:
            return {"error": "No readable text found."}

        return {"url": url, "content": result[:15000], "length": len(result)}
    except Exception as e:
        logger.error(f"Reader error: {e}")
        return {"error": str(e)}
