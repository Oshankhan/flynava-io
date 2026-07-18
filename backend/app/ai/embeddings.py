"""Pluggable embedder (mirrors `ai/provider.py`'s LLM pattern).

`get_embedder()` auto-selects: `FastEmbedEmbedder` (local ONNX model, free,
no network calls after the first download) when `settings.rag_embeddings_enabled`
and the `fastembed` package is importable; otherwise `HashingEmbedder` — a
deterministic, dependency-free fallback so the app, and every test, still run
with zero setup and zero network access. Swapping the underlying model is one
env var; swapping the provider is one class — same shape as `ai/provider.py`.
"""
from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod

from ..config import settings


class Embedder(ABC):
    name: str
    dim: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


class HashingEmbedder(Embedder):
    """No external model, no network. A deterministic bag-of-hashed-tokens
    vector — not semantically strong, but exact-keyword recall works and it
    never requires a download, a GPU, or an API key. Used by every test and
    as the safety net if fastembed is unavailable."""

    name = "hashing"
    dim = 256

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in text.lower().split():
            h = int(hashlib.sha1(tok.encode("utf-8")).hexdigest(), 16)
            v[h % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]


class FastEmbedEmbedder(Embedder):
    """BAAI/bge-small-en-v1.5 via `fastembed` — local ONNX Runtime inference,
    ~34MB quantized model, no torch, no API key. First call downloads the
    model to a local cache; every call after that is offline."""

    name = "fastembed"
    dim = 384

    def __init__(self) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=settings.rag_embed_model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(texts)]


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """Process-wide singleton — loading the ONNX model is the expensive part,
    do it once. `reset_embedder()` (tests only) clears it so settings changes
    take effect."""
    global _embedder
    if _embedder is not None:
        return _embedder
    if settings.rag_embeddings_enabled:
        try:
            _embedder = FastEmbedEmbedder()
            return _embedder
        except Exception:  # noqa: BLE001 - missing package / model download failure -> fallback
            pass
    _embedder = HashingEmbedder()
    return _embedder


def reset_embedder() -> None:
    global _embedder
    _embedder = None
