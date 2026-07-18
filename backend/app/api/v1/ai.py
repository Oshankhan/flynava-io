"""Ask IO endpoint — RAG-backed Q&A (PRD AI-005, section 9.3)."""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pymongo.database import Database

from ...ai import rag
from ...ai.embeddings import get_embedder
from ...ai.provider import get_provider
from ...core import audit
from ...services import rag_index
from ..deps import get_db, require_module, require_role

router = APIRouter(tags=["ai"])


class HistoryTurn(BaseModel):
    q: str
    a: str = ""


class AskRequest(BaseModel):
    question: str
    history: list[HistoryTurn] | None = None


@router.post("/ai/ask")
def ask(body: AskRequest, user: dict = Depends(require_module("ai_insights")),
        db: Database = Depends(get_db)) -> dict:
    history = [t.model_dump() for t in body.history] if body.history else None
    result = rag.answer(db, body.question, get_provider(), history=history)
    audit.record(db, actor_id=user["user_id"], action="ai_ask",
                 meta={"question": body.question, "confidence": result["confidence"]})
    return result


class ReindexRequest(BaseModel):
    sources: list[str] | None = None
    force: bool = False


@router.post("/ai/reindex")
def reindex(body: ReindexRequest = ReindexRequest(),
           user: dict = Depends(require_role("super_admin")),
           db: Database = Depends(get_db)) -> dict:
    """Rebuild the semantic search index (or just the given sources). Only
    chunks whose text actually changed get re-embedded unless `force`."""
    result = rag_index.reindex(db, sources=body.sources, force=body.force)
    audit.record(db, actor_id=user["user_id"], action="ai_reindex", meta=result)
    return result


@router.get("/ai/index/status")
def index_status(user: dict = Depends(require_role("super_admin")),
                 db: Database = Depends(get_db)) -> dict:
    counts = Counter(c["source"] for c in db.rag_chunks.find({}, {"source": 1}))
    version = (db.rag_index_meta.find_one({"_id": "version"}) or {}).get("value", 0)
    return {
        "total_chunks": sum(counts.values()),
        "by_source": dict(counts),
        "index_version": version,
        "embedder": get_embedder().name,
        "available_sources": rag_index.sources(),
    }
