from typing import Any

from openai import AsyncOpenAI

from ..resilience import CircuitBreaker


class LLMProvider:
    """OpenAI-compatible provider (works for Gemini compat API, vLLM, Ollama)."""

    def __init__(
        self,
        name: str,
        model: str,
        base_url: str,
        api_key: str | None,
        *,
        breaker: CircuitBreaker,
        timeout_s: float,
    ) -> None:
        self.name = name
        self.model = model
        self.breaker = breaker
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key or "EMPTY",
            timeout=timeout_s,
            max_retries=0,
        )

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        top_p: float,
        max_tokens: int,
        json_schema: dict | None = None,
        schema_name: str = "assistant_answer",
        tools: list[dict] | None = None,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
        if json_schema is not None and not tools:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": json_schema,
                },
            }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message
