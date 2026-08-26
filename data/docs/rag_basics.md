# Retrieval-Augmented Generation (RAG)

Retrieval-Augmented Generation grounds an LLM's answers in an external corpus instead of relying only on parametric memory. A typical pipeline has two phases.

## Ingestion phase

Documents are loaded, split into chunks, converted into embedding vectors, and stored in a vector database. Chunking strategy matters: too large and retrieval becomes noisy, too small and context is fragmented. A common baseline is paragraph-aware chunking with 400-1000 characters per chunk and 10-20% overlap between consecutive chunks so ideas that straddle boundaries survive.

## Query phase

The user's question is embedded with the same model used at ingestion time, then similarity search (usually cosine distance) returns the top-k chunks. Those chunks are injected into the system prompt as grounding context, and the model is instructed to cite them rather than invent facts.

## Why vector databases

Vector databases such as ChromaDB, FAISS, Milvus, or pgvector index embeddings for approximate nearest neighbor search. This makes retrieval fast even with millions of chunks, and persistent stores allow the index to be reused across service restarts without re-embedding everything.
