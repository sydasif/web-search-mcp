"""Offline unit tests for URL validation in _http.client."""
from __future__ import annotations

import pytest

from web_search_mcp._http.client import validate_url


class TestUnsupportedSchemes:
    """Unsupported URL schemes must raise ValueError."""

    @pytest.mark.parametrize("url", [
        "ftp://example.com/file",
        "file:///etc/passwd",
        "ssh://user@host",
        "gopher://example.com",
        "javascript:alert(1)",
        "data:text/html,<h1>hi</h1>",
        "mailto:user@example.com",
    ])
    def test_raises_on_unsupported_scheme(self, url: str) -> None:
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            validate_url(url)


class TestMissingHostname:
    """URLs with no hostname must raise ValueError."""

    @pytest.mark.parametrize("url", [
        "https://",
        "https://?query=val",
        "https://?query=val#frag",
        "https:///path",
    ])
    def test_raises_on_missing_hostname(self, url: str) -> None:
        with pytest.raises(ValueError, match="no hostname"):
            validate_url(url)


class TestBlockedIPv4:
    """Private/internal IPv4 addresses must be blocked."""

    @pytest.mark.parametrize("ip", [
        "127.0.0.1",
        "127.1.2.3",
        "10.0.0.1",
        "10.255.255.255",
        "192.168.1.1",
        "192.168.0.1",
        "172.16.0.1",
        "172.31.255.255",
        "169.254.1.1",
        "240.0.0.1",
        "255.255.255.255",
    ])
    def test_raises_on_blocked_ipv4(self, ip: str) -> None:
        with pytest.raises(ValueError, match="blocked address range"):
            validate_url(f"https://{ip}/")

class TestBlockedIPv6:
    """Private/internal IPv6 addresses must be blocked."""

    @pytest.mark.parametrize("addr", [
        "::1",
        "fe80::1",
        "fd00::1",
        "::2",
    ])
    def test_raises_on_blocked_ipv6(self, addr: str) -> None:
        with pytest.raises(ValueError, match="blocked address range"):
            validate_url(f"https://[{addr}]/")

class TestIPv4MappedIPv6:
    """IPv4-mapped IPv6 addresses resolve to the IPv4 address and must be blocked."""

    @pytest.mark.parametrize("addr,expect_msg", [
        ("::ffff:127.0.0.1", "blocked address range"),
        ("::ffff:10.0.0.1", "blocked address range"),
        ("::ffff:192.168.1.1", "blocked address range"),
    ])
    def test_raises_on_ipv4_mapped_blocked(self, addr: str, expect_msg: str) -> None:
        with pytest.raises(ValueError, match=expect_msg):
            validate_url(f"https://[{addr}]/")


class TestValidURLs:
    """Public/valid URLs must pass through unchanged."""

    @pytest.mark.parametrize("url", [
        "https://example.com",
        "https://example.com/path?q=1",
        "http://example.com",
        "https://8.8.8.8/",
        "https://1.1.1.1/",
        "https://www.github.com/user/repo",
    ])
    def test_returns_valid_url(self, url: str) -> None:
        assert validate_url(url) == url
