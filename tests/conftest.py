import hashlib
import math

import pytest

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


class BagOfWordsEmbedder:
    """Deterministic offline embedder: hashed bag-of-words, unit-normalized."""

    dim = DIM

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


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        gemini_api_key="",
        data_docs_dir=str(tmp_path / "docs"),
        qdrant_path=str(tmp_path / "qdrant"),
    )


@pytest.fixture
def store(tmp_path):
    return VectorStore("test_kb", BagOfWordsEmbedder(), path=tmp_path / "qdrant")


@pytest.fixture
def retriever(store):
    return Retriever(store, top_k=3)
