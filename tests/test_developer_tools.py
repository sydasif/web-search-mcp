"""Tests for developer-focused tools (registries, errors, compare)."""

from __future__ import annotations

from unittest.mock import patch, MagicMock
from web_search_mcp.registries import (
    PackageInfo,
    lookup_package,
    search_packages,
    format_package_info,
    format_package_list,
    _detect_registry,
    _fmt_downloads,
    _fmt_date,
)
from web_search_mcp.errors import ErrorParser
from web_search_mcp.utils import ErrorResponse


# ═══════════════════════════════════════════════════════════
#  registries.py  —  package lookup & search
# ═══════════════════════════════════════════════════════════


class TestDetectRegistry:
    """Auto-detection of registry from package name."""

    def test_npm_scoped_package(self):
        assert _detect_registry("@angular/core") == "npm"

    def test_go_module(self):
        assert _detect_registry("github.com/gin-gonic/gin") == "go"

    def test_pypi_with_dot(self):
        assert _detect_registry("numpy") == "npm"  # no dots → npm default
        assert _detect_registry("some.package") == "pypi"  # has dots → pypi

    def test_npm_fallback(self):
        assert _detect_registry("express") == "npm"


class TestFmtDownloads:
    """Human-readable download formatting."""

    def test_millions(self):
        assert _fmt_downloads(5_000_000) == "5.0M"

    def test_thousands(self):
        assert _fmt_downloads(1234) == "1.2K"

    def test_small(self):
        assert _fmt_downloads(42) == "42"

    def test_zero(self):
        assert _fmt_downloads(0) == "0"


class TestFmtDate:
    """Relative date formatting."""

    def test_today_same_day(self):
        result = _fmt_date("today")
        assert result is not None

    def test_invalid_date(self):
        assert _fmt_date("not-a-date") == "not-a-date"

    def test_none_input(self):
        assert _fmt_date(None) is None


class TestLookupPackage:
    """Package info lookups with mocked HTTP."""

    @patch("web_search_mcp.registries.httpx.Client")
    def test_lookup_npm_success(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        # Mock npm registry response
        registry_resp = MagicMock()
        registry_resp.json.return_value = {
            "name": "express",
            "description": "Fast, unopinionated web framework",
            "dist-tags": {"latest": "4.18.2"},
            "versions": {
                "4.18.2": {
                    "license": "MIT",
                    "dependencies": {"accepts": "1.3.8", "array-flatten": "1.1.1"},
                    "homepage": "https://expressjs.com",
                }
            },
            "time": {"4.18.2": "2023-10-01T12:00:00Z"},
            "repository": {"url": "https://github.com/expressjs/express"},
            "keywords": ["web", "framework"],
        }
        registry_resp.is_success = True

        # Mock downloads response
        dl_resp = MagicMock()
        dl_resp.is_success = True
        dl_resp.json.return_value = {"downloads": 25000000}

        # Side effect: first call = registry, second = downloads
        mock_client.get.side_effect = [registry_resp, dl_resp]

        result = lookup_package("express", registry="npm")
        assert isinstance(result, PackageInfo)
        assert result.name == "express"
        assert result.version == "4.18.2"
        assert result.description == "Fast, unopinionated web framework"
        assert result.license == "MIT"
        assert result.downloads == "25.0M/week"
        assert result.dependencies_count == 2
        assert "web" in result.keywords

    @patch("web_search_mcp.registries.httpx.Client")
    def test_lookup_pypi_success(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        pypi_resp = MagicMock()
        pypi_resp.json.return_value = {
            "info": {
                "name": "requests",
                "version": "2.31.0",
                "summary": "Python HTTP for Humans.",
                "license": "Apache-2.0",
                "requires_dist": ["urllib3", "certifi", "charset-normalizer"],
                "keywords": "http,requests",
                "home_page": "https://requests.readthedocs.io",
                "project_urls": {"Source": "https://github.com/psf/requests"},
            }
        }
        pypi_resp.is_success = True

        dl_resp = MagicMock()
        dl_resp.is_success = False  # No download stats

        mock_client.get.side_effect = [pypi_resp, dl_resp]

        result = lookup_package("requests", registry="pypi")
        assert isinstance(result, PackageInfo)
        assert result.name == "requests"
        assert result.version == "2.31.0"
        assert result.license == "Apache-2.0"
        assert result.dependencies_count == 3
        assert "http" in result.keywords

    @patch("web_search_mcp.registries.httpx.Client")
    def test_lookup_not_found(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = Exception("404")

        result = lookup_package("nonexistent-pkg-xyzzy", registry="npm")
        assert isinstance(result, ErrorResponse)
        assert "not found" in result.error.lower()

    def test_lookup_empty_name(self):
        result = lookup_package("")
        assert isinstance(result, ErrorResponse)

    def test_lookup_unknown_registry(self):
        result = lookup_package("foo", registry="unknown")  # type: ignore
        assert isinstance(result, ErrorResponse)


class TestSearchPackages:
    """Package keyword search with mocked HTTP."""

    @patch("web_search_mcp.registries.httpx.Client")
    def test_search_npm(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        search_resp = MagicMock()
        search_resp.json.return_value = {
            "objects": [
                {
                    "package": {
                        "name": "react",
                        "version": "18.2.0",
                        "description": "A JavaScript library for building UIs",
                        "date": "2023-06-01T00:00:00Z",
                        "links": {"npm": "https://www.npmjs.com/package/react"},
                        "keywords": ["react", "ui"],
                    },
                    "score": {"detail": {"quality": 0.9}},
                }
            ]
        }
        search_resp.is_success = True
        mock_client.get.return_value = search_resp
        # make a second call for search
        mock_client.get.return_value = search_resp

        results = search_packages("react", registry="npm")
        assert isinstance(results, list)
        assert len(results) >= 1
        assert results[0].name == "react"
        assert results[0].registry == "npm"

    def test_search_empty_query(self):
        result = search_packages("")
        assert isinstance(result, ErrorResponse)


class TestPackageFormatters:
    """Markdown formatting for PackageInfo."""

    def test_format_package_info(self):
        info = PackageInfo(
            name="pytest",
            registry="pypi",
            version="8.0.0",
            description="Testing framework",
            license="MIT",
            downloads="1.5M/week",
            last_updated="30d ago",
            homepage="https://pytest.org",
            repository="https://github.com/pytest-dev/pytest",
            dependencies_count=5,
            keywords=["test", "python"],
        )
        md = format_package_info(info)
        assert "pytest" in md
        assert "8.0.0" in md
        assert "Testing framework" in md
        assert "MIT" in md
        assert "1.5M/week" in md

    def test_format_package_info_minimal(self):
        info = PackageInfo(name="foo", registry="npm", version="1.0.0", description="")
        md = format_package_info(info)
        assert "foo" in md
        assert "1.0.0" in md

    def test_format_package_list_empty(self):
        md = format_package_list([], "query", "npm")
        assert "No packages found" in md

    def test_format_package_list_results(self):
        packages = [
            PackageInfo(name="a", registry="npm", version="1.0.0", description="first"),
            PackageInfo(name="b", registry="npm", version="2.0.0", description="second"),
        ]
        md = format_package_list(packages, "test query", "npm")
        assert "a" in md
        assert "b" in md
        assert "2 packages" in md


# ═══════════════════════════════════════════════════════════
#  errors.py  —  ErrorParser & translate_error
# ═══════════════════════════════════════════════════════════


class TestErrorParser:
    """Error message parsing and language/framework detection."""

    def setup_method(self):
        self.parser = ErrorParser()

    def test_parse_python_traceback(self):
        tb = """Traceback (most recent call last):
  File "/app/main.py", line 23, in <module>
    result = calculate(42, None)
ValueError: cannot unpack non-iterable NoneType object"""
        parsed = self.parser.parse(tb)
        assert parsed.language == "python"
        assert parsed.error_type == "ValueError"
        assert parsed.file_path == "/app/main.py"
        assert parsed.line_number == 23

    def test_parse_javascript_error(self):
        js_error = """TypeError: Cannot read property 'length' of undefined
    at Object.<anonymous> (/app/index.js:45:12)
    at Module._compile (internal/modules/cjs/loader.js:1138:30)"""
        parsed = self.parser.parse(js_error)
        assert parsed.language == "javascript"
        assert parsed.error_type is not None
        assert parsed.file_path == "/app/index.js"
        assert parsed.line_number == 45

    def test_parse_rust_borrow_error(self):
        rust_error = """error[E0502]: cannot borrow `x` as mutable because it is also borrowed as immutable
  --> src/main.rs:34:18
   |
23 |     let y = &x;
   |             -- immutable borrow occurs here
34 |     x.push(4);
   |     ^^^^^^^^ mutable borrow occurs here"""
        parsed = self.parser.parse(rust_error)
        assert parsed.language == "rust"
        assert parsed.error_type == "E0502"
        assert parsed.file_path == "src/main.rs"
        assert parsed.line_number == 34

    def test_parse_django_error(self):
        django_error = """django.core.exceptions.ImproperlyConfigured: Error loading MySQLdb module.
  File "/app/myapp/views.py", line 12, in my_view
    return render(request, 'template.html')"""
        parsed = self.parser.parse(django_error)
        assert parsed.language == "python"
        assert parsed.framework == "django"

    def test_parse_cors_error(self):
        cors_error = "Access to XMLHttpRequest has been blocked by CORS policy"
        parsed = self.parser.parse(cors_error)
        assert parsed.error_type == "CORS Error"

    def test_parse_fetch_error(self):
        fetch_error = "TypeError: Failed to fetch at https://api.example.com/data"
        parsed = self.parser.parse(fetch_error)
        assert "Fetch Error" in (parsed.error_type or "")

    def test_parse_empty_string(self):
        parsed = self.parser.parse("")
        assert parsed.error_type == "Unknown Error"

    def test_parse_go_panic(self):
        go_error = """panic: runtime error: invalid memory address or nil pointer dereference
[signal SIGSEGV: segmentation violation code=0x1 addr=0x0 pc=0x12345]

goroutine 1 [running]:
main.main()
        /app/main.go:42 +0x123"""
        parsed = self.parser.parse(go_error)
        assert parsed.language == "go"

    def test_parse_typescript_with_framework(self):
        ts_error = """TypeError: Cannot read properties of undefined (reading 'map')
    at MyComponent (app/components/List.tsx:56:14)"""
        parsed = self.parser.parse(ts_error, language="typescript")
        assert parsed.language == "typescript"
        assert parsed.file_path == "app/components/List.tsx"

    def test_clean_message_ansi(self):
        cleaned = self.parser._clean_message("\x1b[31merror\x1b[0m: something broke")
        assert cleaned == "error: something broke"
        assert "\x1b" not in cleaned

    def test_clean_message_multi_line(self):
        msg = "line1\n\n\nline2"
        cleaned = self.parser._clean_message(msg)
        assert "\n\n\n" not in cleaned

    def test_extract_key_terms(self):
        terms = self.parser._extract_key_terms(
            "TypeError: 'NoneType' object is not subscriptable",
            "TypeError",
        )
        assert "TypeError" in terms
        assert "NoneType" in terms

    def test_extract_location_no_match(self):
        loc, line = self.parser._extract_location("random text without stack trace")
        assert loc is None
        assert line is None


class TestErrorParserFrameworks:
    """Framework detection edge cases."""

    def setup_method(self):
        self.parser = ErrorParser()

    def test_detect_react(self):
        assert (
            self.parser._detect_framework(
                "Uncaught Error: useEffect received an unexpected argument"
            )
            == "react"
        )

    def test_detect_fastapi(self):
        assert (
            self.parser._detect_framework("fastapi.exceptions.HTTPException: 404 Not Found")
            == "fastapi"
        )

    def test_detect_express(self):
        assert self.parser._detect_framework("app.get('/') returned undefined") == "express"

    def test_no_framework(self):
        assert self.parser._detect_framework("generic error message") is None


# ═══════════════════════════════════════════════════════════
#  Package formatter edge cases
# ═══════════════════════════════════════════════════════════


class TestFormatPackageInfoEdgeCases:
    """Edge cases for package info formatting."""

    def test_no_optional_fields(self):
        info = PackageInfo(name="test", registry="npm", version="1.0.0", description="desc")
        md = format_package_info(info)
        assert "test" in md
        assert "1.0.0" in md
        assert "Dependencies:" not in md  # None, so not shown

    def test_all_fields_none(self):
        info = PackageInfo(name="x", registry="go", version="v0.0.0", description="")
        md = format_package_info(info)
        assert "x" in md

    def test_empty_keywords(self):
        info = PackageInfo(name="pkg", registry="npm", version="1.0.0", description="")
        md = format_package_info(info)
        assert "Keywords:" not in md
