# Architecture

## Component diagram

```mermaid
flowchart LR
    subgraph Client
        B["Browser"]
    end
    subgraph Edge["FastAPI backend (:8000, Docker)"]
        RL["Token-bucket rate limiter<br/>(per client IP)"]
        RT["POST /chat"]
        CACHE[("TTL + LRU cache")]
        ORCH["Orchestrator"]
        subgraph RAG
            RET["Retriever"]
            VS[("Qdrant<br/>embedded local or service")]
        end
        TL["Tool executor<br/>calculator · datetime · kb_search"]
    end
    subgraph Providers["Provider fallback chain"]
        direction TB
        P1["gemini — Gemini 2.5 Flash<br/>(primary cloud)"]
        P2["vllm — Qwen2.5-1.5B-Instruct<br/>(local CPU, Dockerfile.vllm)"]
        P3["ollama — qwen2.5:1.5b-instruct<br/>(host fallback)"]
    end
    subgraph Serving["Local inference stack"]
        VLLM["vLLM server :8001<br/>weights baked into image"]
        OL["Ollama :11434"]
        QR["Qdrant :6333<br/>(service mode in compose;<br/>embedded file mode in dev)"]
    end
    B -->|HTTP| UI["Streamlit UI :8501"]
    UI --> RL --> RT --> ORCH
    ORCH <--> CACHE
    ORCH --> RET --> VS
    ORCH --> TL
    ORCH --> P1
    P1 -.->|on failure| P2
    P2 -.->|on failure| P3
    P2 --- VLLM
    P3 --- OL
    RET --- QR
```

## Chat request sequence

```mermaid
sequenceDiagram
    participant UI as Streamlit UI
    participant API as FastAPI
    participant C as Cache
    participant R as Retriever
    participant O as Orchestrator
    participant P as Provider chain

    UI->>API: POST /chat {message}
    API->>API: rate limit check (429 if burst exceeded)
    API->>C: sha256(message, flags, params)
    alt cache hit
        C-->>API: ChatResponse (cached=true)
    else miss
        API->>R: top-k similarity search
        R-->>O: context block + sources
        O->>P: messages + json_schema + tools
        Note over P: retry w/ backoff → circuit breaker → next provider
        P-->>O: assistant message (or tool_calls)
        opt tool_calls present
            O->>O: execute tools locally, append results, re-call (max 3 rounds)
        end
        O->>O: validate Pydantic AssistantAnswer (lenient parse fallback)
        O->>C: store response
    end
    API-->>UI: ChatResponse {answer, sources, provider_used, latency_ms, degraded}
```

## Reliability design

| Failure | Mechanism | User-visible behavior |
|---|---|---|
| Transient network/API error | Exponential backoff + jitter (default 3 attempts) | Slight latency increase |
| Provider persistently failing | Circuit breaker opens after N failures, half-open probe after cooldown | Requests skip dead provider instantly |
| Gemini quota/auth missing | Chain falls through to vLLM, then Ollama | Answer served by local model |
| All providers down | Degraded response synthesized from retrieved passages | 200 with `degraded: true`, never a crash |
| Malformed JSON from weak model | Fence-stripping + regex extraction before giving up | Raw text answer instead of error |
| Request flood | Token bucket (60 rpm, burst 20 per IP) | 429 with Retry-After |
| Vector store unreachable | Retrieval wrapped in try/except; chat continues without grounding context (logged) | 200 with no sources, answer from general knowledge |
| Repeated identical question | TTL cache (300 s, 512 entries) | Instant response, `cached: true` |

## Performance notes

- Endpoints are fully async; provider calls never block the event loop.
- The embedding model loads lazily on first ingest/query and is pre-baked into the Docker image, so dev startup stays fast while containers stay network-free.
- Cache keys hash message + flags + sampling params, so toggling RAG/tools misses deliberately.
- Single uvicorn worker keeps the in-process cache/rate-limiter coherent; scale by running replicas behind a proxy (swap the in-memory pieces for Redis when you do).
- The local model choice (1.5B, max_model_len 4096, KV-cache 4 GB) trades capability for demoable latency on CPU-only hardware.
