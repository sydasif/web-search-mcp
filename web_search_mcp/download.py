import logging
import os
from typing import Any

import yt_dlp

logger = logging.getLogger("web-search-mcp")


def download_media(
    url: str, output_path: str = "~/Downloads", timeout: int = 30
) -> dict[str, Any]:
    """
    Download video/audio from URL using yt-dlp.

    Args:
        url: The URL to download content from.
        output_path: The directory to save the downloaded file (default: "~/Downloads").
        timeout: Socket timeout in seconds (default: 30).

    Returns:
        Dict containing metadata about the downloaded file (title, file_path, duration, uploader).

    Raises:
        Exception: If the download fails.
    """
    # Expand user home directory
    output_path = os.path.expanduser(output_path)

    # Ensure the output directory exists
    os.makedirs(output_path, exist_ok=True)

    # Configure yt-dlp options
    ydl_opts: dict[str, Any] = {
        "outtmpl": os.path.join(output_path, "%(title)s.%(ext)s"),
        "format": "bestvideo+bestaudio/best",  # Best quality, merging video+audio
        "merge_output_format": "mp4",  # Ensure final output is MP4 (requires ffmpeg)
        "quiet": True,  # Suppress stdout
        "no_warnings": True,
        "logger": logger,  # Use our logger
        "socket_timeout": timeout,
        "retries": 3,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore
            # extract_info with download=True performs the download
            info = ydl.extract_info(url, download=True)

            # prepare_filename returns the full path
            # With merge_output_format, yt-dlp handles the extension update in info
            file_path = ydl.prepare_filename(info)

            # Verification: If merged to mp4, ensure path reflects that
            if info.get("requested_downloads"):
                # If there were multiple downloads (video+audio) merged
                for d in info["requested_downloads"]:
                    if d.get("filepath"):
                        file_path = d["filepath"]
                        break

            # Fallback manual fix for merge_output_format if needed
            # (Sometimes prepare_filename still returns the unmerged ext)
            if ydl_opts.get("merge_output_format") == "mp4" and not file_path.endswith(
                ".mp4"
            ):
                base, _ = os.path.splitext(file_path)
                potential_path = f"{base}.mp4"
                if os.path.exists(potential_path):
                    file_path = potential_path

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
