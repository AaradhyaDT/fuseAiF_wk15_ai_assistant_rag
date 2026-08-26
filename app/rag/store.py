from pathlib import Path

import chromadb


class VectorStore:
    def __init__(self, persist_dir: str | Path, collection_name: str, embedding_fn=None) -> None:
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._kwargs = {"embedding_function": embedding_fn} if embedding_fn is not None else {}
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection_name = collection_name
        self.collection = self._client.get_or_create_collection(
            collection_name, metadata={"hnsw:space": "cosine"}, **self._kwargs
        )

    def reset(self) -> None:
        self._client.delete_collection(self.collection_name)
        self.collection = self._client.get_or_create_collection(
            self.collection_name, metadata={"hnsw:space": "cosine"}, **self._kwargs
        )

    def upsert(self, ids: list[str], documents: list[str], metadatas: list[dict]) -> None:
        self.collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    def count(self) -> int:
        return self.collection.count()

    def query(self, text: str, k: int) -> list[dict]:
        total = self.count()
        if total == 0:
            return []
        result = self.collection.query(
            query_texts=[text],
            n_results=min(k, total),
            include=["documents", "metadatas", "distances"],
        )
        hits = []
        for doc, meta, dist in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0], strict=True
        ):
            hits.append(
                {
                    "text": doc,
                    "source": (meta or {}).get("source", "unknown"),
                    "distance": dist,
                }
            )
        return hits
