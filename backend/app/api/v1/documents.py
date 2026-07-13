"""Document Management: folders with role/team access, draft → submit →
approve workflow, sharing ("allot"), starring, and usage stats.

Flow: any user uploads into a visible folder → status `draft` (owner-only) →
owner submits → `pending` → an L3/L4 manager approves/rejects → uploader
notified. Managers (L3/L4) create folders, set their access, and share
("allot") documents to specific people. Downloads are logged (SEC-010).
"""
from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pymongo.database import Database

from ...config import settings
from ...core import audit
from ...core.rbac import user_level, user_roles
from ...services import notifications as notif
from ..deps import get_current_user, get_db

router = APIRouter(tags=["documents"])

KINDS = {"document", "mom", "policy"}
MAX_SIZE = 20 * 1024 * 1024  # 20 MB
STORAGE_QUOTA_BYTES = 50 * 1024 * 1024 * 1024  # 50 GB, display-only


class FolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    category: str = "general"
    roles: list[str] = []
    teams: list[str] = []


class FolderUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    category: str | None = None
    roles: list[str] | None = None
    teams: list[str] | None = None


class DecisionIn(BaseModel):
    comment: str = ""


class ShareIn(BaseModel):
    user_ids: list[str] = Field(min_length=1)


def _require_l3(user: dict) -> None:
    if user_level(user) < 3 and user.get("role") != "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "requires L3/L4")


def _is_manager(user: dict) -> bool:
    return user_level(user) >= 3 or user.get("role") == "super_admin"


def _folder_visible(user: dict, folder: dict) -> bool:
    if _is_manager(user):
        return True
    access = folder.get("access") or {}
    roles, teams = access.get("roles") or [], access.get("teams") or []
    if not roles and not teams:
        return True
    if any(r in roles for r in user_roles(user)):
        return True
    if user.get("team_id") in teams:
        return True
    return False


def _visible_folder_ids(db: Database, user: dict) -> set[str] | None:
    """None means "every folder" (manager) — avoids materializing a list."""
    if _is_manager(user):
        return None
    return {f["folder_id"] for f in db.folders.find({}) if _folder_visible(user, f)}


def _doc_visible(user: dict, doc: dict, visible_ids: set[str] | None) -> bool:
    # An explicit share ("allot") is a direct grant that overrides both draft
    # privacy and folder access — that's the point of allotting a document.
    if user["user_id"] in (doc.get("shared_with") or []):
        return True
    if doc.get("status") == "draft" and doc.get("uploaded_by") != user["user_id"]:
        return False
    fid = doc.get("folder_id")
    if fid is None:
        return True  # folderless (e.g. project-tab uploads) — visible to all who can see the doc
    return visible_ids is None or fid in visible_ids


def _folder_out(db: Database, f: dict) -> dict:
    access = f.get("access") or {}
    return {
        "folder_id": f["folder_id"], "name": f["name"], "description": f.get("description", ""),
        "category": f.get("category", "general"), "roles": access.get("roles") or [],
        "teams": access.get("teams") or [],
        "document_count": db.documents.count_documents({"folder_id": f["folder_id"]}),
    }


def _public(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in {"_id", "path"}}


@router.get("/folders")
def list_folders(user: dict = Depends(get_current_user),
                 db: Database = Depends(get_db)) -> list[dict]:
    return [_folder_out(db, f) for f in db.folders.find({}).sort("name", 1)
           if _folder_visible(user, f)]


@router.post("/folders")
def create_folder(body: FolderCreate, user: dict = Depends(get_current_user),
                  db: Database = Depends(get_db)) -> dict:
    _require_l3(user)
    folder = {
        "folder_id": "folder_" + uuid.uuid4().hex[:8], "name": body.name,
        "description": body.description, "category": body.category,
        "access": {"roles": body.roles, "teams": body.teams},
        "created_by": user["user_id"], "created_at": dt.datetime.now(dt.timezone.utc),
    }
    db.folders.insert_one(folder)
    audit.record(db, actor_id=user["user_id"], action="folder_created",
                entity_type="folder", entity_id=folder["folder_id"], meta={"name": body.name})
    return _folder_out(db, folder)


@router.patch("/folders/{folder_id}")
def update_folder(folder_id: str, body: FolderUpdate,
                  user: dict = Depends(get_current_user),
                  db: Database = Depends(get_db)) -> dict:
    _require_l3(user)
    folder = db.folders.find_one({"folder_id": folder_id})
    if not folder:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "folder not found")
    patch: dict = {}
    if body.name is not None:
        patch["name"] = body.name
    if body.description is not None:
        patch["description"] = body.description
    if body.category is not None:
        patch["category"] = body.category
    if body.roles is not None or body.teams is not None:
        access = folder.get("access") or {}
        patch["access"] = {
            "roles": body.roles if body.roles is not None else access.get("roles") or [],
            "teams": body.teams if body.teams is not None else access.get("teams") or [],
        }
    if patch:
        db.folders.update_one({"folder_id": folder_id}, {"$set": patch})
    audit.record(db, actor_id=user["user_id"], action="folder_updated",
                entity_type="folder", entity_id=folder_id, meta={"fields": list(patch)})
    return _folder_out(db, db.folders.find_one({"folder_id": folder_id}))


@router.post("/documents")
async def upload_document(
    title: str = Form(...),
    kind: str = Form("document"),
    folder_id: str = Form(""),
    project_id: str = Form(""),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> dict:
    if kind not in KINDS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"kind must be one of {KINDS}")
    if folder_id:
        folder = db.folders.find_one({"folder_id": folder_id})
        if not folder or not _folder_visible(user, folder):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "folder not found")
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "file too large")

    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4().hex
    suffix = Path(file.filename or "file").suffix
    stored = upload_root / f"{doc_id}{suffix}"
    stored.write_bytes(content)
    now = dt.datetime.now(dt.timezone.utc)

    doc = {
        "doc_id": doc_id, "title": title, "kind": kind,
        "folder_id": folder_id or None, "project_id": project_id or None,
        "filename": file.filename, "file_type": suffix.lstrip(".").lower() or "file",
        "size": len(content), "uploaded_by": user["user_id"], "uploaded_by_name": user["name"],
        "status": "draft", "created_at": now, "updated_at": now,
        "decided_by": None, "decided_at": None, "comment": "", "path": str(stored),
        "source": "upload", "shared_with": [], "starred_by": [], "downloads": 0,
    }
    db.documents.insert_one(doc)
    audit.record(db, actor_id=user["user_id"], action="document_uploaded",
                entity_type="document", entity_id=doc_id,
                meta={"title": title, "kind": kind, "size": len(content)})
    return _public(doc)


@router.get("/documents")
def list_documents(
    folder_id: str | None = None, project_id: str | None = None, q: str | None = None,
    file_type: str | None = None, doc_status: str | None = None, tab: str = "all",
    sort: str = "newest",
    user: dict = Depends(get_current_user), db: Database = Depends(get_db),
) -> list[dict]:
    query: dict = {}
    if folder_id:
        query["folder_id"] = folder_id
    if project_id:
        query["project_id"] = project_id
    if file_type:
        query["file_type"] = file_type
    if doc_status:
        query["status"] = doc_status
    if q:
        query["title"] = {"$regex": q, "$options": "i"}

    if tab == "mine":
        query["uploaded_by"] = user["user_id"]
    elif tab == "shared":
        query["shared_with"] = user["user_id"]
    elif tab == "starred":
        query["starred_by"] = user["user_id"]
    elif tab == "approvals":
        if not _is_manager(user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "manager access only")
        query["status"] = "pending"

    sort_field, sort_dir = {
        "newest": ("updated_at", -1), "oldest": ("updated_at", 1),
        "name": ("title", 1), "size": ("size", -1),
    }.get(sort, ("updated_at", -1))

    visible_ids = _visible_folder_ids(db, user)
    rows = db.documents.find(query).sort(sort_field, sort_dir).limit(300)
    return [_public(d) for d in rows if _doc_visible(user, d, visible_ids)]


@router.get("/documents/stats")
def document_stats(user: dict = Depends(get_current_user), db: Database = Depends(get_db)) -> dict:
    visible_ids = _visible_folder_ids(db, user)
    docs = [d for d in db.documents.find({}) if _doc_visible(user, d, visible_ids)]
    month_ago = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)
    marketing_folder_ids = {f["folder_id"] for f in db.folders.find({"category": "marketing"})}
    return {
        "total_documents": len(docs),
        "uploaded_this_month": sum(1 for d in docs if d.get("created_at") and
                                   d["created_at"].replace(tzinfo=dt.timezone.utc) > month_ago),
        "marketing_assets": sum(1 for d in docs if d.get("folder_id") in marketing_folder_ids),
        "pending_approval": sum(1 for d in docs if d.get("status") == "pending"),
        "total_downloads": sum(d.get("downloads", 0) for d in docs),
        "storage_used_bytes": sum(d.get("size", 0) for d in docs),
        "storage_quota_bytes": STORAGE_QUOTA_BYTES,
    }


def _get_owned_or_404(db: Database, doc_id: str) -> dict:
    doc = db.documents.find_one({"doc_id": doc_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "document not found")
    return doc


@router.post("/documents/{doc_id}/submit")
def submit_document(doc_id: str, user: dict = Depends(get_current_user),
                    db: Database = Depends(get_db)) -> dict:
    doc = _get_owned_or_404(db, doc_id)
    if doc["uploaded_by"] != user["user_id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "only the owner can submit this document")
    if doc["status"] != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, f"already {doc['status']}")
    now = dt.datetime.now(dt.timezone.utc)
    db.documents.update_one({"doc_id": doc_id}, {"$set": {"status": "pending", "updated_at": now}})
    for approver in db.users.find({"level": {"$gte": 3}, "status": "active"}, {"user_id": 1}):
        if approver["user_id"] != user["user_id"]:
            notif.create(db, recipient_id=approver["user_id"], type="approval_request",
                        title=f"Approval needed: {doc['title']}",
                        body=f"Submitted by {user['name']}", action_link="/documents")
    audit.record(db, actor_id=user["user_id"], action="document_submitted",
                entity_type="document", entity_id=doc_id, meta={})
    return _public(db.documents.find_one({"doc_id": doc_id}))


def _decide(db: Database, doc_id: str, user: dict, decision: str, comment: str) -> dict:
    doc = _get_owned_or_404(db, doc_id)
    if doc["status"] != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"already {doc['status']}")
    now = dt.datetime.now(dt.timezone.utc)
    db.documents.update_one({"doc_id": doc_id}, {"$set": {
        "status": decision, "decided_by": user["user_id"], "decided_at": now,
        "comment": comment, "updated_at": now,
    }})
    notif.create(db, recipient_id=doc["uploaded_by"], type="approval_decision",
                title=f"'{doc['title']}' was {decision}",
                body=comment or f"Decided by {user['name']}", action_link="/documents")
    audit.record(db, actor_id=user["user_id"], action=f"document_{decision}",
                entity_type="document", entity_id=doc_id, meta={"comment": comment})
    return _public(db.documents.find_one({"doc_id": doc_id}))


@router.post("/documents/{doc_id}/approve")
def approve(doc_id: str, body: DecisionIn, user: dict = Depends(get_current_user),
           db: Database = Depends(get_db)) -> dict:
    _require_l3(user)
    return _decide(db, doc_id, user, "approved", body.comment)


@router.post("/documents/{doc_id}/reject")
def reject(doc_id: str, body: DecisionIn, user: dict = Depends(get_current_user),
          db: Database = Depends(get_db)) -> dict:
    _require_l3(user)
    return _decide(db, doc_id, user, "rejected", body.comment)


@router.post("/documents/{doc_id}/star")
def toggle_star(doc_id: str, user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> dict:
    doc = _get_owned_or_404(db, doc_id)
    starred = doc.get("starred_by") or []
    if user["user_id"] in starred:
        db.documents.update_one({"doc_id": doc_id}, {"$pull": {"starred_by": user["user_id"]}})
        starred_now = False
    else:
        db.documents.update_one({"doc_id": doc_id}, {"$addToSet": {"starred_by": user["user_id"]}})
        starred_now = True
    return {"starred": starred_now}


@router.post("/documents/{doc_id}/share")
def share_document(doc_id: str, body: ShareIn, user: dict = Depends(get_current_user),
                   db: Database = Depends(get_db)) -> dict:
    _require_l3(user)
    doc = _get_owned_or_404(db, doc_id)
    existing = set(doc.get("shared_with") or [])
    new_ids = [u for u in body.user_ids if u not in existing]
    if new_ids:
        db.documents.update_one({"doc_id": doc_id},
                                {"$addToSet": {"shared_with": {"$each": new_ids}}})
        for uid in new_ids:
            notif.create(db, recipient_id=uid, type="document_shared",
                        title=f"Document shared: {doc['title']}",
                        body=f"{user['name']} shared this document with you",
                        action_link="/documents")
    audit.record(db, actor_id=user["user_id"], action="document_shared",
                entity_type="document", entity_id=doc_id, meta={"shared_with": new_ids})
    return {"shared": new_ids}


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str, user: dict = Depends(get_current_user),
                    db: Database = Depends(get_db)) -> dict:
    doc = _get_owned_or_404(db, doc_id)
    is_owner_draft = doc["uploaded_by"] == user["user_id"] and doc["status"] == "draft"
    if not is_owner_draft and not _is_manager(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot delete this document")
    if doc.get("path"):
        Path(doc["path"]).unlink(missing_ok=True)
    db.documents.delete_one({"doc_id": doc_id})
    audit.record(db, actor_id=user["user_id"], action="document_deleted",
                entity_type="document", entity_id=doc_id, meta={"title": doc["title"]})
    return {"status": "deleted"}


@router.get("/documents/{doc_id}/download")
def download(doc_id: str, user: dict = Depends(get_current_user),
             db: Database = Depends(get_db)) -> FileResponse:
    doc = _get_owned_or_404(db, doc_id)
    if not doc.get("path"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file not stored for demo documents")
    db.documents.update_one({"doc_id": doc_id}, {"$inc": {"downloads": 1}})
    # SEC-010: exports are logged with identity, timestamp, scope, size.
    audit.record(db, actor_id=user["user_id"], action="document_downloaded",
                entity_type="document", entity_id=doc_id,
                meta={"filename": doc["filename"], "size": doc["size"]})
    return FileResponse(doc["path"], filename=doc["filename"] or "document")
