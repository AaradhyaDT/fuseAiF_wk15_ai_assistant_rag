import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any


class TTLCache:
    """Small in-memory TTL + LRU cache for prompt/response pairs."""

    def __init__(
        self,
        ttl_s: int,
        max_items: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.ttl = ttl_s
        self.max_items = max_items
        self.clock = clock
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    @staticmethod
    def make_key(*parts: Any) -> str:
        payload = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, key: str) -> Any:
        item = self._data.get(key)
        if item is None:
            return None
        ts, value = item
        if self.clock() - ts > self.ttl:
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return value

    def put(self, key: str, value: Any) -> None:
        self._data[key] = (self.clock(), value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_items:
            self._data.popitem(last=False)

    def __len__(self) -> int:
        return len(self._data)
