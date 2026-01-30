from typing import Any, Protocol


class SearchProvider(Protocol):
    def search(self, query: str, search_type: str, **kwargs) -> dict[str, Any]: ...
