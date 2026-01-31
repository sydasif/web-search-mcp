from unittest.mock import patch

import pytest

from web_search_mcp.download import download_media


@patch("web_search_mcp.download.os.makedirs")
@patch("web_search_mcp.download.yt_dlp.YoutubeDL")
def test_download_media_success(mock_ydl_cls, mock_makedirs):
    # Setup mock
    mock_ydl_instance = mock_ydl_cls.return_value
    mock_ydl_instance.__enter__.return_value = mock_ydl_instance

    mock_info = {
        "title": "Test Video",
        "duration": 60,
        "uploader": "Test Uploader",
        "view_count": 100,
        "description": "Test Description",
        "requested_downloads": [{"filepath": "downloads/Test Video.mp4"}],
    }
    mock_ydl_instance.extract_info.return_value = mock_info
    mock_ydl_instance.prepare_filename.return_value = "downloads/Test Video.mp4"

    # Execute
    result = download_media("https://example.com/video", "downloads", timeout=30)

    # Verify
    assert result["title"] == "Test Video"
    assert result["file_path"] == "downloads/Test Video.mp4"
    assert result["uploader"] == "Test Uploader"

    # Verify yt-dlp was called correctly
    mock_ydl_cls.assert_called_once()
    mock_ydl_instance.extract_info.assert_called_once_with(
        "https://example.com/video", download=True
    )
    mock_makedirs.assert_called_once()


@patch("web_search_mcp.download.os.makedirs")
@patch("web_search_mcp.download.yt_dlp.YoutubeDL")
def test_download_media_failure(mock_ydl_cls, mock_makedirs):
    # Setup mock to raise exception
    mock_ydl_instance = mock_ydl_cls.return_value
    mock_ydl_instance.__enter__.return_value = mock_ydl_instance
    mock_ydl_instance.extract_info.side_effect = Exception("Download error")

    # Execute & Verify
    with pytest.raises(Exception, match="Download error"):
        download_media("https://example.com/video")

    mock_makedirs.assert_called_once()
