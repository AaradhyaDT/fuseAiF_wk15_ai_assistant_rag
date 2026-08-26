import logging
from typing import Any, Protocol

from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

from ..config import Settings
from ..resilience import CircuitBreaker, with_retries
from .base import LLMProvider

logger = logging.getLogger(__name__)

TRANSIENT_ERRORS = (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError)


class AllProvidersFailedError(RuntimeError):
    def __init__(self, errors: dict[str, str]):
        super().__init__(f"all providers failed: {errors}")
        self.errors = errors


class _ProviderLike(Protocol):
    name: str
    breaker: CircuitBreaker

    async def complete(self, *args: Any, **kwargs: Any) -> Any: ...


def _make(name: str, settings: Settings) -> LLMProvider:
    spec = {
        "gemini": (settings.gemini_model, settings.gemini_base_url, settings.gemini_api_key),
        "vllm": (settings.vllm_model, settings.vllm_base_url, settings.vllm_api_key),
        "ollama": (settings.ollama_model, settings.ollama_base_url, settings.ollama_api_key),
    }[name]
    model, base_url, api_key = spec
    return LLMProvider(
        name,
        model,
        base_url,
        api_key,
        breaker=CircuitBreaker(
            name, settings.breaker_failure_threshold, settings.breaker_reset_timeout_s
        ),
        timeout_s=settings.request_timeout_s,
    )


def build_providers(settings: Settings) -> list[LLMProvider]:
    candidates: list[LLMProvider] = []
    if settings.gemini_api_key:
        candidates.append(_make("gemini", settings))
    candidates.append(_make("vllm", settings))
    candidates.append(_make("ollama", settings))
    by_name = {p.name: p for p in candidates}
    ordered: list[LLMProvider] = []
    for raw in settings.provider_order.split(","):
        p = by_name.get(raw.strip())
        if p is not None and p not in ordered:
            ordered.append(p)
    ordered.extend(p for p in candidates if p not in ordered)
    return ordered


async def execute_chain(
    providers: list[_ProviderLike],
    messages: list[dict[str, Any]],
    settings: Settings,
    **gen_kwargs: Any,
) -> tuple[str, Any]:
    """Walk the fallback chain; first healthy provider wins."""
    errors: dict[str, str] = {}
    for provider in providers:
        try:
            message = await with_retries(
                lambda p=provider: p.breaker.call(
                    p.complete,
                    messages,
                    temperature=settings.temperature,
                    top_p=settings.top_p,
                    max_tokens=settings.max_output_tokens,
                    **gen_kwargs,
                ),
                attempts=settings.retry_attempts,
                backoff_s=settings.retry_backoff_s,
                retry_on=TRANSIENT_ERRORS,
            )
            return provider.name, message
        except Exception as exc:
            errors[provider.name] = f"{type(exc).__name__}: {exc}"
            logger.warning("provider %s failed: %s", provider.name, errors[provider.name])
    raise AllProvidersFailedError(errors)
