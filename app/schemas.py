from pydantic import BaseModel, Field


class Source(BaseModel):
    source: str
    snippet: str
    score: float | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: str | None = None
    use_rag: bool = True
    use_tools: bool = True


class AssistantAnswer(BaseModel):
    """Structured payload every provider is asked to emit."""

    answer: str
    used_context: bool = False


ASSISTANT_ANSWER_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "used_context": {"type": "boolean"},
    },
    "required": ["answer"],
}


class ChatResponse(BaseModel):
    answer: str
    provider_used: str
    degraded: bool = False
    cached: bool = False
    sources: list[Source] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    latency_ms: int = 0
