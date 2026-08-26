import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any


class RetryError(RuntimeError):
    def __init__(self, attempts: int, last: BaseException):
        super().__init__(f"gave up after {attempts} attempts: {last!r}")
        self.last = last


async def with_retries(
    fn: Callable[[], Awaitable[Any]],
    *,
    attempts: int,
    backoff_s: float,
    jitter_s: float = 0.25,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Any:
    """Exponential backoff with jitter around transient failures."""
    delay = backoff_s
    last: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except retry_on as exc:
            last = exc
            if attempt == attempts:
                break
            await sleep(delay + random.uniform(0.0, jitter_s))
            delay *= 2.0
    raise RetryError(attempts, last)


class BreakerOpenError(RuntimeError):
    pass


class CircuitBreaker:
    """Per-provider circuit breaker: closed -> open -> half-open -> closed."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        reset_timeout_s: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.reset_timeout_s = reset_timeout_s
        self._clock = clock
        self.state = "closed"
        self._failures = 0
        self._opened_at: float | None = None
        self._probing = False

    def _trip(self) -> None:
        self.state = "open"
        self._opened_at = self._clock()

    def _allow_call(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if self._opened_at is None:
                self._opened_at = self._clock()
            if self._clock() - self._opened_at >= self.reset_timeout_s:
                self.state = "half-open"
                self._probing = True
                return True
            return False
        return not self._probing

    async def call(self, fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        if not self._allow_call():
            raise BreakerOpenError(f"{self.name} circuit open")
        try:
            result = await fn(*args, **kwargs)
        except Exception:
            self._failures += 1
            if self.state == "half-open" or self._failures >= self.failure_threshold:
                self._trip()
                self._probing = False
            raise
        self.state = "closed"
        self._failures = 0
        self._probing = False
        return result


class TokenBucket:
    """Sync token-bucket rate limiter (per client, in-process)."""

    def __init__(self, rpm: int, burst: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.rate_per_sec = max(rpm, 1) / 60.0
        self.capacity = max(1, burst)
        self.tokens = float(self.capacity)
        self._last = clock()
        self._clock = clock

    def allow(self) -> bool:
        now = self._clock()
        elapsed = max(0.0, now - self._last)
        self._last = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_sec)
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False
