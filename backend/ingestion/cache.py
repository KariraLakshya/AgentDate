"""24h cache keyed by canonical URL. Pluggable backend, injectable clock.

Only normalized (already minimised) records are ever stored; raw scrape data never is.
"""
import copy
import time
from typing import Any, Callable, Optional, Protocol

TTL_SECONDS = 24 * 60 * 60


class CacheBackend(Protocol):
    def get(self, key: str) -> Optional[tuple[float, Any]]: ...
    def set(self, key: str, value: tuple[float, Any]) -> None: ...
    def delete(self, key: str) -> None: ...


class InMemoryBackend:
    def __init__(self):
        self._d: dict[str, tuple[float, Any]] = {}

    def get(self, key):
        return self._d.get(key)

    def set(self, key, value):
        self._d[key] = value

    def delete(self, key):
        self._d.pop(key, None)


class UrlCache:
    def __init__(self, backend: Optional[CacheBackend] = None, ttl: float = TTL_SECONDS,
                 clock: Callable[[], float] = time.time):
        self.backend = backend or InMemoryBackend()
        self.ttl = ttl
        self.clock = clock

    def get(self, url: str) -> Optional[Any]:
        item = self.backend.get(url)
        if item is None:
            return None
        stored_at, value = item
        if self.clock() - stored_at >= self.ttl:
            self.backend.delete(url)
            return None
        return copy.deepcopy(value)

    def set(self, url: str, value: Any) -> None:
        self.backend.set(url, (self.clock(), copy.deepcopy(value)))

    def delete(self, url: str) -> None:
        self.backend.delete(url)
