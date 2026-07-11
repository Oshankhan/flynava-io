"""Bug status report endpoints — build a template from OpenProject bugs and
send it by email (PRD G6 automated reporting; OPS/PRD modules)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from pymongo.database import Database

from ...ai.provider import get_provider
from ...core import audit
from ...services import notifications as notif
from ...services import reports
from ..deps import get_db, require_role

router = APIRouter(tags=["reports"])
SENDERS = ("super_admin", "leadership", "manager", "team_lead")


class GenerateIn(BaseModel):
    bug_ids: list[str]
    title: str = "Bug Status Summary"
    intro: str = ""
    ai_intro: bool = False


class SendIn(BaseModel):
    bug_ids: list[str]
    recipients: list[str]
    title: str = "Bug Status Summary"
    intro: str = ""


def _ai_intro(rows: list[dict]) -> str:
    sample = "; ".join(f"{r['bug_type']}: {r['bug_name']}" for r in rows[:8])
    system = ("Write a single professional email opening line (max 2 sentences) "
              "for a bug status report. Respond as JSON with key 'answer' only.")
    user = f"The report lists {len(rows)} issues. Examples: {sample}"
    try:
        raw = get_provider().complete(system, user)
        return json.loads(raw).get("answer", "")
    except Exception:  # noqa: BLE001 - intro is optional, never fail the report
        return (f"As per your instructions, please find below the list of "
                f"{len(rows)} issue(s) with their OP IDs, assignees, and "
                f"accountable persons for your reference.")


@router.get("/reports/projects")
def projects(_: dict = Depends(require_role(*SENDERS)),
             db: Database = Depends(get_db)) -> list[dict]:
    return reports.list_projects(db)


@router.get("/reports/bugs")
def bugs(project: str, status: str | None = None, priority: str | None = None,
         _: dict = Depends(require_role(*SENDERS)),
         db: Database = Depends(get_db)) -> list[dict]:
    return reports.list_bugs(db, project, status, priority)


@router.post("/reports/generate")
def generate(body: GenerateIn, _: dict = Depends(require_role(*SENDERS)),
             db: Database = Depends(get_db)) -> dict:
    rows = reports.bugs_by_ids(db, body.bug_ids)
    if not rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no bugs selected")
    intro = body.intro or (_ai_intro(rows) if body.ai_intro else "")
    return {
        "subject": body.title,
        "intro": intro,
        "count": len(rows),
        "html": reports.render_html(body.title, intro, rows),
    }


@router.post("/reports/send")
def send(body: SendIn, user: dict = Depends(require_role(*SENDERS)),
         db: Database = Depends(get_db)) -> dict:
    rows = reports.bugs_by_ids(db, body.bug_ids)
    if not rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no bugs selected")
    html = reports.render_html(body.title, body.intro, rows)
    result = reports.send_email(body.title, html, body.recipients)
    audit.record(db, actor_id=user["user_id"], action="bug_report_" + result["status"],
                 entity_type="report",
                 meta={"count": len(rows), "recipients": body.recipients,
                       "title": body.title})
    notif.create(db, recipient_id=user["user_id"], type="report",
                 title=f"Bug report '{body.title}' {result['status']}",
                 body=result["detail"])
    return {**result, "count": len(rows), "recipients": body.recipients,
            "preview_html": html}
