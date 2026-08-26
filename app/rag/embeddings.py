import logging

logger = logging.getLogger(__name__)


class SentenceTransformerEmbedder:
    """Explicit, swappable embedder backed by sentence-transformers.

    The model loads lazily on first use so app startup and tests stay fast;
    production ingestion/retrieval triggers the real load.
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            logger.info("loading embedding model %s", self.model_name)
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dim(self) -> int:
        return int(self._load().get_sentence_embedding_dimension())

    def __call__(self, input: list[str]) -> list[list[float]]:
        model = self._load()
        return model.encode(input, normalize_embeddings=True).tolist()
