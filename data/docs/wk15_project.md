# WK15 Assistant: Architecture Overview

This project is a production-style AI assistant built for the Fuse AI Fellowship Week 15 assignment.

## Components

- FastAPI backend exposing /chat, /ingest, /health, /tools.
- Orchestrator implementing cache lookup, RAG grounding, a tool-calling loop, and JSON schema enforcement.
- Provider chain: Gemini 2.5 Flash first, then a locally served Qwen2.5-1.5B-Instruct behind vLLM, then Ollama as final fallback.
- ChromaDB vector store persisted under data/chroma, populated from markdown documents in data/docs.
- Streamlit chat UI talking to the backend over HTTP.

## Reliability features

Every provider call is wrapped in exponential-backoff retries for transient errors and a circuit breaker that trips after repeated failures. When every provider is down the API still answers with a degraded response built from retrieved passages instead of crashing.

## Structured output

Each request asks the model for JSON matching a fixed schema via response_format json_schema. The orchestrator validates the payload with Pydantic and falls back to lenient parsing if a weaker model emits fenced or slightly malformed JSON.

## Tool calling

Three tools are registered in OpenAI function-calling format: calculator (AST-whitelisted arithmetic), current_datetime, and search_knowledge_base (semantic search over the corpus). The orchestrator executes tool calls locally and feeds results back to the model until it produces a final answer or hits the round budget.
