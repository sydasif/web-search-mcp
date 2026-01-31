import logging
import os
from typing import Any

import yt_dlp

logger = logging.getLogger("web-search-mcp")


def download_media(
    url: str, output_path: str = "downloads", timeout: int = 30
) -> dict[str, Any]:
    """
    Download video/audio from URL using yt-dlp.

    Args:
        url: The URL to download content from.
        output_path: The directory to save the downloaded file (default: "downloads").
        timeout: Socket timeout in seconds (default: 30).

    Returns:
        Dict containing metadata about the downloaded file (title, file_path, duration, uploader).

    Raises:
        Exception: If the download fails.
    """
    # Ensure the output directory exists
    os.makedirs(output_path, exist_ok=True)

    # Configure yt-dlp options
    ydl_opts: dict[str, Any] = {
        "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
        "format": "best",  # Download best quality available
        "quiet": True,  # Suppress stdout
        "no_warnings": True,
        "logger": logger,  # Use our logger
        "socket_timeout": timeout,
        "retries": 3,
        # We assume ffmpeg is available as per user confirmation
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
            # extract_info with download=True performs the download
            info = ydl.extract_info(url, download=True)

            # info is a dict with metadata
            # prepare_filename returns the full path to the downloaded file
            file_path = ydl.prepare_filename(info)

            return {
                "title": info.get("title", "Unknown"),
                "file_path": file_path,
                "duration": info.get("duration"),
                "uploader": info.get("uploader"),
                "view_count": info.get("view_count"),
                "description": info.get("description"),
            }
    except Exception as e:
        logger.error(f"Error downloading media from {url}: {e}")
        raise
