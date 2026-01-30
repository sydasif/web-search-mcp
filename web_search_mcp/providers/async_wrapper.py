import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from .base import SearchProvider


class AsyncSearchProviderWrapper:
    def __init__(self, provider: SearchProvider):
        self.provider = provider
        self.executor = ThreadPoolExecutor(
            max_workers=4
        )  # Limit concurrent DDG searches

    async def search(self, query: str, search_type: str, **kwargs) -> dict[str, Any]:
        """Async wrapper that runs the synchronous search in a thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.executor, lambda: self.provider.search(query, search_type, **kwargs)
        )

    def close(self):
        """Close the thread pool executor."""
        self.executor.shutdown(wait=True)
