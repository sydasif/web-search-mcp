"""Thread-safe TTL cache and decorator for search and fetch operations."""

from __future__ import annotations

import time
from collections.abc import Callable
from functools import wraps
from threading import Lock
from typing import Any, TypeVar

T = TypeVar("T")


class TTLCache:
    """A thread-safe time-to-live cache."""

    def __init__(self, default_ttl: float = 300.0, max_size: int = 1000) -> None:
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        """Get an item from the cache if it exists and has not expired."""
        with self._lock:
            if key not in self._cache:
                return None
            expiry, value = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set an item in the cache with an optional TTL."""
        with self._lock:
            if len(self._cache) >= self.max_size and self._cache:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            expiry = time.time() + (ttl if ttl is not None else self.default_ttl)
            self._cache[key] = (expiry, value)

    def clear(self) -> None:
        """Clear all items from the cache."""
        with self._lock:
            self._cache.clear()


# Global search cache instance
search_cache = TTLCache(default_ttl=300.0)


def cached(
    cache_instance: TTLCache,
    key_func: Callable[..., str] | None = None,
    ttl: float | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to cache function results in a TTLCache."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{args}:{kwargs}"

            cached_val = cache_instance.get(cache_key)
            if cached_val is not None:
                return cached_val

            result = func(*args, **kwargs)
            cache_instance.set(cache_key, result, ttl=ttl)
            return result

        return wrapper

    return decorator
