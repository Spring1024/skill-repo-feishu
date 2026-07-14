from __future__ import annotations

from cachetools import TTLCache


class FolderCache:
    """In-memory LRU cache for Feishu Drive folder structures."""

    def __init__(self, ttl: int = 300, maxsize: int = 128) -> None:
        self._cache: TTLCache[str, list[dict]] = TTLCache(maxsize=maxsize, ttl=ttl)

    def get(self, parent_token: str) -> list[dict] | None:
        return self._cache.get(parent_token)

    def set(self, parent_token: str, items: list[dict]) -> None:
        self._cache[parent_token] = items

    def invalidate(self, parent_token: str | None = None) -> None:
        if parent_token is None:
            self._cache.clear()
        else:
            self._cache.pop(parent_token, None)

    def get_or_set(self, parent_token: str, loader) -> list[dict]:
        """Get from cache or call loader() to populate."""
        data = self._cache.get(parent_token)
        if data is not None:
            return data
        data = loader()
        self._cache[parent_token] = data
        return data

    def add_entry(self, parent_token: str, entry: dict) -> None:
        existing = self._cache.get(parent_token) or []
        # Avoid duplicates by token
        tokens = {e["file_token"] for e in existing}
        if entry["file_token"] not in tokens:
            existing.append(entry)
        self._cache[parent_token] = existing
