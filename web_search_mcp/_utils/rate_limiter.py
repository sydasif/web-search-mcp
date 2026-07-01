"""Sliding window rate limiter."""

from __future__ import annotations

import threading
import time


class RateLimiter:
    """A simple sliding window rate limiter.

    Args:
        requests_per_minute: Maximum number of requests allowed per minute.
        window_seconds: The time window in seconds to track requests. Defaults to 60.0.

    """

    def __init__(self, requests_per_minute: int = 30, window_seconds: float = 60.0) -> None:
        if requests_per_minute < 0:
            msg = "requests_per_minute must be >= 0"
            raise ValueError(msg)
        if window_seconds <= 0:
            msg = "window_seconds must be > 0"
            raise ValueError(msg)

        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.requests: list[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Blocks until a request can be made without exceeding the rate limit.

        This method implements a sliding window algorithm, removing requests older
        than the window_seconds and sleeping if the limit is reached.
        """
        if self.requests_per_minute <= 0:
            return

        while True:
            with self._lock:
                now = time.time()
                # Remove requests older than the window
                self.requests = [req for req in self.requests if now - req < self.window_seconds]

                if len(self.requests) < self.requests_per_minute:
                    self.requests.append(now)
                    return

                # Calculate wait time based on the oldest request in the window
                wait_time = self.window_seconds - (now - self.requests[0])

            if wait_time > 0:
                time.sleep(wait_time)
