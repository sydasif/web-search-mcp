# Web Search MCP - Optimization Documentation

This directory contains detailed documentation for the optimization plan outlined in [OPTIMIZATION_PLAN.md](../OPTIMIZATION_PLAN.md).

---

## 📚 Documentation Structure

| Document | Description | Priority |
|----------|-------------|----------|
| [OPTIMIZATION_PLAN.md](../OPTIMIZATION_PLAN.md) | Main optimization plan with summary and roadmap | ⭐⭐⭐ |
| [01-performance.md](./01-performance.md) | Performance optimizations (caching, rate limiting, HTTP, SSRF) | ⭐⭐⭐ |
| [02-code-quality.md](./02-code-quality.md) | Code quality improvements (types, errors, logging, DI, plugins) | ⭐⭐ |
| [03-operational.md](./03-operational.md) | Operational improvements (health checks, metrics, tests, CI/CD) | ⭐⭐ |

---

## 🎯 Quick Start

### High Priority (Start Here)

1. **Add caching layer** - Reduces redundant API calls
   - File: `web_search_mcp/_utils/cache.py` (new)
   - Effort: 3 hours
   - Impact: High

2. **Improve rate limiter** - Add async support
   - File: `web_search_mcp/_utils/rate_limiter.py`
   - Effort: 2 hours
   - Impact: High

3. **Enhance error handling** - Standardize error responses
   - File: `web_search_mcp/_utils/errors.py` (new)
   - Effort: 3 hours
   - Impact: High

4. **Add input validation** - Prevent injection attacks
   - File: `web_search_mcp/_utils/validation.py` (new)
   - Effort: 2 hours
   - Impact: High

5. **Add health checks** - Monitor server status
   - File: `web_search_mcp/server.py` (modify)
   - Effort: 1 hour
   - Impact: High

**Total for Phase 1:** 11 hours | **Expected Outcome:** More reliable, secure, and performant server

---

## 📋 Implementation Checklist

### Phase 1: Foundation (Week 1)
- [ ] Add caching layer (`_utils/cache.py`)
- [ ] Improve rate limiter (`_utils/rate_limiter.py`)
- [ ] Enhance error handling (`_utils/errors.py`)
- [ ] Add input validation (`_utils/validation.py`)
- [ ] Add health checks (`server.py`)
- [ ] Enhanced SSRF protection (`_http/client.py`)

### Phase 2: Architecture (Week 2)
- [ ] Dependency injection (`_services/__init__.py`)
- [ ] Plugin architecture for search providers (`search/providers.py`)
- [ ] Configuration validation (`_config/settings.py`)
- [ ] Type hints improvements (all modules)
- [ ] Test fixtures (`tests/conftest.py`)

### Phase 3: Observability (Week 3)
- [ ] Metrics collection (`_utils/metrics.py`)
- [ ] Structured logging (`_config/logging.py`)

### Phase 4: Quality (Week 4)
- [ ] API documentation standardization (all public functions)
- [ ] ADR documentation (`docs/adr/`)
- [ ] Property-based tests (`tests/test_property_based.py`)
- [ ] Benchmark tests (`tests/benchmark.py`)
- [ ] CI/CD workflows (`.github/workflows/`)

---

## 🔧 Code Examples

### Caching Example

```python
# In web_search_mcp/search/ddg.py
from .._utils.cache import cached, search_cache

@cached(search_cache, key_func=lambda req: f"ddg:{req.query}:{req.search_type}")
def ddg_search(request: SearchRequest) -> SearchResponse | ErrorResponse:
    # ... existing implementation
```

### Error Handling Example

```python
# In web_search_mcp/server.py
from .._utils.errors import handle_errors, SearchError

@mcp.tool(...)
@handle_errors(context="search_web")
def search_web(...) -> ...:
    # ... implementation
    if not query:
        raise SearchError("Query cannot be empty", error_code="INVALID_INPUT")
```

### Health Check Example

```python
# In web_search_mcp/server.py
@mcp.tool(name="health_check")
def health_check() -> dict:
    return {
        "status": "healthy",
        "version": "0.5.0",
        "components": {
            "ddg": {"status": "healthy", "latency_ms": 45.2},
            "exa": {"status": "not_configured"},
        }
    }
```

---

## 📊 Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Search latency (p95) | ~500ms | <300ms | Benchmark tests |
| Error rate | ~1% | <0.5% | Metrics collection |
| Test coverage | ~80% | >90% | pytest-cov |
| Code quality (ruff) | Good | Excellent | ruff check |
| Type safety | Good | Excellent | mypy strict |

---

## 🏆 Contributing

If you implement any of these optimizations, please:

1. Create a feature branch: `git checkout -b feat/optimization-<name>`
2. Add tests for the new functionality
3. Update documentation as needed
4. Submit a pull request with a clear description

---

## 📚 Additional Resources

- [Main README](../../README.md) - Project overview
- [CLAUDE.md](../../CLAUDE.md) - Development guidelines
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [MCP Specification](https://github.com/modelcontextprotocol/specification)
