import hashlib
import math

import pytest
from chromadb import EmbeddingFunction

from app.config import Settings
from app.rag.retriever import Retriever
from app.rag.store import VectorStore

DIM = 64


def _token_vec(token: str) -> list[float]:
    vec = [0.0] * DIM
    digest = int(hashlib.sha256(token.encode()).hexdigest(), 16)
    idx = digest % DIM
    sign = 1.0 if (digest >> 8) & 1 else -1.0
    vec[idx] += sign
    vec[(digest >> 16) % DIM] += sign * 0.5
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class BagOfWordsEmbedder(EmbeddingFunction):
    """Deterministic offline embedder: hashed bag-of-words, unit-normalized."""

    def __init__(self) -> None:
        super().__init__()

    def __call__(self, input):
        outputs = []
        for text in input:
            acc = [0.0] * DIM
            for token in text.lower().split():
                tv = _token_vec(token)
                acc = [a + b for a, b in zip(acc, tv, strict=True)]
            norm = math.sqrt(sum(x * x for x in acc)) or 1.0
            outputs.append([x / norm for x in acc])
        return outputs

    def name(self) -> str:
        return "bag_of_words_test"

    def get_config(self) -> dict:
        return {}

    @classmethod
    def build_from_config(cls, config: dict):
        return cls()


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        gemini_api_key="",
        data_docs_dir=str(tmp_path / "docs"),
        chroma_dir=str(tmp_path / "chroma"),
    )


@pytest.fixture
def store(tmp_path):
    return VectorStore(tmp_path / "chroma", "test_kb", embedding_fn=BagOfWordsEmbedder())


@pytest.fixture
def retriever(store):
    return Retriever(store, top_k=3)
