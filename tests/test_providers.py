import pytest

from app.config import Settings
from app.providers import AllProvidersFailedError, execute_chain
from app.resilience import CircuitBreaker


class StubProvider:
    def __init__(self, name: str, behavior: str):
        self.name = name
        self.behavior = behavior
        self.breaker = CircuitBreaker(name, failure_threshold=100, reset_timeout_s=1)

    async def complete(self, messages, **kwargs):
        if self.behavior == "fail":
            raise RuntimeError("simulated outage")
        return f"reply-from-{self.name}"


@pytest.fixture
def chain_settings():
    return Settings(_env_file=None, retry_attempts=2, retry_backoff_s=0.001)


async def test_chain_skips_broken_provider(chain_settings):
    providers = [StubProvider("first", "fail"), StubProvider("second", "ok")]
    name, message = await execute_chain(providers, [], chain_settings)
    assert name == "second"
    assert message == "reply-from-second"


async def test_chain_first_healthy_provider_wins(chain_settings):
    providers = [StubProvider("first", "ok"), StubProvider("second", "ok")]
    name, _message = await execute_chain(providers, [], chain_settings)
    assert name == "first"


async def test_chain_all_fail_raises(chain_settings):
    providers = [StubProvider("a", "fail"), StubProvider("b", "fail")]
    with pytest.raises(AllProvidersFailedError) as excinfo:
        await execute_chain(providers, [], chain_settings)
    assert set(excinfo.value.errors) == {"a", "b"}
