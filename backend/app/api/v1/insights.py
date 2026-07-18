"""Department AI insight cards — problem-statement detectors narrated into
the PRD RAG envelope (Answer/Reason/Evidence/Recommended Action/Confidence).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from pymongo.database import Database

from ...ai.provider import get_provider
from ...core import audit, rbac
from ...insights import engine as insights_engine
from ..deps import get_current_user, get_db

router = APIRouter(tags=["insights"])


def _require_dept_access(user: dict, dept: str) -> None:
    module = insights_engine.DEPT_MODULE.get(dept)
    if not module:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown department")
    if not rbac.has_any_access(user, module):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"no access to {dept} insights")


def _require_known_project(db: Database, project: str | None) -> None:
    if project and not db.projects.find_one(
            {"source_system": "openproject", "source_id": project}):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown project")


@router.get("/insights/projects")
def list_insight_projects(user: dict = Depends(get_current_user),
                          db: Database = Depends(get_db)) -> list[dict]:
    """Every OP-synced project, for the operations insights screen's project
    dropdown — unlike `/reports/projects`, not restricted to projects that
    have bugs. Gated the same as operations insights themselves."""
    _require_dept_access(user, "operations")
    out = []
    for p in db.projects.find({"source_system": "openproject"}):
        task_count = db.tasks.count_documents(
            {"source_system": "openproject", "project_source_id": p["source_id"]})
        out.append({"source_id": p["source_id"], "name": p.get("name"),
                    "task_count": task_count})
    return sorted(out, key=lambda x: -x["task_count"])


@router.get("/insights/{dept}")
def get_insights(dept: str, project: str | None = None,
                 user: dict = Depends(get_current_user),
                 db: Database = Depends(get_db)) -> dict:
    _require_dept_access(user, dept)
    _require_known_project(db, project)
    return insights_engine.run_dept(db, dept, get_provider(), user["user_id"], project=project)


@router.post("/insights/{dept}/refresh")
def refresh_insights(dept: str, project: str | None = None,
                     user: dict = Depends(get_current_user),
                     db: Database = Depends(get_db)) -> dict:
    _require_dept_access(user, dept)
    _require_known_project(db, project)
    result = insights_engine.run_dept(db, dept, get_provider(), user["user_id"],
                                      force=True, project=project)
    audit.record(db, actor_id=user["user_id"], action="insights_refresh",
                 meta={"dept": dept, "project": project, "cards": len(result["cards"])})
    return result


class FeedbackBody(BaseModel):
    insight_id: str
    useful: bool


@router.post("/insights/feedback")
def insight_feedback(body: FeedbackBody, user: dict = Depends(get_current_user),
                     db: Database = Depends(get_db)) -> dict:
    doc = db.ai_insights.find_one({"insight_id": body.insight_id})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "insight not found")
    _require_dept_access(user, doc["dept"])

    uid = user["user_id"]
    if body.useful:
        db.ai_insights.update_one(
            {"insight_id": body.insight_id},
            {"$addToSet": {"useful_by": uid}, "$pull": {"not_useful_by": uid}})
    else:
        db.ai_insights.update_one(
            {"insight_id": body.insight_id},
            {"$addToSet": {"not_useful_by": uid}, "$pull": {"useful_by": uid}})

    doc = db.ai_insights.find_one({"insight_id": body.insight_id})
    useful_by, not_useful_by = doc.get("useful_by", []), doc.get("not_useful_by", [])
    mine = True if uid in useful_by else False if uid in not_useful_by else None
    return {"insight_id": body.insight_id, "useful": len(useful_by),
            "not_useful": len(not_useful_by), "mine": mine}
