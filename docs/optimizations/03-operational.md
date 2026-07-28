# Operational & Testing Optimizations

## Overview

This document details the operational and testing optimizations for web-search-mcp.

---

## 1. Health Checks

### Current State
No health check endpoint. No way to monitor server status.

### Issues
- Hard to detect if server is running
- No visibility into component health
- No metrics for monitoring

### Recommended Implementation

```python
# In web_search_mcp/server.py (add at the end, before main())

import time
from typing import Any

_SERVER_START_TIME = time.time()

@mcp.tool(
    name="health_check",
    annotations={
        "title": "Health check endpoint",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def health_check() -> dict[str, Any]:
    """Check the health status of the server and its dependencies.

    Returns a comprehensive health status including:
    - Overall server status
    - Version information
    - Health of individual components (DDG, Exa, HTTP client)
    - Configuration summary

    Returns:
        dict: Health status with the following structure:
            {
                "status": "healthy" | "degraded" | "unhealthy",
                "version": str,
                "uptime_seconds": float,
                "components": {
                    "ddg": {"status": str, "latency_ms": float | None, "error": str | None},
                    "exa": {"status": str, "latency_ms": float | None, "error": str | None},
                    "http_client": {"status": str, "error": str | None},
                },
                "configuration": dict,
            }
    """
    from ._config import settings
    from .search.ddg import ddg_search
    from .search.exa import exa_search
    from ._models.requests import SearchRequest
    
    status: dict[str, Any] = {
        "status": "healthy",
        "version": "0.5.0",
        "uptime_seconds": time.time() - _SERVER_START_TIME,
        "components": {},
        "configuration": {
            "rate_limits": {
                "search": settings.rate_limits.search,
                "fetch": settings.rate_limits.fetch,
            },
            "depth_limits": settings.depth_limits.model_dump() if hasattr(settings.depth_limits, 'model_dump') else str(settings.depth_limits),
            "providers": ["ddg", "exa"],
        },
    }
    
    # Check DDG
    try:
        ddg_start = time.time()
        req = SearchRequest(query="health check", max_results=1)
        result = ddg_search(req)
        ddg_latency = (time.time() - ddg_start) * 1000
        
        if isinstance(result, SearchResponse):
            status["components"]["ddg"] = {
                "status": "healthy",
                "latency_ms": round(ddg_latency, 2),
                "error": None,
            }
        else:
            status["components"]["ddg"] = {
                "status": "degraded",
                "latency_ms": round(ddg_latency, 2),
                "error": getattr(result, "error", "Unknown error"),
            }
            status["status"] = "degraded"
    except Exception as e:
        status["components"]["ddg"] = {
            "status": "unhealthy",
            "latency_ms": None,
            "error": str(e),
        }
        status["status"] = "unhealthy"
    
    # Check Exa (only if API key is configured)
    if hasattr(settings, 'exa_api_key') and settings.exa_api_key:
        try:
            exa_start = time.time()
            result = exa_search(query="health check", max_results=1)
            exa_latency = (time.time() - exa_start) * 1000
            
            if isinstance(result, SearchResponse):
                status["components"]["exa"] = {
                    "status": "healthy",
                    "latency_ms": round(exa_latency, 2),
                    "error": None,
                }
            else:
                status["components"]["exa"] = {
                    "status": "degraded",
                    "latency_ms": round(exa_latency, 2),
                    "error": getattr(result, "error", "Unknown error"),
                }
                if status["status"] != "unhealthy":
                    status["status"] = "degraded"
        except Exception as e:
            status["components"]["exa"] = {
                "status": "unhealthy",
                "latency_ms": None,
                "error": str(e),
            }
            status["status"] = "unhealthy"
    else:
        status["components"]["exa"] = {
            "status": "not_configured",
            "latency_ms": None,
            "error": "EXA_API_KEY not set",
        }
    
    # Check HTTP client
    try:
        from ._http import http_client
        response = http_client.get("https://example.com", timeout=5)
        response.raise_for_status()
        status["components"]["http_client"] = {
            "status": "healthy",
            "error": None,
        }
    except Exception as e:
        status["components"]["http_client"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        status["status"] = "unhealthy"
    
    return status
```

**Files to Modify:**
- `web_search_mcp/server.py`

**Effort:** 1 hour  
**Impact:** High  
**Risk:** Low

---

## 2. Metrics Collection

### Current State
No metrics collection. No way to monitor performance.

### Issues
- No visibility into request rates
- No latency tracking
- No error rate monitoring
- Hard to detect performance regressions

### Recommended Implementation

```python
# New file: web_search_mcp/_utils/metrics.py
"""Metrics collection for monitoring and observability."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


class MetricsCollector:
    """Collects and tracks various metrics."""
    
    def __init__(self):
        self._counters: dict[str, int] = defaultdict(int)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._gauges: dict[str, float] = defaultdict(float)
        self._start_time = time.time()
    
    def increment(self, name: str, value: int = 1) -> None:
        """Increment a counter metric."""
        self._counters[name] += value
    
    def observe(self, name: str, value: float) -> None:
        """Observe a value for a histogram metric."""
        self._histograms[name].append(value)
        if len(self._histograms[name]) > 1000:
            self._histograms[name] = self._histograms[name][-1000:]
    
    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge metric to a specific value."""
        self._gauges[name] = value
    
    def get_metrics(self) -> dict[str, Any]:
        """Get all collected metrics."""
        return {
            "counters": dict(self._counters),
            "histograms": {
                name: {
                    "count": len(values),
                    "sum": sum(values),
                    "avg": sum(values) / len(values) if values else 0,
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                }
                for name, values in self._histograms.items()
            },
            "gauges": dict(self._gauges),
            "uptime_seconds": time.time() - self._start_time,
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._histograms.clear()
        self._gauges.clear()


# Global metrics collector
metrics = MetricsCollector()

# Metric names
METRIC_SEARCH_REQUESTS = "search_requests_total"
METRIC_SEARCH_ERRORS = "search_errors_total"
METRIC_SEARCH_LATENCY = "search_latency_seconds"
METRIC_FETCH_REQUESTS = "fetch_requests_total"
METRIC_FETCH_ERRORS = "fetch_errors_total"
METRIC_FETCH_LATENCY = "fetch_latency_seconds"
METRIC_ACTIVE_REQUESTS = "active_requests"


def track_metric(metric_name: str, tags: dict[str, str] | None = None):
    """Decorator to track a metric for a function."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            tags_str = ":".join(f"{k}={v}" for k, v in (tags or {}).items())
            full_metric = f"{metric_name}:{tags_str}" if tags_str else metric_name
            
            try:
                metrics.increment(f"{full_metric}_started")
                metrics.set_gauge(METRIC_ACTIVE_REQUESTS, 
                                  metrics._gauges.get(METRIC_ACTIVE_REQUESTS, 0) + 1)
                
                result = func(*args, **kwargs)
                
                latency = time.time() - start_time
                metrics.observe(f"{full_metric}_latency", latency)
                metrics.increment(f"{full_metric}_success")
                
                return result
            except Exception as e:
                metrics.increment(f"{full_metric}_errors")
                raise
            finally:
                metrics.set_gauge(METRIC_ACTIVE_REQUESTS, 
                                  max(0, metrics._gauges.get(METRIC_ACTIVE_REQUESTS, 0) - 1))
        
        return wrapper
    return decorator


@contextmanager
def track_latency(metric_name: str, tags: dict[str, str] | None = None):
    """Context manager to track latency for a block of code."""
    start_time = time.time()
    tags_str = ":".join(f"{k}={v}" for k, v in (tags or {}).items())
    full_metric = f"{metric_name}:{tags_str}" if tags_str else metric_name
    
    try:
        yield
    finally:
        latency = time.time() - start_time
        metrics.observe(full_metric, latency)


# Prometheus integration (optional)
try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest
    
    PROM_SEARCH_REQUESTS = Counter(
        'web_search_mcp_search_requests_total',
        'Total search requests',
        ['provider', 'search_type', 'status']
    )
    PROM_SEARCH_LATENCY = Histogram(
        'web_search_mcp_search_latency_seconds',
        'Search request latency',
        ['provider'],
        buckets=[0.1, 0.5, 1, 2, 5, 10]
    )
    PROM_SEARCH_ERRORS = Counter(
        'web_search_mcp_search_errors_total',
        'Total search errors',
        ['provider', 'error_type']
    )
    PROM_ACTIVE_REQUESTS = Gauge(
        'web_search_mcp_active_requests',
        'Number of active requests'
    )
    
    def prometheus_metrics_handler() -> str:
        """Get Prometheus metrics in text format."""
        return generate_latest()
    
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


def get_metrics() -> dict[str, Any]:
    """Get all collected metrics."""
    return metrics.get_metrics()
```

**Files to Create:**
- `web_search_mcp/_utils/metrics.py`

**Files to Modify:**
- `web_search_mcp/server.py` (add metrics endpoint)
- All search/fetch functions (add metrics tracking)

**Effort:** 2 hours  
**Impact:** High  
**Risk:** Low

---

## 3. Configuration Validation

### Current State
No validation of environment variables. Settings loaded but not validated.

### Issues
- Invalid configurations may cause runtime errors
- No early feedback on configuration issues
- Hard to debug configuration problems

### Recommended Implementation

```python
# In web_search_mcp/_config/settings.py (add validation)

def validate_configuration() -> list[str]:
    """Validate configuration at startup.
    
    Returns:
        List of error messages. Empty list if configuration is valid.
    """
    from . import settings
    import logging
    
    logger = logging.getLogger(__name__)
    errors = []
    
    # Check required dependencies
    try:
        import ddgs
    except ImportError:
        errors.append("ddgs package not installed - DuckDuckGo search will not work")
    
    # Check optional dependencies with warnings
    try:
        import exa_py
    except ImportError:
        logger.warning("exa_py not installed - Exa search will be unavailable")
    
    try:
        import trafilatura
    except ImportError:
        logger.warning("trafilatura not installed - page extraction may be limited")
    
    # Validate API keys if set
    if hasattr(settings, 'exa_api_key') and settings.exa_api_key:
        if len(settings.exa_api_key) < 20:
            errors.append("EXA_API_KEY appears invalid (too short)")
    
    if hasattr(settings, 'github_token') and settings.github_token:
        if len(settings.github_token) < 40:
            errors.append("GITHUB_TOKEN appears invalid (too short)")
    
    # Validate rate limits
    if hasattr(settings, 'rate_limits'):
        if settings.rate_limits.search <= 0:
            errors.append("rate_limits.search must be positive")
        
        if settings.rate_limits.fetch <= 0:
            errors.append("rate_limits.fetch must be positive")
    
    return errors


def check_dependencies() -> dict[str, bool]:
    """Check which optional dependencies are available.
    
    Returns:
        Dictionary mapping dependency names to availability.
    """
    dependencies = {
        "ddgs": True,
        "exa_py": False,
        "trafilatura": False,
        "httpx": True,
        "pydantic": True,
        "fastmcp": True,
    }
    
    try:
        import exa_py
        dependencies["exa_py"] = True
    except ImportError:
        pass
    
    try:
        import trafilatura
        dependencies["trafilatura"] = True
    except ImportError:
        pass
    
    return dependencies
```

**Files to Modify:**
- `web_search_mcp/_config/settings.py`
- `web_search_mcp/server.py` (add startup validation)

**Effort:** 1 hour  
**Impact:** Medium  
**Risk:** Low

---

## 4. Test Fixtures

### Current State
Tests use direct imports and real network calls. No standardized fixtures.

### Issues
- Tests are slow (real API calls)
- Hard to mock dependencies
- No isolation between tests
- No way to skip integration tests

### Recommended Implementation

```python
# New file: tests/conftest.py
"""Pytest fixtures for web-search-mcp."""

import pytest
from unittest.mock import MagicMock, patch
import httpx
from web_search_mcp._models import (
    SearchRequest,
    SearchResponse,
    SearchResult,
    PageResponse,
    ErrorResponse,
)


# Fixtures for models
@pytest.fixture
def search_request():
    """Create a sample SearchRequest."""
    return SearchRequest(
        query="Python programming",
        max_results=5,
        search_type="text",
    )


@pytest.fixture
def search_response():
    """Create a sample SearchResponse."""
    return SearchResponse(
        query="Python programming",
        results=[
            SearchResult(
                title="Python Documentation",
                url="https://docs.python.org/3/",
                body="Official Python documentation",
                href="https://docs.python.org/3/",
            ),
        ],
        total_results=1,
        search_type="text",
    )


@pytest.fixture
def page_response():
    """Create a sample PageResponse."""
    return PageResponse(
        url="https://example.com",
        content="Example content",
        length=17,
        title="Example Domain",
        metadata={},
    )


@pytest.fixture
def error_response():
    """Create a sample ErrorResponse."""
    return ErrorResponse(
        error="Test error",
        details={"code": "TEST_ERROR"},
    )


# Fixtures for mocking
@pytest.fixture
def mock_http_client():
    """Mock httpx client."""
    mock = MagicMock(spec=httpx.Client)
    mock.get = MagicMock()
    mock.get.return_value.raise_for_status = MagicMock()
    mock.get.return_value.text = "<html><body>Test</body></html>"
    mock.get.return_value.status_code = 200
    
    with patch('web_search_mcp._http.http_client', mock):
        yield mock


@pytest.fixture
def mock_ddg_search():
    """Mock DDG search function."""
    def mock_search(request: SearchRequest) -> SearchResponse:
        return SearchResponse(
            query=request.query,
            results=[
                SearchResult(
                    title=f"Result for {request.query}",
                    url="https://example.com",
                    body="Test result",
                    href="https://example.com",
                )
            ],
            total_results=1,
            search_type=request.search_type,
        )
    
    with patch('web_search_mcp.search.ddg.ddg_search', mock_search):
        yield mock_search


# Fixtures for integration tests
@pytest.fixture(scope="session")
def integration_tests_enabled():
    """Check if integration tests should run."""
    import os
    return os.getenv("RUN_INTEGRATION_TESTS", "false").lower() == "true"


# Custom markers
@pytest.fixture(autouse=True)
def skip_integration_if_disabled(request, integration_tests_enabled):
    """Skip integration tests if RUN_INTEGRATION_TESTS is not set."""
    if "integration" in request.keywords:
        if not integration_tests_enabled:
            pytest.skip("Integration tests disabled - set RUN_INTEGRATION_TESTS=true")


@pytest.fixture(autouse=True)
def skip_slow_if_disabled(request):
    """Skip slow tests if RUN_SLOW_TESTS is not set."""
    import os
    if "slow" in request.keywords:
        if os.getenv("RUN_SLOW_TESTS", "false").lower() != "true":
            pytest.skip("Slow tests disabled - set RUN_SLOW_TESTS=true")
```

**Files to Create:**
- `tests/conftest.py`

**Files to Modify:**
- All test files to use fixtures

**Effort:** 3 hours  
**Impact:** High  
**Risk:** Low

---

## 5. Benchmark Tests

### Current State
No performance benchmarks. No way to track performance over time.

### Issues
- Hard to detect performance regressions
- No baseline measurements
- No automated performance testing

### Recommended Implementation

```python
# New file: tests/benchmark.py
"""Performance benchmarks for web-search-mcp."""

import pytest
from web_search_mcp._models.requests import SearchRequest


class TestSearchBenchmarks:
    """Benchmark tests for search functionality."""
    
    @pytest.mark.benchmark
    @pytest.mark.integration
    def test_ddg_search_benchmark(self, benchmark):
        """Benchmark DuckDuckGo search performance."""
        from web_search_mcp.search.ddg import ddg_search
        
        req = SearchRequest(query="Python programming", max_results=5)
        
        result = benchmark(ddg_search, req)
        assert isinstance(result, SearchResponse)
    
    @pytest.mark.benchmark
    @pytest.mark.integration
    def test_fetch_page_benchmark(self, benchmark):
        """Benchmark page fetch performance."""
        from web_search_mcp.search.ddg import fetch_page
        
        result = benchmark(fetch_page, "https://example.com", max_length=1000)
        assert isinstance(result, PageResponse)


class TestRedditBenchmarks:
    """Benchmark tests for Reddit functionality."""
    
    @pytest.mark.benchmark
    @pytest.mark.integration
    def test_reddit_search_benchmark(self, benchmark):
        """Benchmark Reddit search performance."""
        from web_search_mcp.social.reddit import reddit_search_tool
        
        result = benchmark(
            reddit_search_tool,
            query="Python programming",
            max_results=5,
            depth="quick",
            response_format="json"
        )
        assert result is not None
```

**Files to Create:**
- `tests/benchmark.py`

**Files to Modify:**
- `pyproject.toml` (add pytest-benchmark dependency)

**Effort:** 1 hour  
**Impact:** Medium  
**Risk:** Low

---

## 6. CI/CD Workflows

### Current State
No CI/CD workflows defined. Manual testing and deployment.

### Issues
- No automated testing
- No automated releases
- No code quality checks in CI
- No performance tracking

### Recommended Implementation

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install uv
        run: pip install uv
      
      - name: Install dependencies
        run: uv sync --all-extras
      
      - name: Run ruff
        run: uv run ruff check .
      
      - name: Run mypy
        run: uv run mypy .

  test:
    name: Test
    needs: lint
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install uv
        run: pip install uv
      
      - name: Install dependencies
        run: uv sync --all-extras
      
      - name: Run unit tests
        run: uv run pytest tests/ -m "not integration" --cov=web_search_mcp --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          fail_ci_if_error: false

  integration-test:
    name: Integration Tests
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name != 'schedule'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install uv
        run: pip install uv
      
      - name: Install dependencies
        run: uv sync --all-extras
      
      - name: Run integration tests
        env:
          RUN_INTEGRATION_TESTS: "true"
          EXA_API_KEY: ${{ secrets.EXA_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: uv run pytest tests/ -m "integration" -v
```

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags: ['v*']

jobs:
  release:
    name: Release
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install uv
        run: pip install uv
      
      - name: Build package
        run: uv build
      
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_API_TOKEN }}
      
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          generate_release_notes: true
```

**Files to Create:**
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`

**Effort:** 2 hours  
**Impact:** High  
**Risk:** Low
