"""Client projects: board list, detail, creation (L3/L4), project edit (L3/L4),
editable stages (add/delete L3/L4, update L2+), member add (L2+) with
`project_added` notifications, and an activity feed."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from pymongo.database import Database

from ...core import audit
from ...core.rbac import user_level
from ...services import notifications as notif
from ...services import projects as projects_svc
from ..deps import get_current_user, get_db

router = APIRouter(tags=["projects"])


class ProjectCreate(BaseModel):
    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=200)
    client: str = ""
    team_ids: list[str] = []
    member_ids: list[str] = []
    description: str = ""
    engagement: str = ""
    priority: str = "Medium"
    project_manager_id: str | None = None
    start_date: str | None = None
    due_date: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    client: str | None = None
    description: str | None = None
    engagement: str | None = None
    priority: str | None = None
    status: str | None = None
    project_manager_id: str | None = None
    start_date: str | None = None
    due_date: str | None = None
    team_ids: list[str] | None = None


class StageCreate(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    status: str = "pending"
    progress: int = Field(default=0, ge=0, le=100)
    start_date: str | None = None
    end_date: str | None = None


class StagePatch(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    progress: int | None = Field(default=None, ge=0, le=100)
    start_date: str | None = None
    end_date: str | None = None


class MembersAdd(BaseModel):
    member_ids: list[str] = Field(min_length=1)


def _require_l3(user: dict) -> None:
    if user_level(user) < 3 and user.get("role") != "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "requires L3/L4")


def _require_l2(user: dict) -> None:
    if user_level(user) < 2 and user.get("role") != "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "requires team lead level or above")


def _get_or_404(db: Database, project_id: str) -> dict:
    p = db.projects.find_one({"project_id": project_id})
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    return p


@router.get("/projects")
def list_projects(user: dict = Depends(get_current_user),
                  db: Database = Depends(get_db)) -> list[dict]:
    return projects_svc.list_for_user(db, user)


@router.get("/projects/{project_id}")
def get_project(project_id: str, user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> dict:
    p = _get_or_404(db, project_id)
    if not projects_svc.visible_to(user, p):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a member of this project")
    return projects_svc.detail(db, project_id)


@router.post("/projects")
def create_project(body: ProjectCreate, user: dict = Depends(get_current_user),
                   db: Database = Depends(get_db)) -> dict:
    _require_l3(user)
    project = projects_svc.create(
        db, creator=user, code=body.code, name=body.name, client=body.client,
        team_ids=body.team_ids, member_ids=body.member_ids, description=body.description,
        engagement=body.engagement, priority=body.priority,
        project_manager_id=body.project_manager_id, start_date=body.start_date,
        due_date=body.due_date)
    audit.record(db, actor_id=user["user_id"], action="project_created",
                entity_type="project", entity_id=project["project_id"],
                meta={"code": body.code, "name": body.name})
    return project


@router.patch("/projects/{project_id}")
def patch_project(project_id: str, body: ProjectUpdate,
                  user: dict = Depends(get_current_user),
                  db: Database = Depends(get_db)) -> dict:
    _require_l3(user)
    _get_or_404(db, project_id)
    updated = projects_svc.update(db, project_id, body.model_dump())
    audit.record(db, actor_id=user["user_id"], action="project_updated",
                entity_type="project", entity_id=project_id,
                meta={"fields": [k for k, v in body.model_dump().items() if v is not None]})
    return updated


@router.post("/projects/{project_id}/stages")
def create_stage(project_id: str, body: StageCreate,
                 user: dict = Depends(get_current_user),
                 db: Database = Depends(get_db)) -> dict:
    _require_l3(user)
    _get_or_404(db, project_id)
    try:
        updated = projects_svc.add_stage(
            db, project_id, key=body.key, name=body.name, description=body.description,
            status=body.status, progress=body.progress, start_date=body.start_date,
            end_date=body.end_date)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    audit.record(db, actor_id=user["user_id"], action="stage_added",
                entity_type="project", entity_id=project_id, meta={"stage": body.key})
    return updated


@router.patch("/projects/{project_id}/stages/{stage_key}")
def patch_stage(project_id: str, stage_key: str, body: StagePatch,
               user: dict = Depends(get_current_user),
               db: Database = Depends(get_db)) -> dict:
    _require_l2(user)
    _get_or_404(db, project_id)
    updated = projects_svc.update_stage(db, project_id, stage_key, body.model_dump())
    if not updated:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "stage not found")
    audit.record(db, actor_id=user["user_id"], action="stage_updated",
                entity_type="project", entity_id=project_id, meta={"stage": stage_key})
    return updated


@router.delete("/projects/{project_id}/stages/{stage_key}")
def remove_stage(project_id: str, stage_key: str,
                 user: dict = Depends(get_current_user),
                 db: Database = Depends(get_db)) -> dict:
    _require_l3(user)
    _get_or_404(db, project_id)
    updated = projects_svc.delete_stage(db, project_id, stage_key)
    audit.record(db, actor_id=user["user_id"], action="stage_deleted",
                entity_type="project", entity_id=project_id, meta={"stage": stage_key})
    return updated


@router.post("/projects/{project_id}/members")
def add_members(project_id: str, body: MembersAdd,
                user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> dict:
    _require_l2(user)
    project = _get_or_404(db, project_id)
    added = projects_svc.add_members(db, project_id, body.member_ids)
    for uid in added:
        notif.create(db, recipient_id=uid, type="project_added",
                    title=f"Added to project: {project['name']}",
                    body=f"{user['name']} added you to {project['name']}",
                    action_link=f"/projects/{project_id}")
    if added:
        audit.record(db, actor_id=user["user_id"], action="project_members_added",
                    entity_type="project", entity_id=project_id, meta={"member_ids": added})
    return {"added": added}


@router.get("/projects/{project_id}/activity")
def project_activity(project_id: str, user: dict = Depends(get_current_user),
                     db: Database = Depends(get_db)) -> list[dict]:
    p = _get_or_404(db, project_id)
    if not projects_svc.visible_to(user, p):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a member of this project")
    out = []
    query = {"$or": [{"entity_type": "project", "entity_id": project_id},
                     {"meta.project_id": project_id}]}
    for a in db.audit_logs.find(query).sort("created_at", -1).limit(30):
        actor = db.users.find_one({"user_id": a.get("actor_id")}, {"name": 1})
        out.append({
            "action": a["action"], "actor_name": actor["name"] if actor else "Unknown",
            "meta": a.get("meta") or {}, "at": a.get("created_at"),
        })
    return out
