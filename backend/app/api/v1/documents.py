"""Documents & MOM approval workflows (PRD G5, COM-002, scope: 'Approval
workflows for documents and MOMs').

Flow: any user uploads (document / MOM / policy) → status `pending` → approvers
(super_admin / leadership / hr) approve or reject → uploader notified → full
audit trail. Downloads are logged (SEC-010).
"""
from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pymongo.database import Database

from ...config import settings
from ...core import audit
from ...services import notifications as notif
from ..deps import get_current_user, get_db, require_role

router = APIRouter(tags=["documents"])

APPROVER_ROLES = ("super_admin", "leadership", "hr")
KINDS = {"document", "mom", "policy"}
MAX_SIZE = 20 * 1024 * 1024  # 20 MB


class DecisionIn(BaseModel):
    comment: str = ""


def _public(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in {"_id", "path"}}


@router.post("/documents")
async def upload_document(
    title: str = Form(...),
    kind: str = Form("document"),
    project_id: str = Form(""),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> dict:
    if kind not in KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"kind must be one of {KINDS}")
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large")

    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4().hex
    suffix = Path(file.filename or "file").suffix[:10]
    stored = upload_root / f"{doc_id}{suffix}"
    stored.write_bytes(content)

    doc = {
        "doc_id": doc_id,
        "title": title,
        "kind": kind,
        "project_id": project_id or None,
        "filename": file.filename,
        "size": len(content),
        "uploaded_by": user["user_id"],
        "status": "pending",
        "created_at": dt.datetime.now(dt.timezone.utc),
        "decided_by": None,
        "decided_at": None,
        "comment": "",
        "path": str(stored),
    }
    db.documents.insert_one(doc)

    # Notify every approver that a document awaits sign-off.
    for approver in db.users.find({"role": {"$in": list(APPROVER_ROLES)},
                                   "status": "active"}, {"user_id": 1}):
        if approver["user_id"] != user["user_id"]:
            notif.create(db, recipient_id=approver["user_id"], type="approval_request",
                         title=f"Approval needed: {title}",
                         body=f"{kind.upper()} uploaded by {user['name']}",
                         action_link="/documents")
    audit.record(db, actor_id=user["user_id"], action="document_uploaded",
                 entity_type="document", entity_id=doc_id,
                 meta={"title": title, "kind": kind, "size": len(content)})
    return _public(doc)


@router.get("/documents")
def list_documents(project_id: str | None = None,
                   user: dict = Depends(get_current_user),
                   db: Database = Depends(get_db)) -> list[dict]:
    query = {"project_id": project_id} if project_id else {}
    return [_public(d) for d in db.documents.find(query).sort("created_at", -1).limit(100)]


def _decide(db: Database, doc_id: str, user: dict, decision: str, comment: str) -> dict:
    doc = db.documents.find_one({"doc_id": doc_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    if doc["status"] != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"already {doc['status']}")
    now = dt.datetime.now(dt.timezone.utc)
    db.documents.update_one({"doc_id": doc_id}, {"$set": {
        "status": decision, "decided_by": user["user_id"], "decided_at": now,
        "comment": comment,
    }})
    notif.create(db, recipient_id=doc["uploaded_by"], type="approval_decision",
                 title=f"'{doc['title']}' was {decision}",
                 body=comment or f"Decided by {user['name']}",
                 action_link="/documents")
    audit.record(db, actor_id=user["user_id"], action=f"document_{decision}",
                 entity_type="document", entity_id=doc_id, meta={"comment": comment})
    updated = db.documents.find_one({"doc_id": doc_id})
    return _public(updated)


@router.post("/documents/{doc_id}/approve")
def approve(doc_id: str, body: DecisionIn,
            user: dict = Depends(require_role(*APPROVER_ROLES)),
            db: Database = Depends(get_db)) -> dict:
    return _decide(db, doc_id, user, "approved", body.comment)


@router.post("/documents/{doc_id}/reject")
def reject(doc_id: str, body: DecisionIn,
           user: dict = Depends(require_role(*APPROVER_ROLES)),
           db: Database = Depends(get_db)) -> dict:
    return _decide(db, doc_id, user, "rejected", body.comment)


@router.get("/documents/{doc_id}/download")
def download(doc_id: str, user: dict = Depends(get_current_user),
             db: Database = Depends(get_db)) -> FileResponse:
    doc = db.documents.find_one({"doc_id": doc_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    # SEC-010: exports are logged with identity, timestamp, scope, size.
    audit.record(db, actor_id=user["user_id"], action="document_downloaded",
                 entity_type="document", entity_id=doc_id,
                 meta={"filename": doc["filename"], "size": doc["size"]})
    return FileResponse(doc["path"], filename=doc["filename"] or "document")
