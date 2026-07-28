"""Milestone Tracker API — dashboard, list, details, employee/department
views and reports. All derivation lives in services/milestones.py; this module
is routing, validation and the RBAC gate only.

Route ordering matters here: the literal paths (`/milestones/export`,
`/milestones/reports`, `/milestones/employees/...`, `/milestones/departments/...`)
are declared BEFORE `/milestones/{milestone_id}`, otherwise the path parameter
swallows them and `GET /milestones/export` 404s looking for a milestone with
that id.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field
from pymongo.database import Database

from ...core.rbac import user_level
from ...services import milestones as svc
from ..deps import get_current_user, get_db, has_aggregate_access

router = APIRouter(tags=["milestones"])


# --------------------------------------------------------------------------
# bodies
# --------------------------------------------------------------------------
class MilestoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    project_id: str | None = None
    department: str | None = None
    team_id: str | None = None
    owner_id: str | None = None
    manager_id: str | None = None
    category: str = "General"
    priority: str = "Medium"
    status: str = "not_started"
    start_date: str | None = None
    due_date: str | None = None
    completion_criteria: list[dict] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class MilestoneUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    project_id: str | None = None
    department: str | None = None
    team_id: str | None = None
    owner_id: str | None = None
    manager_id: str | None = None
    category: str | None = None
    priority: str | None = None
    status: str | None = None
    start_date: str | None = None
    due_date: str | None = None
    completion_criteria: list[dict] | None = None
    dependencies: list[str] | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    weightage: int = Field(default=1, ge=0, le=1000)
    status: str = "todo"
    assignee_id: str | None = None
    due_date: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    weightage: int | None = Field(default=None, ge=0, le=1000)
    status: str | None = None
    assignee_id: str | None = None
    due_date: str | None = None
    order: int | None = None


class DailyEntryCreate(BaseModel):
    task_id: str | None = None
    date: str | None = None
    hours: float = Field(default=0, ge=0, le=24)
    progress_delta: float = Field(default=0, ge=0, le=100)
    note: str = ""


class DependencyUpdate(BaseModel):
    dependencies: list[str] = Field(default_factory=list)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class DocumentLink(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: str = ""
    kind: str = "link"
    doc_id: str | None = None


class CustomReportRequest(BaseModel):
    title: str = "Custom Report"
    columns: list[str] = Field(default_factory=list)
    group_by: str | None = None
    filters: dict = Field(default_factory=dict)


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------
def _filters(
    department: str | None = None, team: str | None = None,
    project: str | None = None, category: str | None = None,
    manager: str | None = None, owner: str | None = None,
    status_: str | None = Query(default=None, alias="status"),
    priority: str | None = None, health: str | None = None,
    date_from: str | None = None, date_to: str | None = None,
    q: str | None = None,
) -> dict:
    return {"department": department, "team": team, "project": project,
            "category": category, "manager": manager, "owner": owner,
            "status": status_, "priority": priority, "health": health,
            "date_from": date_from, "date_to": date_to, "q": q}


def _require_aggregate(user: dict) -> None:
    """Company/department-wide screens. A bare "own" level (employee) sees
    only the Employee Milestones view of themselves, never these."""
    if not has_aggregate_access(user, "milestones"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no aggregate access to milestones")


def _get_or_404(db: Database, user: dict, milestone_id: str) -> dict:
    milestone = db.tracker_milestones.find_one({"milestone_id": milestone_id}, {"_id": 0})
    if not milestone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "milestone not found")
    if not svc.can_view(db, user, milestone):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no access to this milestone")
    return milestone


def _require_manage(db: Database, user: dict, milestone: dict) -> None:
    if not svc.can_manage(user, milestone):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot modify this milestone")


def _csv(name: str, columns: list[dict], rows: list[dict]) -> Response:
    return Response(
        content=svc.to_csv(columns, rows),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# --------------------------------------------------------------------------
# Screen 1 — Dashboard
# --------------------------------------------------------------------------
@router.get("/milestones/dashboard")
def dashboard(filters: dict = Depends(_filters),
              user: dict = Depends(get_current_user),
              db: Database = Depends(get_db)) -> dict:
    _require_aggregate(user)
    return svc.build_dashboard(db, user, filters)


@router.get("/milestones/filters")
def filters_meta(user: dict = Depends(get_current_user),
                 db: Database = Depends(get_db)) -> dict:
    return svc.filter_options(db, user)


# --------------------------------------------------------------------------
# Screen 6 — Reports (declared before /milestones/{milestone_id})
# --------------------------------------------------------------------------
@router.get("/milestones/reports")
def reports_catalog(user: dict = Depends(get_current_user)) -> dict:
    _require_aggregate(user)
    return svc.report_catalog()


@router.post("/milestones/reports/custom")
def custom_report(body: CustomReportRequest,
                  user: dict = Depends(get_current_user),
                  db: Database = Depends(get_db)) -> dict:
    _require_aggregate(user)
    return svc.run_custom_report(db, user, columns=body.columns,
                                 filters=body.filters, group_by=body.group_by,
                                 title=body.title)


@router.get("/milestones/reports/{report_key}")
def run_report(report_key: str, format: str = "json",
               filters: dict = Depends(_filters),
               user: dict = Depends(get_current_user),
               db: Database = Depends(get_db)):
    _require_aggregate(user)
    report = svc.run_report(db, user, report_key, filters)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown report")
    if format == "csv":
        return _csv(f"{report_key}.csv", report["columns"], report["rows"])
    return report


# --------------------------------------------------------------------------
# Screen 4 — Employee Milestones
# --------------------------------------------------------------------------
@router.get("/milestones/employees/{user_id}")
def employee_milestones(user_id: str, user: dict = Depends(get_current_user),
                        db: Database = Depends(get_db)) -> dict:
    payload = svc.employee_view(db, user, user_id)
    if payload is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "no access to this employee's milestones")
    return payload


# --------------------------------------------------------------------------
# Screen 5 — Department Dashboard
# --------------------------------------------------------------------------
@router.get("/milestones/departments")
def department_list(user: dict = Depends(get_current_user),
                    db: Database = Depends(get_db)) -> list[dict]:
    _require_aggregate(user)
    return svc.department_summaries(db, user)


@router.get("/milestones/departments/{dept_id}")
def department_dashboard(dept_id: str, filters: dict = Depends(_filters),
                         user: dict = Depends(get_current_user),
                         db: Database = Depends(get_db)) -> dict:
    _require_aggregate(user)
    payload = svc.department_view(db, user, dept_id, filters)
    if payload is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no access to this department")
    return payload


# --------------------------------------------------------------------------
# Screen 2 — Milestone List
# --------------------------------------------------------------------------
@router.get("/milestones/export")
def export_list(filters: dict = Depends(_filters),
                user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> Response:
    page = svc.list_milestones(db, user, filters, page=1, page_size=100000)
    return _csv("milestones.csv", svc.LIST_EXPORT_COLUMNS, page["items"])


@router.get("/milestones")
def list_milestones(filters: dict = Depends(_filters),
                    page: int = Query(default=1, ge=1),
                    page_size: int = Query(default=20, ge=1, le=200),
                    sort: str = "due_date", order: str = "asc",
                    user: dict = Depends(get_current_user),
                    db: Database = Depends(get_db)) -> dict:
    return svc.list_milestones(db, user, filters, page=page, page_size=page_size,
                               sort=sort, order=order)


@router.post("/milestones", status_code=status.HTTP_201_CREATED)
def create_milestone(body: MilestoneCreate,
                     user: dict = Depends(get_current_user),
                     db: Database = Depends(get_db)) -> dict:
    if not svc.can_manage(user, None):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot create milestones")
    return svc.create_milestone(db, user, body.model_dump(exclude_none=True))


# --------------------------------------------------------------------------
# Screen 3 — Milestone Details
# --------------------------------------------------------------------------
@router.get("/milestones/{milestone_id}")
def milestone_detail(milestone_id: str, user: dict = Depends(get_current_user),
                     db: Database = Depends(get_db)) -> dict:
    _get_or_404(db, user, milestone_id)
    payload = svc.get_detail(db, user, milestone_id)
    if payload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "milestone not found")
    return payload


@router.patch("/milestones/{milestone_id}")
def update_milestone(milestone_id: str, body: MilestoneUpdate,
                     user: dict = Depends(get_current_user),
                     db: Database = Depends(get_db)) -> dict:
    milestone = _get_or_404(db, user, milestone_id)
    _require_manage(db, user, milestone)
    updated = svc.update_milestone(db, user, milestone_id,
                                   body.model_dump(exclude_none=True))
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "milestone not found")
    return updated


@router.delete("/milestones/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_milestone(milestone_id: str, user: dict = Depends(get_current_user),
                     db: Database = Depends(get_db)) -> Response:
    milestone = _get_or_404(db, user, milestone_id)
    if user_level(user) < 3 and user.get("user_id") != milestone.get("owner_id"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot delete this milestone")
    svc.delete_milestone(db, milestone_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Tasks tab ---
@router.post("/milestones/{milestone_id}/tasks", status_code=status.HTTP_201_CREATED)
def add_task(milestone_id: str, body: TaskCreate,
             user: dict = Depends(get_current_user),
             db: Database = Depends(get_db)) -> dict:
    milestone = _get_or_404(db, user, milestone_id)
    _require_manage(db, user, milestone)
    return svc.add_task(db, user, milestone_id, body.model_dump(exclude_none=True))


@router.patch("/milestones/{milestone_id}/tasks/{task_id}")
def update_task(milestone_id: str, task_id: str, body: TaskUpdate,
                user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> dict:
    milestone = _get_or_404(db, user, milestone_id)
    _require_manage(db, user, milestone)
    task = svc.update_task(db, user, milestone_id, task_id,
                           body.model_dump(exclude_none=True))
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task not found")
    return task


@router.delete("/milestones/{milestone_id}/tasks/{task_id}",
               status_code=status.HTTP_204_NO_CONTENT)
def delete_task(milestone_id: str, task_id: str,
                user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> Response:
    milestone = _get_or_404(db, user, milestone_id)
    _require_manage(db, user, milestone)
    if not svc.delete_task(db, user, milestone_id, task_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Daily Success tab ---
@router.post("/milestones/{milestone_id}/daily", status_code=status.HTTP_201_CREATED)
def add_daily_entry(milestone_id: str, body: DailyEntryCreate,
                    user: dict = Depends(get_current_user),
                    db: Database = Depends(get_db)) -> dict:
    _get_or_404(db, user, milestone_id)
    return svc.add_daily_entry(db, user, milestone_id, body.model_dump(exclude_none=True))


@router.post("/milestones/{milestone_id}/daily/{entry_id}/{decision}")
def decide_daily_entry(milestone_id: str, entry_id: str, decision: str,
                       user: dict = Depends(get_current_user),
                       db: Database = Depends(get_db)) -> dict:
    if decision not in ("approve", "reject"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "decision must be approve or reject")
    milestone = _get_or_404(db, user, milestone_id)
    entry = db.milestone_daily_entries.find_one(
        {"entry_id": entry_id, "milestone_id": milestone_id}, {"_id": 0})
    if not entry:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")
    if not svc.can_approve(user, milestone, entry):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "cannot approve this entry (self-approval is never allowed)")
    result = svc.set_entry_status(db, user, milestone_id, entry_id,
                                  "approved" if decision == "approve" else "rejected")
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entry not found")
    return result


# --- Dependencies tab ---
@router.put("/milestones/{milestone_id}/dependencies")
def set_dependencies(milestone_id: str, body: DependencyUpdate,
                     user: dict = Depends(get_current_user),
                     db: Database = Depends(get_db)) -> dict:
    milestone = _get_or_404(db, user, milestone_id)
    _require_manage(db, user, milestone)
    return {"dependencies": svc.set_dependencies(db, user, milestone_id, body.dependencies)}


# --- Documents tab ---
@router.post("/milestones/{milestone_id}/documents", status_code=status.HTTP_201_CREATED)
def link_document(milestone_id: str, body: DocumentLink,
                  user: dict = Depends(get_current_user),
                  db: Database = Depends(get_db)) -> dict:
    milestone = _get_or_404(db, user, milestone_id)
    _require_manage(db, user, milestone)
    return svc.link_document(db, user, milestone_id, body.model_dump(exclude_none=True))


# --- Comments tab ---
@router.post("/milestones/{milestone_id}/comments", status_code=status.HTTP_201_CREATED)
def add_comment(milestone_id: str, body: CommentCreate,
                user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> dict:
    _get_or_404(db, user, milestone_id)
    return svc.add_comment(db, user, milestone_id, body.body)
