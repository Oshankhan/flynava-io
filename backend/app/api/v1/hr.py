"""HR module endpoints — employee directory, self-service payslip/leaves, and
the biometric attendance ERP (upload → store → email)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel
from pymongo.database import Database

from ...core import audit
from ...services import hr
from ...services import notifications as notif
from ...services.reports import send_email
from ..deps import get_current_user, get_db, require_role

router = APIRouter(tags=["hr"])
HR_ROLES = ("super_admin", "leadership", "hr")


class LeaveDecisionIn(BaseModel):
    comment: str = ""


def require_hr_access(user: dict = Depends(get_current_user)) -> dict:
    """HR admins, or the HR team lead (who runs day-to-day leave admin)."""
    if user["role"] in HR_ROLES or \
            (user["role"] == "team_lead" and user.get("department") == "hr"):
        return user
    raise HTTPException(status.HTTP_403_FORBIDDEN, "HR access required")


class AttendanceSend(BaseModel):
    upload_id: str
    recipients: list[str]
    title: str = "Daily Attendance Report"


# --- Directory (HR/leadership/admin) ---
@router.get("/hr/employees")
def employees(_: dict = Depends(require_role(*HR_ROLES)),
              db: Database = Depends(get_db)) -> list[dict]:
    return hr.list_employees(db)


@router.get("/hr/employees/{emp_id}")
def employee(emp_id: str, _: dict = Depends(require_role(*HR_ROLES)),
             db: Database = Depends(get_db)) -> dict:
    e = hr.get_employee(db, emp_id)
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "employee not found")
    return e


# --- Self-service (any authenticated user) ---
@router.get("/hr/me")
def my_record(user: dict = Depends(get_current_user),
              db: Database = Depends(get_db)) -> dict:
    e = hr.employee_by_email(db, user["email"])
    if not e:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "no employee record linked to your account")
    return e


# --- Pending Leaves queue (HR admins + HR team lead) ---
@router.get("/hr/leaves")
def pending_leaves(_: dict = Depends(require_hr_access),
                   db: Database = Depends(get_db)) -> list[dict]:
    return hr.list_pending_leaves(db)


def _decide_leave(db: Database, leave_id: str, user: dict, decision: str,
                  comment: str) -> dict:
    result = hr.decide_leave(db, leave_id, decision)
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "leave not found or already decided")
    audit.record(db, actor_id=user["user_id"], action=f"leave_{decision.lower()}",
                 entity_type="leave", entity_id=leave_id,
                 meta={**result, "comment": comment})
    emp = db.employees.find_one({"emp_id": result["emp_id"]}, {"email": 1})
    owner = db.users.find_one({"email": emp["email"]}, {"user_id": 1}) if emp else None
    if owner:
        notif.create(db, recipient_id=owner["user_id"], type="leave_decision",
                     title=f"Your leave request was {decision.lower()}",
                     body=comment, action_link="/my-payslip")
    return result


@router.post("/hr/leaves/{leave_id}/approve")
def approve_leave(leave_id: str, body: LeaveDecisionIn,
                  user: dict = Depends(require_hr_access),
                  db: Database = Depends(get_db)) -> dict:
    return _decide_leave(db, leave_id, user, "Approved", body.comment)


@router.post("/hr/leaves/{leave_id}/reject")
def reject_leave(leave_id: str, body: LeaveDecisionIn,
                 user: dict = Depends(require_hr_access),
                 db: Database = Depends(get_db)) -> dict:
    return _decide_leave(db, leave_id, user, "Rejected", body.comment)


# --- Attendance ERP ---
@router.get("/hr/attendance/sample")
def sample(_: dict = Depends(require_role(*HR_ROLES)),
           db: Database = Depends(get_db)) -> Response:
    return Response(
        content=hr.sample_csv(db), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=biometric_sample.csv"})


@router.post("/hr/attendance/upload")
async def upload_attendance(file: UploadFile = File(...),
                            user: dict = Depends(require_role(*HR_ROLES)),
                            db: Database = Depends(get_db)) -> dict:
    raw = await file.read()
    rows = hr.parse_attendance(raw)
    if not rows:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "no attendance rows found — check the CSV columns")
    result = hr.store_attendance(db, rows, user["user_id"], file.filename or "upload.csv")
    audit.record(db, actor_id=user["user_id"], action="attendance_upload",
                 entity_type="attendance", entity_id=result["upload_id"],
                 meta={"rows": result["rows"]})
    return result


@router.post("/hr/attendance/send")
def send_attendance(body: AttendanceSend, user: dict = Depends(require_role(*HR_ROLES)),
                    db: Database = Depends(get_db)) -> dict:
    rows = [hr._clean(r) for r in db.attendance.find({"upload_id": body.upload_id})]
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "upload not found")
    summary = hr._summary(rows)
    html = hr.render_attendance_html(body.title, rows, summary)
    result = send_email(body.title, html, body.recipients)
    audit.record(db, actor_id=user["user_id"], action="attendance_" + result["status"],
                 entity_type="attendance", entity_id=body.upload_id,
                 meta={"recipients": body.recipients, "rows": len(rows)})
    notif.create(db, recipient_id=user["user_id"], type="attendance",
                 title=f"Attendance report {result['status']}", body=result["detail"])
    return {**result, "count": len(rows), "summary": summary, "preview_html": html}
