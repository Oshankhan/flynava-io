"""Client projects: board list, detail, creation (L3/L4), stage advance
(L3/L4), and member add (L2+) with `project_added` notifications."""
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


class StageUpdate(BaseModel):
    stage: str
    status: str | None = None


class MembersAdd(BaseModel):
    member_ids: list[str] = Field(min_length=1)


@router.get("/projects")
def list_projects(user: dict = Depends(get_current_user),
                  db: Database = Depends(get_db)) -> list[dict]:
    return projects_svc.list_for_user(db, user)


@router.get("/projects/{project_id}")
def get_project(project_id: str, user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> dict:
    p = db.projects.find_one({"project_id": project_id})
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    if not projects_svc.visible_to(user, p):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not a member of this project")
    return projects_svc.detail(db, project_id)


@router.post("/projects")
def create_project(body: ProjectCreate, user: dict = Depends(get_current_user),
                   db: Database = Depends(get_db)) -> dict:
    if user_level(user) < 3 and user.get("role") != "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "project creation requires L3/L4")
    project = projects_svc.create(
        db, creator=user, code=body.code, name=body.name, client=body.client,
        team_ids=body.team_ids, member_ids=body.member_ids)
    audit.record(db, actor_id=user["user_id"], action="project_created",
                entity_type="project", entity_id=project["project_id"],
                meta={"code": body.code, "name": body.name})
    return project


@router.patch("/projects/{project_id}/stage")
def update_stage(project_id: str, body: StageUpdate,
                 user: dict = Depends(get_current_user),
                 db: Database = Depends(get_db)) -> dict:
    if user_level(user) < 3 and user.get("role") != "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "stage changes require L3/L4")
    if not db.projects.find_one({"project_id": project_id}):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    try:
        updated = projects_svc.set_stage(db, project_id, body.stage, body.status)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    audit.record(db, actor_id=user["user_id"], action="project_stage_changed",
                entity_type="project", entity_id=project_id,
                meta={"stage": body.stage})
    return updated


@router.post("/projects/{project_id}/members")
def add_members(project_id: str, body: MembersAdd,
                user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> dict:
    if user_level(user) < 2 and user.get("role") != "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "team leads and above only")
    project = db.projects.find_one({"project_id": project_id}, {"name": 1})
    if not project:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    added = projects_svc.add_members(db, project_id, body.member_ids)
    for uid in added:
        notif.create(db, recipient_id=uid, type="project_added",
                    title=f"Added to project: {project['name']}",
                    body=f"{user['name']} added you to {project['name']}",
                    action_link=f"/projects/{project_id}")
    return {"added": added}
