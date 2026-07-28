# Performance Optimizations

## Overview

This document details the performance optimizations recommended for web-search-mcp.

---

## 1. HTTP Client Management

### Current State
Global `http_client` in `_http/client.py` is created at module load time with basic configuration.

### Issues
- No connection pooling
- No retry logic for transient failures
- Global client doesn't respect context managers

### Recommended Implementation

```python
# In _http/client.py
from contextlib import asynccontextmanager
import httpx

# Configure retry logic
RETRY_CONFIG = httpx.Retry(
    total=3,
    backoff_factor=0.5,
    status_codes=[429, 500, 502, 503, 504],
)

# Use connection pooling
http_client = httpx.Client(
    timeout=30.0,
    headers={"User-Agent": settings.user_agent},
    follow_redirects=True,
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    retry=RETRY_CONFIG,
    verify=True,
)

def get_retry_client(timeout: float = 15.0) -> httpx.Client:
    """Return a context-managed httpx client configured for JSON API calls with retries."""
    return httpx.Client(
        timeout=timeout,
        headers={
            "User-Agent": settings.user_agent,
            "Accept": "application/json",
        },
        retry=RETRY_CONFIG,
        verify=True,
    )
```

**Files to Modify:**
- `web_search_mcp/_http/client.py`

**Effort:** 1 hour  
**Impact:** High  
**Risk:** Low

---

## 2. Rate Limiter Improvements

### Current State
Simple sliding window rate limiter with thread locking in `_utils/rate_limiter.py`.

### Issues
- Thread-based locking adds overhead
- No async support
- Global rate limiters may cause bottlenecks

### Recommended Implementation

```python
# In _utils/rate_limiter.py
from collections import deque
import asyncio
import time
from typing import Optional

class AsyncRateLimiter:
    """Async-compatible rate limiter with sliding window."""

    def __init__(self, requests_per_minute: int = 30, window_seconds: float = 60.0):
        if requests_per_minute < 0:
            raise ValueError("requests_per_minute must be >= 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")

        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.requests: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Async version of acquire."""
        if self.requests_per_minute <= 0:
            return

        while True:
            now = time.time()
            async with self._lock:
                # Remove requests older than the window
                while self.requests and now - self.requests[0] > self.window_seconds:
                    self.requests.popleft()

                if len(self.requests) < self.requests_per_minute:
                    self.requests.append(now)
                    return

                wait_time = self.window_seconds - (now - self.requests[0])

            if wait_time > 0:
                await asyncio.sleep(wait_time)

    def acquire_sync(self) -> None:
        """Synchronous version for backward compatibility."""
        import threading
        if self.requests_per_minute <= 0:
            return

        _sync_lock = threading.Lock()
        while True:
            now = time.time()
            with _sync_lock:
                while self.requests and now - self.requests[0] > self.window_seconds:
                    self.requests.popleft()

                if len(self.requests) < self.requests_per_minute:
                    self.requests.append(now)
                    return

                wait_time = self.window_seconds - (now - self.requests[0])

            if wait_time > 0:
                time.sleep(wait_time)
```

**Files to Modify:**
- `web_search_mcp/_utils/rate_limiter.py`

**Files to Update:**
- `web_search_mcp/search/ddg.py` (update imports)

**Effort:** 2 hours  
**Impact:** High  
**Risk:** Medium

---

## 3. Caching Layer

### Current State
No caching for repeated queries - same searches may be executed multiple times.

### Issues
- Redundant API calls
- Increased latency for repeated queries
- Higher API usage costs (for Exa)

### Recommended Implementation

```python
# New file: web_search_mcp/_utils/cache.py
"""Simple in-memory caching with TTL for search results."""

from functools import wraps
from typing import Callable, TypeVar, Any
import time
import threading

T = TypeVar('T')

class TTLCache:
    """Thread-safe cache with TTL expiration."""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._lock = threading.RLock()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds

    def get(self, key: str) -> tuple[bool, Any]:
        """Get value from cache. Returns (found, value)."""
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self._ttl_seconds:
                    return True, value
                else:
                    del self._cache[key]
            return False, None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache with automatic TTL."""
        with self._lock:
            if len(self._cache) >= self._max_size:
                oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]
            
            self._cache[key] = (value, time.time())

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()

    def invalidate(self, key: str) -> bool:
        """Invalidate a specific cache entry."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

# Global cache instances
search_cache = TTLCache(max_size=500, ttl_seconds=300)  # 5 minutes
fetch_cache = TTLCache(max_size=200, ttl_seconds=600)  # 10 minutes

def cached(cache: TTLCache, key_func: Callable[..., str] | None = None):
    """Decorator for caching function results."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{args}:{frozenset(kwargs.items())}"
            
            found, value = cache.get(cache_key)
            if found:
                return value
            
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result
        
        wrapper.cache_clear = lambda: cache.clear()
        wrapper.cache_invalidate = lambda key: cache.invalidate(key)
        
        return wrapper
    return decorator
```

**Usage Example:**

```python
# In web_search_mcp/search/ddg.py
from .._utils.cache import cached, search_cache

@cached(search_cache, key_func=lambda req: f"ddg:{req.query}:{req.search_type}")
def ddg_search(request: SearchRequest) -> SearchResponse | ErrorResponse:
    # ... existing implementation
```

**Files to Create:**
- `web_search_mcp/_utils/cache.py`

**Files to Modify:**
- `web_search_mcp/search/ddg.py`
- `web_search_mcp/search/exa.py`
- All other search modules

**Effort:** 3 hours  
**Impact:** High  
**Risk:** Low

---

## 4. Enhanced SSRF Protection

### Current State
Basic IP validation in `validate_url` blocks private IP ranges.

### Issues
- Doesn't resolve hostnames to check for private IPs
- No caching of DNS lookups
- Could be more comprehensive

### Recommended Implementation

```python
# Enhanced web_search_mcp/_http/client.py
import ipaddress
import socket
from functools import lru_cache

# List of blocked IP ranges (CIDR notation)
BLOCKED_NETWORKS = [
    # Loopback
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('::1/128'),
    
    # Private networks
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    
    # Link-local
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('fe80::/10'),
    
    # Carrier-grade NAT
    ipaddress.ip_network('100.64.0.0/10'),
    
    # Reserved
    ipaddress.ip_network('240.0.0.0/4'),
    ipaddress.ip_network('::2/128'),
    ipaddress.ip_network('::/96'),
    ipaddress.ip_network('::ffff:0:0/96'),
    
    # IPv6 unique local addresses
    ipaddress.ip_network('fc00::/7'),
]

@lru_cache(maxsize=1000)
def _resolve_hostname(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve hostname to IP addresses with caching."""
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        ips = []
        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            try:
                ip = ipaddress.ip_address(ip_str)
                ips.append(ip)
            except ValueError:
                continue
        return ips
    except socket.gaierror:
        return []
    except Exception:
        return []


def is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if IP is in a blocked range."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    
    for network in BLOCKED_NETWORKS:
        if ip in network:
            return True
    return False


def validate_url(url: str, resolve_hostname: bool = True) -> str:
    """Validate URL with enhanced SSRF protection."""
    from urllib.parse import urlparse
    
    parsed = urlparse(url)
    
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme!r}")

    host = (parsed.hostname or "").strip()
    if not host:
        raise ValueError("URL has no hostname")

    # Check for IP address literal
    try:
        addr = ipaddress.ip_address(host)
        if is_blocked_ip(addr):
            raise ValueError(f"URL uses a blocked IP address: {addr}")
        return url
    except ValueError:
        pass

    # Check for localhost
    if host.lower() in {"localhost", "localhost.localdomain", "127.0.0.1", "::1"}:
        raise ValueError(f"URL uses localhost: {host}")

    # Resolve hostname to check for private IPs
    if resolve_hostname:
        ips = _resolve_hostname(host)
        for ip in ips:
            if is_blocked_ip(ip):
                raise ValueError(f"URL resolves to blocked IP: {ip} (from {host})")

    return url


def clear_dns_cache() -> None:
    """Clear the DNS resolution cache."""
    _resolve_hostname.cache_clear()
```

**Files to Modify:**
- `web_search_mcp/_http/client.py`

**Effort:** 2 hours  
**Impact:** High  
**Risk:** Low

---

## 5. Input Validation

### Current State
Basic validation in some places, inconsistent across modules.

### Issues
- Potential for injection attacks
- No centralized validation
- Inconsistent validation logic

### Recommended Implementation

```python
# New file: web_search_mcp/_utils/validation.py
"""Input validation utilities."""

import re
from urllib.parse import urlparse


def validate_search_query(query: str, max_length: int = 500) -> str:
    """Validate and sanitize search query."""
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")
    
    query = query.strip()
    
    if len(query) > max_length:
        raise ValueError(f"Query too long: {len(query)} > {max_length}")
    
    # Remove potentially harmful patterns
    harmful_patterns = [
        r'<script.*?>.*?</script>',
        r'on\w+\s*=',
        r'javascript:',
        r'data:',
        r'vbscript:',
    ]
    
    for pattern in harmful_patterns:
        query = re.sub(pattern, '', query, flags=re.IGNORECASE)
    
    # Remove excessive whitespace
    query = re.sub(r'\s+', ' ', query)
    
    return query


def validate_url(url: str, allowed_schemes: set[str] | None = None) -> str:
    """Validate a URL."""
    if allowed_schemes is None:
        allowed_schemes = {"http", "https"}
    
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValueError(f"Invalid URL: {e}")
    
    if not parsed.scheme:
        raise ValueError("URL must have a scheme")
    
    if parsed.scheme.lower() not in allowed_schemes:
        raise ValueError(f"URL scheme must be one of {allowed_schemes}")
    
    if not parsed.netloc:
        raise ValueError("URL must have a hostname")
    
    return url


def validate_max_results(max_results: int, min_val: int = 1, max_val: int = 100) -> int:
    """Validate max_results parameter."""
    if not isinstance(max_results, int):
        raise ValueError(f"max_results must be an integer")
    
    if max_results < min_val:
        raise ValueError(f"max_results must be at least {min_val}")
    
    if max_results > max_val:
        raise ValueError(f"max_results must be at most {max_val}")
    
    return max_results


def validate_time_range(time_range: str | None) -> str | None:
    """Validate time_range parameter."""
    if time_range is None:
        return None
    
    valid_ranges = {"d", "w", "m", "y"}
    
    if time_range.lower() not in valid_ranges:
        raise ValueError(f"time_range must be one of {valid_ranges}")
    
    return time_range.lower()
```

**Files to Create:**
- `web_search_mcp/_utils/validation.py`

**Files to Modify:**
- `web_search_mcp/server.py` (use validation in tool functions)

**Effort:** 2 hours  
**Impact:** High  
**Risk:** Low
