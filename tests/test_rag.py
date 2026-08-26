from app.rag.ingest import chunk_text, ingest_documents


def test_chunks_respect_max_size():
    text = "\n\n".join(["word " * 80] * 6)
    chunks = chunk_text(text, size=600, overlap=50)
    assert len(chunks) >= 2
    assert all(len(c) <= 600 for c in chunks)


def test_long_paragraph_windows_overlap():
    text = " ".join(f"tok{i}" for i in range(400))
    chunks = chunk_text(text, size=200, overlap=40)
    assert len(chunks) >= 3
    assert all(len(c) <= 200 for c in chunks)


def test_short_text_single_chunk():
    assert chunk_text("hello world", size=900) == ["hello world"]


def test_empty_text_no_chunks():
    assert chunk_text("", size=900) == []


def test_ingest_and_retrieve_roundtrip(store, retriever, tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "alpha.md").write_text(
        "Alpha document about quantum entanglement physics.\n\nSpooky action at a distance."
    )
    (docs_dir / "beta.md").write_text(
        "Beta document about baking sourdough bread.\n\nYeast flour water time."
    )
    stats = ingest_documents(store, docs_dir, size=400, overlap=50)
    assert stats["files"] == 2
    assert stats["chunks"] >= 2

    hits = retriever.retrieve("quantum entanglement physics")
    assert hits and hits[0]["source"] == "alpha.md"

    block, sources = retriever.context_block("quantum entanglement")
    assert "alpha.md" in block
    assert sources[0].source == "alpha.md"
    assert sources[0].score is not None


def test_ingest_empty_folder(store, tmp_path):
    stats = ingest_documents(store, tmp_path / "missing", size=400, overlap=50)
    assert stats == {"files": 0, "chunks": 0}
    assert store.count() == 0
