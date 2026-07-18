"""In-process cosine-similarity search over the `rag_chunks` collection.

At IO's corpus size (low thousands of chunks) this beats a network hop to any
vector database: one Mongo read into a NumPy matrix, cached in-process and
reused until `services/rag_index.reindex()` bumps the version counter in
`rag_index_meta`. The search surface (`search(...)`) is intentionally the
only thing callers touch — swapping in Atlas `$vectorSearch` or a dedicated
vector DB later is a same-signature class swap, not a caller rewrite (worth
doing well past ~50k chunks; not before).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pymongo.database import Database


@dataclass
class Hit:
    chunk_id: str
    source: str
    text: str
    meta: dict
    score: float


class MongoVectorStore:
    def __init__(self) -> None:
        # Keyed by (db identity, version) rather than version alone: two
        # different Database instances (e.g. separate mongomock DBs in
        # tests) can easily land on the same small version integer, which
        # would otherwise serve one test's cached matrix to another's query.
        self._cache_key: tuple[int, int] | None = None
        self._ids: list[str] = []
        self._sources: list[str] = []
        self._texts: list[str] = []
        self._metas: list[dict] = []
        self._matrix: np.ndarray | None = None

    def _current_version(self, db: Database) -> int:
        row = db.rag_index_meta.find_one({"_id": "version"})
        return row["value"] if row else 0

    def _load(self, db: Database) -> None:
        rows = list(db.rag_chunks.find(
            {}, {"chunk_id": 1, "source": 1, "text": 1, "meta": 1, "embedding": 1}))
        self._ids = [r["chunk_id"] for r in rows]
        self._sources = [r["source"] for r in rows]
        self._texts = [r["text"] for r in rows]
        self._metas = [r.get("meta", {}) for r in rows]
        self._matrix = (np.array([r["embedding"] for r in rows], dtype=np.float32)
                        if rows else np.zeros((0, 1), dtype=np.float32))

    def search(self, db: Database, query_vec: list[float], k: int = 10,
              min_score: float = 0.0, sources: list[str] | None = None) -> list[Hit]:
        """Cosine top-k. Reloads the in-memory matrix only when the stored
        index version has changed since last load (i.e. after a reindex)."""
        key = (id(db), self._current_version(db))
        if self._cache_key != key:
            self._load(db)
            self._cache_key = key
        if self._matrix is None or self._matrix.shape[0] == 0:
            return []

        q = np.array(query_vec, dtype=np.float32)
        q_norm = float(np.linalg.norm(q)) or 1.0
        m_norms = np.linalg.norm(self._matrix, axis=1)
        m_norms[m_norms == 0] = 1.0
        sims = (self._matrix @ q) / (m_norms * q_norm)

        order = np.argsort(-sims)
        hits: list[Hit] = []
        for i in order:
            if sources and self._sources[i] not in sources:
                continue
            score = float(sims[i])
            if score < min_score:
                break
            hits.append(Hit(self._ids[i], self._sources[i], self._texts[i], self._metas[i], score))
            if len(hits) >= k:
                break
        return hits


_store = MongoVectorStore()


def get_store() -> MongoVectorStore:
    return _store
