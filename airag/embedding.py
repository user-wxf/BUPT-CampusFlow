from functools import lru_cache
from typing import Iterable, Protocol

import numpy as np


DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
class EmbeddingError(RuntimeError):
    pass


class TextEmbedder(Protocol):
    model_name: str

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, query: str) -> list[float]:
        ...


def normalize_vector(vector: Iterable[float]) -> list[float]:
    array = np.asarray(list(vector), dtype=np.float32)
    norm = float(np.linalg.norm(array))
    if norm == 0:
        return array.tolist()
    return (array / norm).astype(float).tolist()


class FastEmbedTextEmbedder:
    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL):
        self.model_name = model_name

    @property
    def _model(self):
        return _load_fastembed_model(self.model_name)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        cleaned = [text.strip() for text in texts]
        if not cleaned:
            return []
        try:
            return [normalize_vector(vector) for vector in self._model.embed(cleaned)]
        except Exception as exc:  # pragma: no cover - depends on local model/runtime state
            raise EmbeddingError(f"Embedding failed with model {self.model_name}: {exc}") from exc

    def embed_query(self, query: str) -> list[float]:
        text = query.strip()
        if not text:
            raise EmbeddingError("Query cannot be empty")
        return self.embed_texts([text])[0]


class HashingTextEmbedder:
    """Deterministic lightweight embedder for tests and explicit fallback checks."""

    def __init__(self, dimensions: int = 96, model_name: str = "test-hashing-embedding"):
        self.dimensions = dimensions
        self.model_name = model_name

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return self._embed(query)

    def _embed(self, text: str) -> list[float]:
        vector = np.zeros(self.dimensions, dtype=np.float32)
        chars = [char for char in text.lower() if char.strip()]
        for index, char in enumerate(chars):
            vector[(ord(char) + index * 17) % self.dimensions] += 1.0
            if index < len(chars) - 1:
                pair = char + chars[index + 1]
                vector[(sum(ord(c) for c in pair) + index * 31) % self.dimensions] += 2.0
        return normalize_vector(vector)


@lru_cache(maxsize=2)
def _load_fastembed_model(model_name: str):
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise EmbeddingError("fastembed is not installed") from exc
    try:
        return TextEmbedding(model_name=model_name)
    except Exception as exc:  # pragma: no cover - environment dependent
        raise EmbeddingError(f"Cannot load embedding model {model_name}: {exc}") from exc


@lru_cache(maxsize=1)
def get_default_embedder() -> FastEmbedTextEmbedder:
    return FastEmbedTextEmbedder()
