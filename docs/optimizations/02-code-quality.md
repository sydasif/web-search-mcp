# Code Quality & Maintainability Optimizations

## Overview

This document details the code quality and maintainability optimizations for web-search-mcp.

---

## 1. Type Hints & Static Analysis

### Current State
Good type coverage but some areas need improvement. Generic types could be more specific.

### Issues
- Some functions lack return type annotations
- Union types could be more precise
- No strict mypy configuration
- No `typing.Protocol` usage for interfaces

### Recommended Implementation

#### A. Enhanced mypy Configuration

```toml
# In pyproject.toml - add/update [tool.mypy] section
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
warn_redundant_casts = true
warn_unused_configs = true
```

#### B. Use Overloads for Better Type Precision

```python
# In web_search_mcp/search/ddg.py
from typing import overload

@overload
def format_search_results_markdown(results: SearchResponse) -> str: ...

@overload
def format_search_results_markdown(results: ErrorResponse) -> str: ...

def format_search_results_markdown(results: SearchResponse | ErrorResponse) -> str:
    # ... existing implementation
```

#### C. Add Protocol for Search Providers

```python
# In web_search_mcp/search/__init__.py
from typing import Protocol, runtime_checkable
from .._models import SearchRequest, SearchResponse, ErrorResponse

@runtime_checkable
class SearchProvider(Protocol):
    """Protocol defining the interface for search providers."""
    
    def search(self, request: SearchRequest) -> SearchResponse | ErrorResponse:
        """Execute a search request."""
        ...
    
    def name(self) -> str:
        """Return the provider name."""
        ...
```

**Files to Modify:**
- `pyproject.toml` (mypy config)
- `web_search_mcp/search/ddg.py`
- `web_search_mcp/search/exa.py`
- `web_search_mcp/search/__init__.py`

**Effort:** 4 hours  
**Impact:** Medium  
**Risk:** Low

---

## 2. Error Handling Standardization

### Current State
Inconsistent error handling across modules. Some errors returned as strings, others as ErrorResponse.

### Issues
- No standardized error types
- Error messages vary in format
- No error context propagation
- Hard to handle errors consistently

### Recommended Implementation

```python
# New file: web_search_mcp/_utils/errors.py
"""Standardized error handling utilities."""

from typing import TypeVar, Any, Callable
from functools import wraps
from .._models import ErrorResponse

T = TypeVar('T')

class SearchError(Exception):
    """Base exception for search-related errors."""
    
    def __init__(self, message: str, details: dict[str, Any] | None = None, 
                 error_code: str = "SEARCH_ERROR"):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.error_code = error_code

class RateLimitError(SearchError):
    """Rate limit exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded", 
                 retry_after: int | None = None):
        super().__init__(message, error_code="RATE_LIMIT")
        self.retry_after = retry_after

class InvalidInputError(SearchError):
    """Invalid input provided."""
    
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message, error_code="INVALID_INPUT")
        self.field = field

class NetworkError(SearchError):
    """Network-related error."""
    
    def __init__(self, message: str, status_code: int | None = None, 
                 url: str | None = None):
        super().__init__(message, error_code="NETWORK_ERROR")
        self.status_code = status_code
        self.url = url

class AuthenticationError(SearchError):
    """Authentication failed."""
    
    def __init__(self, message: str = "Authentication required", 
                 provider: str | None = None):
        super().__init__(message, error_code="AUTHENTICATION_ERROR")
        self.provider = provider

class ProviderError(SearchError):
    """Provider-specific error."""
    
    def __init__(self, message: str, provider: str, 
                 details: dict[str, Any] | None = None):
        super().__init__(message, details=details, error_code="PROVIDER_ERROR")
        self.provider = provider

def format_error_message(error: Exception) -> str:
    """Format an exception into a user-friendly message."""
    if isinstance(error, SearchError):
        return f"[{error.error_code}] {error.message}"
    return str(error)

def create_error_response(error: Exception, context: str | None = None) -> ErrorResponse:
    """Create a standardized ErrorResponse from an exception."""
    message = format_error_message(error)
    if context:
        message = f"{context}: {message}"
    
    details = {}
    if isinstance(error, SearchError):
        details = error.details.copy()
        if error.error_code:
            details["error_code"] = error.error_code
    
    return ErrorResponse(error=message, details=details)

def handle_errors(func: Callable[..., T], context: str | None = None) -> Callable[..., T | ErrorResponse]:
    """Decorator to handle exceptions and return ErrorResponse."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return create_error_response(e, context)
    return wrapper
```

**Files to Create:**
- `web_search_mcp/_utils/errors.py`

**Files to Update:**
- All files that currently use `format_error` or return errors

**Effort:** 3 hours  
**Impact:** High  
**Risk:** Low

---

## 3. Logging Improvements

### Current State
Basic logging with module-level loggers. No structured logging or request IDs.

### Issues
- Hard to trace requests across modules
- No correlation IDs
- Log format not machine-parseable
- Noisy library logs not controlled

### Recommended Implementation

```python
# New file: web_search_mcp/_config/logging.py
"""Logging configuration for web-search-mcp."""

import logging
import sys
from contextvars import ContextVar
import uuid

# Context variable for request ID
request_id_var: ContextVar[str] = ContextVar('request_id', default='')

class RequestIdFilter(logging.Filter):
    """Add request_id to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or 'no-request-id'
        return True

def get_request_id() -> str:
    """Get or create request ID for current context."""
    if not request_id_var.get():
        request_id_var.set(str(uuid.uuid4())[:8])
    return request_id_var.get()

def set_request_id(request_id: str | None = None) -> str:
    """Set request ID for current context."""
    if request_id:
        request_id_var.set(request_id)
    else:
        request_id_var.set(str(uuid.uuid4())[:8])
    return request_id_var.get()

def clear_request_id() -> None:
    """Clear request ID from current context."""
    request_id_var.set('')

def configure_logging(
    level: int = logging.INFO,
    json_format: bool = False
) -> None:
    """Configure logging for the application."""
    # Create formatter
    if json_format:
        try:
            from pythonjsonlogger import jsonlogger
            
            class CustomJsonFormatter(jsonlogger.JsonFormatter):
                def add_fields(self, log_record: dict, record: logging.LogRecord, 
                              message_dict: dict) -> None:
                    super().add_fields(log_record, record, message_dict)
                    log_record['request_id'] = getattr(record, 'request_id', '')
                    log_record['logger_name'] = record.name
                    log_record['level'] = record.levelname
            
            formatter = CustomJsonFormatter('%(asctime)s %(levelname)s %(name)s %(message)s')
        except ImportError:
            json_format = False
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s [%(request_id)s] %(message)s'
            )
    
    if not json_format:
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s [%(request_id)s] %(message)s'
        )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(RequestIdFilter())
    root_logger.addHandler(console_handler)
    
    # Set levels for noisy libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('ddgs').setLevel(logging.WARNING)
    logging.getLogger('trafilatura').setLevel(logging.WARNING)

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)
```

**Files to Create:**
- `web_search_mcp/_config/logging.py`

**Files to Modify:**
- `web_search_mcp/server.py` (update logging configuration)
- All files that use `logging.getLogger`

**Effort:** 2 hours  
**Impact:** Medium  
**Risk:** Low

---

## 4. Dependency Injection

### Current State
Global imports and direct function calls. Tight coupling between modules.

### Issues
- Hard to test in isolation
- Difficult to mock dependencies
- Global state can cause issues
- No clear separation of concerns

### Recommended Implementation

```python
# New file: web_search_mcp/_services/__init__.py
"""Service layer with dependency injection."""

from typing import Protocol
from .._models import SearchRequest, SearchResponse, ErrorResponse, PageResponse

class SearchService(Protocol):
    """Interface for search services."""
    
    def search(self, request: SearchRequest) -> SearchResponse | ErrorResponse:
        """Execute a search."""
        ...

class FetchService(Protocol):
    """Interface for fetch services."""
    
    def fetch(self, url: str, **kwargs) -> PageResponse | ErrorResponse:
        """Fetch a page."""
        ...

class DDGSearchService:
    """DuckDuckGo search service implementation."""
    
    def __init__(self, rate_limiter=None):
        self.rate_limiter = rate_limiter
    
    def search(self, request: SearchRequest) -> SearchResponse | ErrorResponse:
        from ..search.ddg import ddg_search
        if self.rate_limiter:
            self.rate_limiter.acquire()
        return ddg_search(request)

class ExaSearchService:
    """Exa search service implementation."""
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key
    
    def search(self, request: SearchRequest) -> SearchResponse | ErrorResponse:
        from ..search.exa import exa_search
        return exa_search(
            query=request.query,
            max_results=request.max_results,
            search_type=request.search_type,
            time_range=request.time_range,
            region=request.region,
        )

class SearchRegistry:
    """Registry for search providers."""
    
    def __init__(self):
        self._providers: dict[str, SearchService] = {}
    
    def register(self, name: str, service: SearchService) -> None:
        self._providers[name] = service
    
    def get(self, name: str) -> SearchService | None:
        return self._providers.get(name)
    
    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

# Global registry instance
search_registry = SearchRegistry()

# Initialize with default providers
def initialize_services() -> None:
    from .._utils.rate_limiter import RateLimiter
    from .._config.settings import settings
    
    search_rate_limiter = RateLimiter(requests_per_minute=settings.rate_limits.search)
    
    search_registry.register("ddg", DDGSearchService(rate_limiter=search_rate_limiter))
    search_registry.register("exa", ExaSearchService(api_key=settings.exa_api_key))
```

**Files to Create:**
- `web_search_mcp/_services/__init__.py`

**Files to Modify:**
- `web_search_mcp/server.py` (use dependency injection)

**Effort:** 4 hours  
**Impact:** High  
**Risk:** Medium

---

## 5. Plugin Architecture for Search Providers

### Current State
Hardcoded provider selection in `search_web`. No way to add custom providers.

### Issues
- Extensibility limited
- Adding new providers requires modifying core code
- No dynamic provider management

### Recommended Implementation

```python
# In web_search_mcp/search/__init__.py
"""Search provider plugin architecture."""

from abc import ABC, abstractmethod
from typing import ClassVar
from .._models import SearchRequest, SearchResponse, ErrorResponse

class BaseSearchProvider(ABC):
    """Abstract base class for search providers."""
    
    # Provider metadata
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    requires_api_key: ClassVar[bool] = False
    
    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """Check if this provider is available."""
        ...
    
    @abstractmethod
    def search(self, request: SearchRequest) -> SearchResponse | ErrorResponse:
        """Execute a search request."""
        ...

class ProviderRegistry:
    """Registry for search providers with plugin support."""
    
    def __init__(self):
        self._providers: dict[str, type[BaseSearchProvider]] = {}
        self._instances: dict[str, BaseSearchProvider] = {}
    
    def register(self, provider_class: type[BaseSearchProvider]) -> None:
        self._providers[provider_class.name] = provider_class
    
    def get_provider(self, name: str, **kwargs) -> BaseSearchProvider | None:
        if name not in self._instances:
            provider_class = self._providers.get(name)
            if provider_class:
                self._instances[name] = provider_class(**kwargs)
        return self._instances.get(name)
    
    def get_available_providers(self) -> list[str]:
        return [
            name for name, cls in self._providers.items()
            if cls.is_available()
        ]
    
    def auto_select(self, preferred: list[str] | None = None) -> BaseSearchProvider | None:
        """Auto-select the best available provider."""
        providers_to_try = preferred or list(self._providers.keys())
        
        for name in providers_to_try:
            provider = self.get_provider(name)
            if provider and provider.is_available():
                return provider
        
        for name in self._providers.keys():
            provider = self.get_provider(name)
            if provider and provider.is_available():
                return provider
        
        return None

# Global registry
provider_registry = ProviderRegistry()

# Register built-in providers
def register_builtin_providers() -> None:
    from .ddg import DuckDuckGoProvider
    from .exa import ExaProvider
    
    provider_registry.register(DuckDuckGoProvider)
    provider_registry.register(ExaProvider)
```

**Files to Create:**
- `web_search_mcp/search/providers.py` (base classes)

**Files to Modify:**
- `web_search_mcp/search/ddg.py` (create `DuckDuckGoProvider` class)
- `web_search_mcp/search/exa.py` (create `ExaProvider` class)
- `web_search_mcp/search/__init__.py` (add registry)
- `web_search_mcp/server.py` (use provider registry)

**Effort:** 4 hours  
**Impact:** High  
**Risk:** Medium

---

## 6. Configuration Management

### Current State
Settings split between `settings.py` and `limits.py`. No validation of configuration.

### Issues
- Configuration scattered across files
- No runtime validation
- Hard to override for testing
- No type safety for nested configurations

### Recommended Implementation

```python
# Enhanced web_search_mcp/_config/settings.py
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class RateLimitConfig(BaseSettings):
    search: int = 30
    fetch: int = 20
    github: int = 60
    reddit: int = 30
    x: int = 30
    
    @field_validator('*')
    @classmethod
    def validate_non_negative(cls, v: int, info) -> int:
        if v < 0:
            raise ValueError(f"{info.field_name} must be non-negative")
        return v

class DepthLimitConfig(BaseSettings):
    github: dict[str, int] = Field(default={"quick": 15, "default": 30, "deep": 60})
    hackernews: dict[str, int] = Field(default={"quick": 15, "default": 30, "deep": 60})
    reddit: dict[str, int] = Field(default={"quick": 10, "default": 25, "deep": 50})
    x: dict[str, int] = Field(default={"quick": 12, "default": 30, "deep": 60})
    
    @model_validator(mode='after')
    def validate_depth_values(self) -> 'DepthLimitConfig':
        for platform, limits in self.model_dump().items():
            for depth, value in limits.items():
                if value <= 0:
                    raise ValueError(f"{platform}.{depth} must be positive, got {value}")
        return self

class HTTPConfig(BaseSettings):
    timeout: float = 30.0
    max_connections: int = 100
    max_keepalive_connections: int = 20
    user_agent: str = "web-search-mcp/1.0"
    
    @field_validator('timeout')
    @classmethod
    def validate_timeout(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("timeout must be positive")
        return v

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SEARCH_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    exa_api_key: str = Field(default="", alias="EXA_API_KEY")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    xquik_api_key: str = Field(default="", alias="XQUIK_API_KEY")
    auth_token: str = Field(default="", alias="AUTH_TOKEN")
    ct0: str = Field(default="", alias="CT0")

    # Configuration sections
    rate_limits: RateLimitConfig = Field(default_factory=RateLimitConfig)
    depth_limits: DepthLimitConfig = Field(default_factory=DepthLimitConfig)
    http: HTTPConfig = Field(default_factory=HTTPConfig)

    # Feature flags
    enable_caching: bool = True
    enable_rate_limiting: bool = True
    enable_ssrf_protection: bool = True

    @classmethod
    def from_env(cls, **overrides) -> 'Settings':
        """Create settings with overrides for testing."""
        settings = cls()
        for key, value in overrides.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
        return settings

settings = Settings()

# Backward compatibility
rate_limit_search = settings.rate_limits.search
rate_limit_fetch = settings.rate_limits.fetch
```

**Files to Modify:**
- `web_search_mcp/_config/settings.py`

**Files to Deprecate:**
- `web_search_mcp/_config/limits.py`

**Effort:** 3 hours  
**Impact:** Medium  
**Risk:** Low
