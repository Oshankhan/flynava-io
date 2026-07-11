"""Ask IO endpoint — RAG-backed Q&A (PRD AI-005, section 9.3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pymongo.database import Database

from ...ai import rag
from ...ai.provider import get_provider
from ...core import audit
from ..deps import get_db, require_module

router = APIRouter(tags=["ai"])


class AskRequest(BaseModel):
    question: str


@router.post("/ai/ask")
def ask(body: AskRequest, user: dict = Depends(require_module("ai_insights")),
        db: Database = Depends(get_db)) -> dict:
    result = rag.answer(db, body.question, get_provider())
    audit.record(db, actor_id=user["user_id"], action="ai_ask",
                 meta={"question": body.question, "confidence": result["confidence"]})
    return result
