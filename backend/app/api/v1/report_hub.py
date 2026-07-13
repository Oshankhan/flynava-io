"""Enterprise reporting hub — report definitions, runs, scheduling, sharing,
exports, and saved views. The original bug-report builder (`reports.py` /
`services/reports.py`) is untouched and still lives at `/reports/projects`,
`/reports/bugs`, `/reports/generate`, `/reports/send`; everything here is
namespaced under `/reports/defs`, `/reports/runs`, `/reports/stats`,
`/reports/meta`, `/reports/templates`, `/reports/scheduled`, `/reports/views`
so there's no path collision.
"""
from __future__ import annotations

import datetime as dt
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from pymongo.database import Database

from ...core import audit
from ...core.rbac import user_level
from ...services import notifications as notif
from ...services import report_engine as engine
from ...services import report_store as store
from ...services import reports as reports_svc
from ...services.report_scheduler import compute_next_run
from ..deps import get_current_user, get_db

router = APIRouter(tags=["report-hub"])

_FREQS = {"daily", "weekly", "monthly", "quarterly", "yearly", "custom"}


class SectionSpec(BaseModel):
    kind: str
    params: dict = {}
    title: str | None = None


class AccessSpec(BaseModel):
    roles: list[str] = []
    teams: list[str] = []


class ReportDefCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    domain: str
    project_id: str | None = None
    type: str
    sections: list[SectionSpec] = Field(min_length=1)
    visibility: str = "private"
    access: AccessSpec = AccessSpec()
    confidential: bool = False
    allowed_user_ids: list[str] = []
    recipients: list[str] = []


class ReportDefUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    domain: str | None = None
    project_id: str | None = None
    type: str | None = None
    sections: list[SectionSpec] | None = None
    visibility: str | None = None
    access: AccessSpec | None = None
    confidential: bool | None = None
    allowed_user_ids: list[str] | None = None
    recipients: list[str] | None = None
    archived: bool | None = None


class RunIn(BaseModel):
    ai_summary: bool = False


class SendIn(BaseModel):
    recipients: list[str] = Field(min_length=1)
    message: str = ""
    run_id: str | None = None


class ShareIn(BaseModel):
    user_ids: list[str] = Field(min_length=1)


class ScheduleIn(BaseModel):
    frequency: str
    time: str = "09:00"
    weekday: int | None = None
    day_of_month: int | None = None
    every_n_days: int | None = None
    recipients: list[str] = []
    active: bool = True


class ViewIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    filters: dict = {}


def _get_visible_or_404(db: Database, user: dict, report_id: str) -> dict:
    rd = db.report_defs.find_one({"report_id": report_id})
    if not rd or not store.report_visible(user, rd):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    return rd


# --- Meta / templates / stats ---
@router.get("/reports/meta")
def meta(user: dict = Depends(get_current_user), db: Database = Depends(get_db)) -> dict:
    projects = [{"project_id": p["project_id"], "name": p["name"], "code": p["code"]}
                for p in db.projects.find({}, {"project_id": 1, "name": 1, "code": 1})]
    users = [{"user_id": u["user_id"], "name": u["name"]} for u in db.users.find({}, {"user_id": 1, "name": 1})]
    return {
        "domains": engine.DOMAINS, "types": engine.TYPES,
        "section_kinds": engine.section_catalog(user),
        "projects": projects, "users": users,
    }


@router.get("/reports/templates")
def templates(user: dict = Depends(get_current_user)) -> list[dict]:
    return engine.TEMPLATES


@router.get("/reports/stats")
def stats(user: dict = Depends(get_current_user), db: Database = Depends(get_db)) -> dict:
    visible = store.visible_defs(db, user)
    active = [rd for rd in visible if not rd.get("archived")]
    now = dt.datetime.now(dt.timezone.utc)
    month_ago = now - dt.timedelta(days=30)

    uploaded_this_month = sum(
        1 for rd in active
        if rd.get("created_at") and rd["created_at"].replace(tzinfo=dt.timezone.utc) > month_ago)
    scheduled_defs = [rd for rd in active if (rd.get("schedule") or {}).get("active")]
    scheduled_defs.sort(key=lambda rd: rd["schedule"]["next_run_at"])
    next_sched = scheduled_defs[0] if scheduled_defs else None
    shared_count = sum(1 for rd in active if rd.get("shared_with"))
    downloads = sum(rd.get("downloads", 0) for rd in active)

    report_ids = [rd["report_id"] for rd in active]
    runs_30d = list(db.report_runs.find({
        "report_id": {"$in": report_ids}, "at": {"$gte": month_ago},
        "triggered_by": {"$in": ["manual", "schedule"]},
    })) if report_ids else []
    delivered = sum(1 for r in runs_30d if r.get("delivery", {}).get("status") in ("sent", "preview"))
    delivery_pct = round(delivered / len(runs_30d) * 100, 1) if runs_30d else 100.0

    return {
        "total_reports": len(active), "total_delta_this_month": uploaded_this_month,
        "scheduled_reports": len(scheduled_defs),
        "next_schedule": ({"name": next_sched["name"], "frequency": next_sched["schedule"]["frequency"]}
                          if next_sched else None),
        "shared_reports": shared_count, "total_downloads": downloads,
        "delivery_success_pct": delivery_pct,
    }


# --- Report definitions ---
@router.get("/reports/defs")
def list_defs(
    tab: str = "all", domain: str | None = None, project_id: str | None = None,
    type: str | None = None, created_by: str | None = None, q: str | None = None,
    date_from: str | None = None, date_to: str | None = None, sort: str = "recent",
    user: dict = Depends(get_current_user), db: Database = Depends(get_db),
) -> list[dict]:
    visible = store.visible_defs(db, user)
    uid = user["user_id"]

    if tab == "my":
        rows = [rd for rd in visible if rd.get("owner_id") == uid and not rd.get("archived")]
    elif tab == "shared":
        rows = [rd for rd in visible if uid in (rd.get("shared_with") or []) and rd.get("owner_id") != uid]
    elif tab == "scheduled":
        rows = [rd for rd in visible if (rd.get("schedule") or {}).get("active") and not rd.get("archived")]
    elif tab == "archived":
        rows = [rd for rd in visible if rd.get("archived")]
    elif tab == "confidential":
        rows = [rd for rd in visible if rd.get("confidential")]
    else:
        rows = [rd for rd in visible if not rd.get("archived") and not rd.get("confidential")]

    if domain:
        rows = [rd for rd in rows if rd.get("domain") == domain]
    if project_id:
        rows = [rd for rd in rows if rd.get("project_id") == project_id]
    if type:
        rows = [rd for rd in rows if rd.get("type") == type]
    if created_by:
        rows = [rd for rd in rows if rd.get("owner_id") == created_by]
    if q:
        ql = q.lower()
        rows = [rd for rd in rows
                if ql in (rd.get("name") or "").lower() or ql in (rd.get("description") or "").lower()]
    if date_from:
        rows = [rd for rd in rows if rd.get("created_at") and rd["created_at"].date().isoformat() >= date_from]
    if date_to:
        rows = [rd for rd in rows if rd.get("created_at") and rd["created_at"].date().isoformat() <= date_to]

    shaped = store.public_many(db, rows, user)
    epoch = dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    key_fn = {
        "recent": lambda rd: rd.get("created_at") or epoch,
        "name": lambda rd: (rd.get("name") or "").lower(),
        "last_run": lambda rd: rd.get("last_run_at") or epoch,
        "downloads": lambda rd: rd.get("downloads", 0),
    }.get(sort)
    if key_fn:
        shaped.sort(key=key_fn, reverse=(sort != "name"))
    return shaped


@router.post("/reports/defs")
def create_def(body: ReportDefCreate, user: dict = Depends(get_current_user),
               db: Database = Depends(get_db)) -> dict:
    if body.domain not in engine.DOMAINS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"domain must be one of {engine.DOMAINS}")
    if body.type not in engine.TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"type must be one of {engine.TYPES}")
    if body.visibility not in ("org", "restricted", "private"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "visibility must be org, restricted, or private")
    if not store.can_create(user, body.visibility, body.confidential, has_schedule=False):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "insufficient level for this visibility/confidentiality")
    now = dt.datetime.now(dt.timezone.utc)
    rd = {
        "report_id": "rep_" + uuid.uuid4().hex[:8], "name": body.name, "description": body.description,
        "domain": body.domain, "project_id": body.project_id, "type": body.type,
        "sections": [s.model_dump() for s in body.sections],
        "visibility": body.visibility, "access": body.access.model_dump(),
        "confidential": body.confidential, "allowed_user_ids": body.allowed_user_ids,
        "shared_with": [], "recipients": body.recipients, "schedule": None,
        "owner_id": user["user_id"], "archived": False, "downloads": 0, "run_count": 0,
        "created_at": now, "updated_at": now, "seed": False,
    }
    db.report_defs.insert_one(rd)
    audit.record(db, actor_id=user["user_id"], action="report_created", entity_type="report",
                entity_id=rd["report_id"], meta={"name": body.name})
    return store.public(db, rd, user)


@router.get("/reports/defs/{report_id}")
def get_def(report_id: str, user: dict = Depends(get_current_user), db: Database = Depends(get_db)) -> dict:
    rd = _get_visible_or_404(db, user, report_id)
    return store.public(db, rd, user)


@router.patch("/reports/defs/{report_id}")
def update_def(report_id: str, body: ReportDefUpdate, user: dict = Depends(get_current_user),
               db: Database = Depends(get_db)) -> dict:
    rd = _get_visible_or_404(db, user, report_id)
    if not store.can_edit(user, rd):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot edit this report")
    patch = body.model_dump(exclude_unset=True)
    if patch:
        patch["updated_at"] = dt.datetime.now(dt.timezone.utc)
        db.report_defs.update_one({"report_id": report_id}, {"$set": patch})
    audit.record(db, actor_id=user["user_id"], action="report_updated", entity_type="report",
                entity_id=report_id, meta={"fields": list(patch)})
    return store.public(db, db.report_defs.find_one({"report_id": report_id}), user)


@router.delete("/reports/defs/{report_id}")
def delete_def(report_id: str, user: dict = Depends(get_current_user), db: Database = Depends(get_db)) -> dict:
    rd = _get_visible_or_404(db, user, report_id)
    if not store.can_delete(user, rd):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot delete this report")
    db.report_defs.delete_one({"report_id": report_id})
    db.report_runs.delete_many({"report_id": report_id})
    audit.record(db, actor_id=user["user_id"], action="report_deleted", entity_type="report",
                entity_id=report_id, meta={"name": rd["name"]})
    return {"status": "deleted"}


@router.post("/reports/defs/{report_id}/run")
def run_def(report_id: str, body: RunIn, user: dict = Depends(get_current_user),
            db: Database = Depends(get_db)) -> dict:
    rd = _get_visible_or_404(db, user, report_id)
    run_doc = engine.run_report(db, rd, user, triggered_by="manual")
    if body.ai_summary:
        summary = engine.ai_summary(rd, run_doc["sections"])
        db.report_runs.update_one({"run_id": run_doc["run_id"]}, {"$set": {"ai_summary": summary}})
        run_doc["ai_summary"] = summary
    audit.record(db, actor_id=user["user_id"], action="report_run", entity_type="report",
                entity_id=report_id, meta={"run_id": run_doc["run_id"]})
    return run_doc


@router.post("/reports/defs/{report_id}/send")
def send_def(report_id: str, body: SendIn, user: dict = Depends(get_current_user),
             db: Database = Depends(get_db)) -> dict:
    rd = _get_visible_or_404(db, user, report_id)
    if user_level(user) < 2:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "requires L2+")
    if body.run_id:
        run_doc = db.report_runs.find_one({"run_id": body.run_id, "report_id": report_id})
        if not run_doc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    else:
        run_doc = engine.run_report(db, rd, user, triggered_by="manual")
    html = engine.render_report_email_html(rd, run_doc)
    result = reports_svc.send_email(f"{rd['name']} — Report", html, body.recipients)
    for email in body.recipients:
        recipient = db.users.find_one({"email": email.lower()})
        if recipient:
            notif.create(db, recipient_id=recipient["user_id"], type="report",
                        title=f"Report shared: {rd['name']}", body=body.message or result["detail"],
                        action_link="/reports")
    db.report_runs.update_one({"run_id": run_doc["run_id"]}, {"$set": {
        "recipients": body.recipients, "delivery": {"status": result["status"], "detail": result["detail"]},
    }})
    audit.record(db, actor_id=user["user_id"], action="report_" + result["status"], entity_type="report",
                entity_id=report_id, meta={"recipients": body.recipients})
    return {**result, "run_id": run_doc["run_id"], "preview_html": html}


@router.post("/reports/defs/{report_id}/share")
def share_def(report_id: str, body: ShareIn, user: dict = Depends(get_current_user),
              db: Database = Depends(get_db)) -> dict:
    rd = _get_visible_or_404(db, user, report_id)
    if not (user["user_id"] == rd.get("owner_id") or store.is_manager(user)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot share this report")
    existing = set(rd.get("shared_with") or [])
    new_ids = [u for u in body.user_ids if u not in existing]
    if new_ids:
        db.report_defs.update_one({"report_id": report_id},
                                  {"$addToSet": {"shared_with": {"$each": new_ids}}})
        for uid in new_ids:
            notif.create(db, recipient_id=uid, type="report_shared", title=f"Report shared: {rd['name']}",
                        body=f"{user['name']} shared this report with you", action_link="/reports")
    audit.record(db, actor_id=user["user_id"], action="report_shared", entity_type="report",
                entity_id=report_id, meta={"shared_with": new_ids})
    return {"shared": new_ids}


@router.put("/reports/defs/{report_id}/schedule")
def set_schedule(report_id: str, body: ScheduleIn, user: dict = Depends(get_current_user),
                  db: Database = Depends(get_db)) -> dict:
    rd = _get_visible_or_404(db, user, report_id)
    if not store.can_edit(user, rd):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot schedule this report")
    if user_level(user) < 2:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "requires L2+")
    if body.frequency not in _FREQS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"frequency must be one of {_FREQS}")
    schedule = body.model_dump()
    schedule["next_run_at"] = compute_next_run(schedule)
    schedule["last_run_at"] = (rd.get("schedule") or {}).get("last_run_at")
    db.report_defs.update_one({"report_id": report_id},
                              {"$set": {"schedule": schedule, "updated_at": dt.datetime.now(dt.timezone.utc)}})
    audit.record(db, actor_id=user["user_id"], action="report_schedule_set", entity_type="report",
                entity_id=report_id, meta={"frequency": body.frequency})
    return store.public(db, db.report_defs.find_one({"report_id": report_id}), user)


@router.delete("/reports/defs/{report_id}/schedule")
def delete_schedule(report_id: str, user: dict = Depends(get_current_user),
                     db: Database = Depends(get_db)) -> dict:
    rd = _get_visible_or_404(db, user, report_id)
    if not store.can_edit(user, rd):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot modify this report's schedule")
    db.report_defs.update_one({"report_id": report_id}, {"$set": {"schedule": None}})
    audit.record(db, actor_id=user["user_id"], action="report_schedule_removed", entity_type="report",
                entity_id=report_id, meta={})
    return {"status": "unscheduled"}


@router.get("/reports/scheduled")
def scheduled(user: dict = Depends(get_current_user), db: Database = Depends(get_db)) -> list[dict]:
    visible = store.visible_defs(db, user)
    rows = [rd for rd in visible if (rd.get("schedule") or {}).get("active") and not rd.get("archived")]
    rows.sort(key=lambda rd: rd["schedule"]["next_run_at"])
    return store.public_many(db, rows, user)


@router.get("/reports/defs/{report_id}/runs")
def def_runs(report_id: str, limit: int = 20, user: dict = Depends(get_current_user),
             db: Database = Depends(get_db)) -> list[dict]:
    _get_visible_or_404(db, user, report_id)
    rows = list(db.report_runs.find({"report_id": report_id}, {"sections": 0})
               .sort("at", -1).limit(limit))
    for r in rows:
        r.pop("_id", None)
    return rows


@router.get("/reports/runs/{run_id}")
def get_run(run_id: str, user: dict = Depends(get_current_user), db: Database = Depends(get_db)) -> dict:
    run_doc = db.report_runs.find_one({"run_id": run_id})
    if not run_doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    _get_visible_or_404(db, user, run_doc["report_id"])
    run_doc.pop("_id", None)
    return run_doc


@router.get("/reports/runs/{run_id}/export")
def export_run(run_id: str, fmt: str = "csv", user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> Response:
    run_doc = db.report_runs.find_one({"run_id": run_id})
    if not run_doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    rd = _get_visible_or_404(db, user, run_doc["report_id"])
    if fmt == "csv":
        content, media, ext = engine.to_csv(run_doc), "text/csv", "csv"
    elif fmt == "xls":
        content, media, ext = engine.to_xls_html(run_doc), "application/vnd.ms-excel", "xls"
    elif fmt == "html":
        content, media, ext = engine.render_report_email_html(rd, run_doc), "text/html", "html"
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "fmt must be csv, xls, or html")
    db.report_defs.update_one({"report_id": rd["report_id"]}, {"$inc": {"downloads": 1}})
    audit.record(db, actor_id=user["user_id"], action="report_exported", entity_type="report",
                entity_id=rd["report_id"], meta={"fmt": fmt, "run_id": run_id})
    slug = re.sub(r"[^a-z0-9]+", "-", rd["name"].lower()).strip("-")
    return Response(content=content, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{slug}-{run_id}.{ext}"'})


# --- Saved views ---
@router.get("/reports/views")
def list_views(user: dict = Depends(get_current_user), db: Database = Depends(get_db)) -> list[dict]:
    rows = list(db.report_views.find({"user_id": user["user_id"]}).sort("created_at", -1))
    for r in rows:
        r.pop("_id", None)
    return rows


@router.post("/reports/views")
def create_view(body: ViewIn, user: dict = Depends(get_current_user), db: Database = Depends(get_db)) -> dict:
    view = {"view_id": "view_" + uuid.uuid4().hex[:8], "user_id": user["user_id"],
           "name": body.name, "filters": body.filters, "created_at": dt.datetime.now(dt.timezone.utc)}
    db.report_views.insert_one(view)
    view.pop("_id", None)
    return view


@router.delete("/reports/views/{view_id}")
def delete_view(view_id: str, user: dict = Depends(get_current_user), db: Database = Depends(get_db)) -> dict:
    res = db.report_views.delete_one({"view_id": view_id, "user_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "view not found")
    return {"status": "deleted"}
