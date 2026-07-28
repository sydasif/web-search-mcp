# Web Search MCP - Optimization Plan

> **Status:** Draft  
> **Created:** 2024  
> **Version:** 1.0  
> **Author:** Vibe Code Agent

---

## 📊 Overview

This document outlines comprehensive optimization suggestions for the **web-search-mcp** repository. The goal is to improve performance, maintainability, security, and observability while preserving the existing architecture and functionality.

**Repository Stats:**
- Total Python code: 3,129 lines
- Modules: 20+ Python files
- Tools: 10+ MCP tools
- Test coverage: Good (end-to-end tests exist)

---

## 🎯 Priority Recommendations Summary

### High Priority (Do First) ⭐⭐⭐

| # | Optimization | Effort | Impact | Risk |
|---|-------------|--------|--------|------|
| 1 | **Add caching layer** | 3h | High | Low |
| 2 | **Improve rate limiter** (async support) | 2h | High | Medium |
| 3 | **Enhance error handling** | 3h | High | Low |
| 4 | **Add input validation** | 2h | High | Low |
| 5 | **Add health checks** | 1h | High | Low |

**Total:** 11 hours | **Expected Impact:** Significant performance, security, and reliability improvements

---

### Medium Priority ⭐⭐

| # | Optimization | Effort | Impact | Risk |
|---|-------------|--------|--------|------|
| 6 | Dependency injection | 4h | High | Medium |
| 7 | Plugin architecture for search providers | 4h | High | Medium |
| 8 | Metrics collection | 2h | High | Low |
| 9 | Configuration validation | 1h | Medium | Low |
| 10 | Type hints & static analysis | 4h | Medium | Low |
| 11 | Test fixtures | 3h | High | Low |
| 12 | Structured logging | 2h | Medium | Low |

**Total:** 21 hours | **Expected Impact:** Improved code quality, testability, and observability

---

### Low Priority ⭐

| # | Optimization | Effort | Impact | Risk |
|---|-------------|--------|--------|------|
| 13 | API documentation standardization | 4h | Medium | Low |
| 14 | ADR documentation | 2h | Medium | Low |
| 15 | Property-based tests | 2h | Medium | Low |
| 16 | Benchmark tests | 1h | Medium | Low |
| 17 | CI/CD workflows | 2h | High | Low |
| 18 | Enhanced SSRF protection | 2h | High | Low |

**Total:** 13 hours | **Expected Impact:** Better documentation, testing, and security

---

## 📋 Implementation Roadmap

### Phase 1: Foundation (Week 1)
**Goal:** Improve core reliability and performance
- [ ] Add caching layer
- [ ] Improve rate limiter (async support)
- [ ] Enhance error handling
- [ ] Add input validation
- [ ] Add health checks

**Estimated Time:** 11 hours

---

### Phase 2: Architecture (Week 2)
**Goal:** Improve code structure and maintainability
- [ ] Dependency injection
- [ ] Plugin architecture for search providers
- [ ] Configuration validation
- [ ] Type hints improvements
- [ ] Test fixtures

**Estimated Time:** 15 hours

---

### Phase 3: Observability (Week 3)
**Goal:** Improve monitoring and debugging
- [ ] Metrics collection
- [ ] Structured logging
- [ ] Enhanced SSRF protection

**Estimated Time:** 6 hours

---

### Phase 4: Quality (Week 4)
**Goal:** Improve code quality and documentation
- [ ] API documentation standardization
- [ ] ADR documentation
- [ ] Property-based tests
- [ ] Benchmark tests
- [ ] CI/CD workflows

**Estimated Time:** 13 hours

---

## 🔧 Detailed Optimizations

### 1. Performance Optimizations

#### A. HTTP Client Management
**Current:** Global `http_client` with no connection pooling or retry logic.

**Recommended:**
- Add connection pooling (`max_keepalive_connections=20`)
- Add retry logic for transient failures (5xx errors)
- Use `httpx.Retry` with exponential backoff

**Files:** `web_search_mcp/_http/client.py`

---

#### B. Rate Limiter Improvements
**Current:** Thread-based sliding window rate limiter.

**Recommended:**
- Add async-compatible version using `asyncio.Lock`
- Use `deque` for efficient removal of old requests
- Support both sync and async contexts

**Files:** `web_search_mcp/_utils/rate_limiter.py`

---

#### C. Caching Layer
**Current:** No caching for repeated queries.

**Recommended:**
- Add `TTLCache` class with configurable TTL (default: 5 minutes)
- Cache search results by query + parameters
- Add cache invalidation methods
- Use decorator pattern for easy integration

**Files to Create:** `web_search_mcp/_utils/cache.py`
**Files to Modify:** All search modules

---

### 2. Code Quality & Maintainability

#### A. Type Hints & Static Analysis
**Current:** Good type coverage but inconsistent.

**Recommended:**
- Enable strict mypy mode in `pyproject.toml`
- Use `@overload` for functions with multiple return types
- Add `typing.Protocol` for interfaces
- Add `py.typed` marker (already configured)

**Files:** `pyproject.toml`, all modules

---

#### B. Error Handling Standardization
**Current:** Inconsistent error handling across modules.

**Recommended:**
- Create exception hierarchy (`SearchError`, `RateLimitError`, etc.)
- Standardize `ErrorResponse` creation
- Add `@handle_errors` decorator for consistent error handling

**Files to Create:** `web_search_mcp/_utils/errors.py`
**Files to Modify:** All modules returning errors

---

#### C. Logging Improvements
**Current:** Basic logging with module-level loggers.

**Recommended:**
- Add structured logging with JSON formatter
- Add request IDs for tracing across modules
- Use `contextvars.ContextVar` for request context
- Configure log levels for noisy libraries (httpx, ddgs)

**Files to Create:** `web_search_mcp/_config/logging.py`
**Files to Modify:** `web_search_mcp/server.py`, all modules

---

### 3. Architecture Improvements

#### A. Dependency Injection
**Current:** Global imports and direct function calls.

**Recommended:**
- Create service layer with clear interfaces
- Use dependency injection for HTTP clients, rate limiters, etc.
- Improve testability by allowing mock implementations

**Files to Create:** `web_search_mcp/_services/__init__.py`
**Files to Modify:** `web_search_mcp/server.py`

---

#### B. Plugin Architecture for Search Providers
**Current:** Hardcoded provider selection in `search_web`.

**Recommended:**
- Create `BaseSearchProvider` abstract base class
- Add `ProviderRegistry` for dynamic provider management
- Support auto-selection with fallback
- Enable custom provider registration

**Files to Create:** `web_search_mcp/search/providers.py`
**Files to Modify:** `web_search_mcp/search/ddg.py`, `web_search_mcp/search/exa.py`, `web_search_mcp/server.py`

---

#### C. Configuration Management
**Current:** Settings split between `settings.py` and `limits.py`.

**Recommended:**
- Consolidate all settings into Pydantic `BaseSettings`
- Add nested configuration classes (`RateLimitConfig`, `DepthLimitConfig`, etc.)
- Add validation for configuration values
- Support environment variable overrides

**Files to Modify:** `web_search_mcp/_config/settings.py`
**Files to Deprecate:** `web_search_mcp/_config/limits.py`

---

### 4. Testing Improvements

#### A. Test Fixtures
**Current:** Tests use direct imports and real network calls.

**Recommended:**
- Add pytest fixtures for mocking HTTP clients
- Add fixtures for common models (SearchRequest, SearchResponse, etc.)
- Add fixtures for mocking external APIs
- Add `integration` marker for tests requiring network access

**Files to Create:** `tests/conftest.py`
**Files to Modify:** All test files

---

#### B. Property-Based Tests
**Current:** No property-based testing.

**Recommended:**
- Add `hypothesis` for property-based testing
- Test input validation with random inputs
- Test edge cases automatically

**Files to Create:** `tests/test_property_based.py`
**Files to Modify:** `pyproject.toml` (add hypothesis dependency)

---

#### C. Benchmark Tests
**Current:** No performance benchmarks.

**Recommended:**
- Add `pytest-benchmark` for performance tracking
- Benchmark all major tools (search_web, fetch_page, etc.)
- Track performance over time

**Files to Create:** `tests/benchmark.py`
**Files to Modify:** `pyproject.toml` (add pytest-benchmark dependency)

---

### 5. Security Improvements

#### A. Input Validation
**Current:** Basic validation in some places.

**Recommended:**
- Create centralized validation utilities
- Validate all user inputs (queries, URLs, parameters)
- Sanitize inputs to prevent injection attacks
- Add length limits and character restrictions

**Files to Create:** `web_search_mcp/_utils/validation.py`
**Files to Modify:** `web_search_mcp/server.py`, all modules accepting user input

---

#### B. Enhanced SSRF Protection
**Current:** Basic IP validation in `validate_url`.

**Recommended:**
- Add DNS resolution to check for private IPs
- Cache DNS lookups to avoid repeated resolutions
- Block additional IP ranges (carrier-grade NAT, reserved, etc.)
- Add configurable allowlist/blocklist

**Files to Modify:** `web_search_mcp/_http/client.py`

---

### 6. Operational Improvements

#### A. Health Checks
**Current:** No health check endpoint.

**Recommended:**
- Add `health_check` tool returning server status
- Check all components (DDG, Exa, HTTP client)
- Include version, uptime, configuration summary
- Return structured status (healthy/degraded/unhealthy)

**Files to Modify:** `web_search_mcp/server.py`

---

#### B. Metrics Collection
**Current:** No metrics collection.

**Recommended:**
- Add in-memory metrics collector
- Track request counts, latencies, error rates
- Support Prometheus integration (optional)
- Add `@track_metric` decorator for easy instrumentation

**Files to Create:** `web_search_mcp/_utils/metrics.py`
**Files to Modify:** `web_search_mcp/server.py`, all search/fetch functions

---

#### C. Configuration Validation
**Current:** No validation of environment variables.

**Recommended:**
- Validate configuration at startup
- Check required dependencies
- Validate API key formats
- Provide clear error messages for configuration issues

**Files to Modify:** `web_search_mcp/_config/settings.py`, `web_search_mcp/server.py`

---

### 7. Documentation Improvements

#### A. API Documentation Standardization
**Current:** Docstrings exist but inconsistent format.

**Recommended:**
- Adopt Google-style docstrings consistently
- Add type information to all docstrings
- Include examples in all public functions
- Document error handling and edge cases

**Files to Modify:** `web_search_mcp/server.py`, all public modules

---

#### B. Architecture Decision Records (ADRs)
**Current:** No ADRs for key decisions.

**Recommended:**
- Create `docs/adr/` directory
- Add ADR template
- Document key architectural decisions:
  - Why FastMCP over base MCP
  - Why DuckDuckGo as primary search
  - Rate limiting strategy
  - Error handling approach
  - SSRF protection strategy

**Files to Create:** `docs/adr/0001-use-fastmcp-over-mcp.md`, etc.

---

### 8. CI/CD Improvements

**Current:** No CI/CD workflows.

**Recommended:**
- Add GitHub Actions workflows for:
  - Linting (ruff, mypy)
  - Unit testing
  - Integration testing (with secrets)
  - Benchmarking
  - Release automation
- Add code coverage reporting
- Add automated releases to PyPI

**Files to Create:**
- `.github/workflows/ci.yml`
- `.github/workflows/benchmark.yml`
- `.github/workflows/release.yml`

---

## 📊 Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Search latency (p95) | ~500ms | <300ms | Benchmark tests |
| Error rate | ~1% | <0.5% | Metrics collection |
| Test coverage | ~80% | >90% | pytest-cov |
| Code quality (ruff) | Good | Excellent | ruff check |
| Type safety | Good | Excellent | mypy strict |
| Startup time | ~1s | <500ms | Manual testing |

---

## 🏆 Conclusion

This optimization plan provides a comprehensive roadmap for improving the **web-search-mcp** server. By implementing these optimizations in phases, we can achieve:

1. **Better performance** - Faster searches, caching, reduced API calls
2. **Enhanced reliability** - Better error handling, input validation, rate limiting
3. **Increased maintainability** - Cleaner architecture, better type hints, dependency injection
4. **Improved observability** - Metrics, health checks, structured logging
5. **Stronger security** - Enhanced SSRF protection, input validation

**Total Estimated Effort:** ~48 hours across 4 phases

---

## 📚 References

- [README.md](../README.md) - Main project documentation
- [CLAUDE.md](../CLAUDE.md) - Development guidelines
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [MCP Specification](https://github.com/modelcontextprotocol/specification)

---

*This document is a living document and should be updated as optimizations are implemented and new requirements emerge.*
