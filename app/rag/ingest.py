from dataclasses import dataclass
from pathlib import Path

from .store import VectorStore

SUPPORTED_SUFFIXES = {".md", ".txt", ".markdown"}


@dataclass
class Document:
    source: str
    text: str


def load_documents(folder: str | Path) -> list[Document]:
    root = Path(folder)
    docs: list[Document] = []
    if not root.exists():
        return docs
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            docs.append(
                Document(
                    source=path.name,
                    text=path.read_text(encoding="utf-8", errors="replace"),
                )
            )
    return docs


def chunk_text(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    size = max(50, int(size))
    overlap = max(0, min(int(overlap), size - 1))
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    units: list[str] = []
    for para in paragraphs:
        if len(para) <= size:
            units.append(para)
            continue
        step = size - overlap
        for start in range(0, len(para), step):
            window = para[start : start + size]
            units.append(window)
            if start + size >= len(para):
                break
    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit
        if len(candidate) <= size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = unit
    if current:
        chunks.append(current)
    return chunks


def ingest_documents(
    store: VectorStore, folder: str | Path, size: int, overlap: int, batch_size: int = 100
) -> dict:
    documents = load_documents(folder)
    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict] = []
    for doc in documents:
        for i, chunk in enumerate(chunk_text(doc.text, size, overlap)):
            ids.append(f"{doc.source}::{i}")
            texts.append(chunk)
            metadatas.append({"source": doc.source})
    store.reset()
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        store.upsert(ids[start:end], texts[start:end], metadatas[start:end])
    return {"files": len(documents), "chunks": len(ids)}
