import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .embedding import DEFAULT_EMBEDDING_MODEL, TextEmbedder, get_default_embedder
from .retrieval import DEFAULT_CHUNKS_PATH, filter_by_metadata, load_chunks


DEFAULT_VECTOR_DB_DIR = Path(__file__).resolve().parent / "vector_db"
DEFAULT_VECTOR_DB_PATH = DEFAULT_VECTOR_DB_DIR / "chunks.json"
VECTOR_DB_VERSION = 1


class VectorStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class VectorSearchResult:
    chunk: dict[str, Any]
    score: float


def chunk_text(chunk: dict[str, Any]) -> str:
    return "\n".join(
        str(chunk.get(field) or "").strip()
        for field in ("service", "title", "content")
        if str(chunk.get(field) or "").strip()
    )


def build_vector_db(
    chunks_path: str | Path = DEFAULT_CHUNKS_PATH,
    db_path: str | Path = DEFAULT_VECTOR_DB_PATH,
    embedder: TextEmbedder | None = None,
) -> dict[str, Any]:
    chunks = load_chunks(chunks_path)
    active_chunks = [chunk for chunk in chunks if chunk.get("status") == "active"]
    selected_embedder = embedder or get_default_embedder()
    embeddings = selected_embedder.embed_texts([chunk_text(chunk) for chunk in active_chunks])
    if len(embeddings) != len(active_chunks):
        raise VectorStoreError("Embedding count does not match chunk count")

    records = []
    for chunk, embedding in zip(active_chunks, embeddings):
        records.append(
            {
                "id": chunk["chunk_id"],
                "chunk": chunk,
                "metadata": {
                    key: chunk.get(key)
                    for key in (
                        "chunk_id",
                        "document_id",
                        "service",
                        "title",
                        "college",
                        "grade",
                        "education_level",
                        "campus",
                        "source",
                        "source_pages",
                        "status",
                    )
                },
                "embedding": embedding,
            }
        )

    payload = {
        "version": VECTOR_DB_VERSION,
        "model": selected_embedder.model_name,
        "chunk_count": len(records),
        "records": records,
    }
    output_path = Path(db_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(output_path), "model": selected_embedder.model_name, "chunk_count": len(records)}


class LocalVectorStore:
    def __init__(
        self,
        db_path: str | Path = DEFAULT_VECTOR_DB_PATH,
        embedder: TextEmbedder | None = None,
    ):
        self.db_path = Path(db_path)
        self.embedder = embedder or get_default_embedder()
        self._payload: dict[str, Any] | None = None

    @property
    def ready(self) -> bool:
        return self.db_path.exists()

    def load(self) -> dict[str, Any]:
        if self._payload is not None:
            return self._payload
        if not self.db_path.exists():
            raise VectorStoreError(f"Vector DB not found: {self.db_path}")
        try:
            payload = json.loads(self.db_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise VectorStoreError(f"Vector DB is not valid JSON: {exc.msg}") from exc
        if payload.get("version") != VECTOR_DB_VERSION:
            raise VectorStoreError("Vector DB version is not supported")
        if payload.get("model") != self.embedder.model_name:
            raise VectorStoreError(
                f"Vector DB model {payload.get('model')} does not match embedder {self.embedder.model_name}"
            )
        records = payload.get("records")
        if not isinstance(records, list):
            raise VectorStoreError("Vector DB records are missing")
        self._payload = payload
        return payload

    def count(self) -> int:
        if not self.ready:
            return 0
        try:
            return int(self.load().get("chunk_count") or 0)
        except VectorStoreError:
            return 0

    def search(self, question: str, profile: dict[str, str], top_k: int = 5) -> list[VectorSearchResult]:
        payload = self.load()
        records = payload["records"]
        filtered = filter_by_metadata([record["chunk"] for record in records], profile)
        allowed_ids = {chunk["chunk_id"] for chunk in filtered}
        candidates = [record for record in records if record["id"] in allowed_ids]
        if not candidates:
            return []

        query_embedding = np.asarray(self.embedder.embed_query(question), dtype=np.float32)
        query_norm = float(np.linalg.norm(query_embedding))
        if query_norm == 0:
            return []
        results: list[VectorSearchResult] = []
        for record in candidates:
            vector = np.asarray(record["embedding"], dtype=np.float32)
            norm = float(np.linalg.norm(vector))
            if norm == 0:
                continue
            score = float(np.dot(query_embedding, vector) / (query_norm * norm))
            results.append(VectorSearchResult(chunk=record["chunk"], score=score))
        results.sort(key=lambda item: (-item.score, str(item.chunk.get("chunk_id") or "")))
        return results[:top_k]


def vector_db_status(db_path: str | Path = DEFAULT_VECTOR_DB_PATH) -> dict[str, Any]:
    path = Path(db_path)
    if not path.exists():
        return {
            "ready": False,
            "path": str(path),
            "model": DEFAULT_EMBEDDING_MODEL,
            "chunks": 0,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"ready": False, "path": str(path), "model": DEFAULT_EMBEDDING_MODEL, "chunks": 0}
    return {
        "ready": payload.get("version") == VECTOR_DB_VERSION,
        "path": str(path),
        "model": payload.get("model") or DEFAULT_EMBEDDING_MODEL,
        "chunks": int(payload.get("chunk_count") or 0),
    }
