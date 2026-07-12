"""My/team tasks + quick task creation (Quick Links → Create Task)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from pymongo.database import Database

from ...core import audit
from ...core.rbac import user_level
from ...services import notifications as notif
from ...services import tasks as tasks_svc
from ..deps import get_current_user, get_db

router = APIRouter(tags=["tasks"])


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    assignee_id: str = ""  # empty → self
    due_date: str | None = None
    priority: str = "Normal"


@router.get("/tasks/my")
def my_tasks(user: dict = Depends(get_current_user),
             db: Database = Depends(get_db)) -> dict:
    return tasks_svc.my_tasks(db, user)


@router.get("/tasks/team")
def team_tasks(user: dict = Depends(get_current_user),
               db: Database = Depends(get_db)) -> dict:
    if user_level(user) < 2 and user.get("role") != "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "team leads and above only")
    team_id = user.get("team_id")
    if not team_id:
        # L3/L4 without a team: aggregate every team they oversee is a later
        # iteration; show the department's teams merged for now.
        teams = [t["team_id"] for t in
                 db.teams.find({"department": user.get("department")})] or \
                [t["team_id"] for t in db.teams.find()]
        bulk = tasks_svc.team_tasks_bulk(db, teams)
        merged = {"rows": [], "buckets": {"total": 0, "completed": 0,
                  "in_progress": 0, "pending": 0, "overdue": 0},
                  "reopened": [], "members": []}
        for tid in teams:
            part = bulk[tid]
            merged["rows"] += part["rows"]
            merged["reopened"] += part["reopened"]
            merged["members"] += part["members"]
            for k in merged["buckets"]:
                merged["buckets"][k] += part["buckets"][k]
        return merged
    return tasks_svc.team_tasks(db, team_id)


@router.post("/tasks")
def create_task(body: TaskCreate, user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> dict:
    assignee_id = body.assignee_id or user["user_id"]
    if assignee_id != user["user_id"]:
        # only leads+ may assign work to someone else, and only to their reports/team
        if user_level(user) < 2:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "executives can only create tasks for themselves")
        assignee = db.users.find_one({"user_id": assignee_id, "status": "active"})
        if not assignee:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "assignee not found")
        same_team = assignee.get("team_id") and \
            assignee.get("team_id") == user.get("team_id")
        reports_to_me = assignee.get("reports_to") == user["user_id"]
        if not (same_team or reports_to_me or user.get("role") == "super_admin"):
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "can only assign within your team")
    task = tasks_svc.create_task(
        db, creator=user, title=body.title, assignee_id=assignee_id,
        description=body.description, due_date=body.due_date,
        priority=body.priority)
    if assignee_id != user["user_id"]:
        notif.create(db, recipient_id=assignee_id, type="task_assigned",
                     title=f"New task: {body.title}",
                     body=f"Assigned by {user['name']}", action_link="/tasks")
    audit.record(db, actor_id=user["user_id"], action="task_created",
                 entity_type="task", entity_id=task["task_id"],
                 meta={"title": body.title, "assignee_id": assignee_id})
    return task
