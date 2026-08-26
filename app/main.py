import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import Settings, get_settings
from .orchestrator import Orchestrator
from .providers import build_providers
from .rag.ingest import ingest_documents
from .rag.retriever import Retriever
from .rag.store import VectorStore
from .resilience import TokenBucket
from .schemas import ChatRequest, ChatResponse
from .tools import TOOL_SPECS


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, rpm: int, burst: int) -> None:
        super().__init__(app)
        self._buckets: dict[str, TokenBucket] = {}
        self._rpm = rpm
        self._burst = burst

    async def dispatch(self, request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        client_ip = request.client.host if request.client else "anonymous"
        bucket = self._buckets.get(client_ip)
        if bucket is None:
            bucket = self._buckets[client_ip] = TokenBucket(self._rpm, self._burst)
        if not bucket.allow():
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": "5"},
            )
        return await call_next(request)


def create_app(settings: Settings | None = None, embedding_fn=None) -> FastAPI:
    settings = settings or get_settings()
    store = VectorStore(settings.chroma_dir, settings.collection_name, embedding_fn=embedding_fn)
    retriever = Retriever(store, top_k=settings.top_k)
    orchestrator = Orchestrator(settings, build_providers(settings), retriever)

    app = FastAPI(title=settings.app_name, version="1.0.0")
    app.state.settings = settings
    app.state.store = store
    app.state.retriever = retriever
    app.state.orchestrator = orchestrator
    app.state.started_at = time.time()

    app.add_middleware(
        RateLimitMiddleware, rpm=settings.rate_limit_rpm, burst=settings.rate_limit_burst
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )

    @app.get("/")
    async def root():
        return {"service": settings.app_name, "docs_url": "/docs"}

    @app.get("/health")
    async def health(request: Request):
        state = request.app.state
        return {
            "status": "ok",
            "uptime_s": round(time.time() - state.started_at, 1),
            "documents_indexed": state.store.count(),
            "providers": [
                {"name": p.name, "breaker_state": p.breaker.state}
                for p in state.orchestrator.chain
            ],
        }

    @app.post("/chat", response_model=ChatResponse)
    async def chat(payload: ChatRequest, request: Request):
        return await request.app.state.orchestrator.chat(payload)

    @app.post("/ingest")
    async def ingest(request: Request):
        state = request.app.state
        stats = ingest_documents(
            state.store,
            Path(state.settings.data_docs_dir),
            state.settings.chunk_size_chars,
            state.settings.chunk_overlap_chars,
        )
        return stats

    @app.get("/tools")
    async def tools():
        return {"tools": TOOL_SPECS}

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:create_app", factory=True, host="0.0.0.0", port=8000)
