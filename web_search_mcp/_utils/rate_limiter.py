"""Sliding window rate limiter (sync and async)."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque


class RateLimiter:
    """A simple thread-safe sliding window rate limiter."""

    def __init__(self, requests_per_minute: int = 30, window_seconds: float = 60.0) -> None:
        if requests_per_minute < 0:
            msg = "requests_per_minute must be >= 0"
            raise ValueError(msg)
        if window_seconds <= 0:
            msg = "window_seconds must be > 0"
            raise ValueError(msg)

        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.requests: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Blocks until a request can be made without exceeding the rate limit."""
        if self.requests_per_minute <= 0:
            return

        while True:
            with self._lock:
                now = time.time()
                while self.requests and now - self.requests[0] >= self.window_seconds:
                    self.requests.popleft()

                if len(self.requests) < self.requests_per_minute:
                    self.requests.append(now)
                    return

                wait_time = self.window_seconds - (now - self.requests[0])

            if wait_time > 0:
                time.sleep(wait_time)


class AsyncRateLimiter:
    """An async-compatible sliding window rate limiter."""

    def __init__(self, requests_per_minute: int = 30, window_seconds: float = 60.0) -> None:
        if requests_per_minute < 0:
            msg = "requests_per_minute must be >= 0"
            raise ValueError(msg)
        if window_seconds <= 0:
            msg = "window_seconds must be > 0"
            raise ValueError(msg)

        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.requests: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Async acquisition of rate limit slot."""
        if self.requests_per_minute <= 0:
            return

        while True:
            async with self._lock:
                now = time.time()
                while self.requests and now - self.requests[0] >= self.window_seconds:
                    self.requests.popleft()

                if len(self.requests) < self.requests_per_minute:
                    self.requests.append(now)
                    return

                wait_time = self.window_seconds - (now - self.requests[0])

            if wait_time > 0:
                await asyncio.sleep(wait_time)
