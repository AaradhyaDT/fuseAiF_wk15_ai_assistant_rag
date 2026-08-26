from ..schemas import Source
from .store import VectorStore


class Retriever:
    def __init__(self, store: VectorStore, top_k: int = 4) -> None:
        self.store = store
        self.top_k = top_k

    def retrieve(self, query: str, k: int | None = None) -> list[dict]:
        return self.store.query(query, k or self.top_k)

    def context_block(self, query: str, k: int | None = None) -> tuple[str, list[Source]]:
        hits = self.retrieve(query, k)
        if not hits:
            return "", []
        lines = [
            f"[doc:{h['source']}] relevance={max(0.0, 1.0 - h['distance']):.2f}\n{h['text']}"
            for h in hits
        ]
        sources = [
            Source(
                source=h["source"],
                snippet=h["text"][:280],
                score=round(max(0.0, 1.0 - h["distance"]), 3),
            )
            for h in hits
        ]
        return "\n\n".join(lines), sources
