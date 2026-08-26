import pytest

from app.resilience import BreakerOpenError, CircuitBreaker, RetryError, TokenBucket, with_retries


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, delta):
        self.t += delta


async def test_retry_succeeds_after_transient_failures():
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("boom")
        return "ok"

    assert await with_retries(flaky, attempts=5, backoff_s=0.001) == "ok"
    assert calls["n"] == 3


async def test_retry_raises_after_exhaustion():
    async def always_fails():
        raise ValueError("always")

    with pytest.raises(RetryError):
        await with_retries(always_fails, attempts=3, backoff_s=0.001)


async def test_breaker_opens_then_half_opens_and_closes():
    clock = FakeClock()
    breaker = CircuitBreaker("t", failure_threshold=2, reset_timeout_s=10.0, clock=clock)

    async def fail():
        raise RuntimeError("down")

    async def ok():
        return "y"

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(fail)
    assert breaker.state == "open"
    with pytest.raises(BreakerOpenError):
        await breaker.call(fail)
    clock.advance(11.0)
    assert await breaker.call(ok) == "y"
    assert breaker.state == "closed"


async def test_breaker_stays_open_before_timeout():
    clock = FakeClock()
    breaker = CircuitBreaker("t", failure_threshold=1, reset_timeout_s=60.0, clock=clock)

    async def fail():
        raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        await breaker.call(fail)
    with pytest.raises(BreakerOpenError):
        await breaker.call(fail)


def test_token_bucket_bursts_then_refills():
    clock = FakeClock()
    bucket = TokenBucket(rpm=60, burst=2, clock=clock)
    assert bucket.allow()
    assert bucket.allow()
    assert not bucket.allow()
    clock.advance(2.0)
    assert bucket.allow()
