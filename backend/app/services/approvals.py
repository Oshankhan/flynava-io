"""Request/approval engine.

Routing rule (user decision): EVERYTHING goes to the requester's direct lead
(`reports_to`) first. The approver can approve, reject, or forward one hop up
the chain. Fallbacks when a user has no lead: department head (level 3 in the
same department), then any super_admin. Every transition notifies + audits.

Leave requests carry `leave_type`/`from_date`/`to_date`/`days` and, on
approval, write through to the HR module (services/hr.py's `leaves` +
`employees.leave_balance` — the same collections `/hr/me` reads) so approving
a leave request has a real effect, not just a status flip.
"""
from __future__ import annotations

import datetime as dt
import uuid

from pymongo.database import Database

from ..core import audit
from . import hr
from . import notifications as notif

REQUEST_TYPES = ("hr_grievance", "leave", "reimbursement", "document", "general")
LEAVE_TYPES = ("Casual", "Sick", "Earned")
TYPE_LABELS = {
    "hr_grievance": "HR Grievance",
    "leave": "Leave Request",
    "reimbursement": "Reimbursement",
    "document": "Document Approval",
    "general": "General Request",
}


def _clean(r: dict) -> dict:
    r.pop("_id", None)
    return r


def resolve_approver(db: Database, user: dict) -> str | None:
    """Direct lead → dept head → super_admin. None only if org is empty."""
    if user.get("reports_to"):
        lead = db.users.find_one({"user_id": user["reports_to"], "status": "active"})
        if lead:
            return lead["user_id"]
    head = db.users.find_one({"level": 3, "department": user.get("department"),
                              "status": "active", "user_id": {"$ne": user["user_id"]}})
    if head:
        return head["user_id"]
    admin = db.users.find_one({"role": "super_admin", "status": "active",
                               "user_id": {"$ne": user["user_id"]}})
    return admin["user_id"] if admin else None


def _names(db: Database, *user_ids: str | None) -> dict[str, str]:
    ids = [u for u in user_ids if u]
    return {u["user_id"]: u["name"]
            for u in db.users.find({"user_id": {"$in": ids}}, {"user_id": 1, "name": 1})}


class LeaveRequestError(ValueError):
    """Raised for invalid leave fields — callers map this to HTTP 400."""


def _leave_days(from_date: str, to_date: str) -> int:
    try:
        d1 = dt.date.fromisoformat(from_date)
        d2 = dt.date.fromisoformat(to_date)
    except ValueError as exc:
        raise LeaveRequestError("from_date/to_date must be YYYY-MM-DD") from exc
    if d2 < d1:
        raise LeaveRequestError("to_date must not be before from_date")
    return (d2 - d1).days + 1


def submit(db: Database, *, requester: dict, type: str, title: str,
           body: str = "", attachment_doc_id: str | None = None,
           leave_type: str | None = None, from_date: str | None = None,
           to_date: str | None = None) -> dict:
    days = None
    if type == "leave":
        if leave_type not in LEAVE_TYPES or not from_date or not to_date:
            raise LeaveRequestError(
                f"leave requests need leave_type (one of {LEAVE_TYPES}), "
                "from_date and to_date")
        days = _leave_days(from_date, to_date)

    approver_id = resolve_approver(db, requester)
    now = dt.datetime.now(dt.timezone.utc)
    req = {
        "req_id": uuid.uuid4().hex[:12],
        "type": type,
        "title": title,
        "body": body,
        "attachment_doc_id": attachment_doc_id,
        "leave_type": leave_type if type == "leave" else None,
        "from_date": from_date if type == "leave" else None,
        "to_date": to_date if type == "leave" else None,
        "days": days,
        "requester_id": requester["user_id"],
        "requester_name": requester["name"],
        "approver_id": approver_id,
        "status": "pending",
        "history": [{"by": requester["user_id"], "by_name": requester["name"],
                     "action": "submitted", "comment": "", "at": now}],
        "created_at": now,
        "decided_at": None,
    }
    db.requests.insert_one(req)
    if approver_id:
        notif.create(db, recipient_id=approver_id, type="approval_request",
                     title=f"{TYPE_LABELS.get(type, 'Request')}: {title}",
                     body=f"From {requester['name']}", action_link="/approvals")
    audit.record(db, actor_id=requester["user_id"], action="request_submitted",
                 entity_type="request", entity_id=req["req_id"],
                 meta={"type": type, "title": title, "approver_id": approver_id})
    return _clean(req)


def _load_for_approver(db: Database, req_id: str, user: dict) -> dict | None:
    req = db.requests.find_one({"req_id": req_id})
    if not req or req["status"] != "pending":
        return None
    # current approver, or a super admin, may act
    if req["approver_id"] != user["user_id"] and user.get("role") != "super_admin":
        return None
    return req


def _apply_leave_approval(db: Database, req: dict) -> dict:
    """Write an approved leave request through to HR: a leave-history row +
    a balance decrement (floored at 0 — insufficient balance doesn't block
    the approval, it's flagged in the audit meta for HR to reconcile)."""
    requester = db.users.find_one({"user_id": req["requester_id"]})
    emp = db.employees.find_one({"email": requester["email"].lower()}) \
        if requester else None
    if not emp:
        return {"applied": False, "reason": "no employee record for requester"}

    leave_type, days = req["leave_type"], req["days"]
    balance = hr.decrement_leave_balance(db, emp["emp_id"], leave_type, days)
    db.leaves.insert_one({
        "leave_id": uuid.uuid4().hex[:8], "emp_id": emp["emp_id"],
        "type": leave_type, "from": req["from_date"], "to": req["to_date"],
        "days": days, "status": "Approved",
    })
    return {"applied": True, "emp_id": emp["emp_id"], **balance}


def decide(db: Database, req_id: str, user: dict, decision: str,
           comment: str = "") -> dict | None:
    req = _load_for_approver(db, req_id, user)
    if not req:
        return None
    now = dt.datetime.now(dt.timezone.utc)
    entry = {"by": user["user_id"], "by_name": user["name"], "action": decision,
             "comment": comment, "at": now}
    db.requests.update_one({"req_id": req_id}, {
        "$set": {"status": decision, "decided_at": now},
        "$push": {"history": entry},
    })
    notif.create(db, recipient_id=req["requester_id"], type="approval_decision",
                 title=f"Your request '{req['title']}' was {decision}",
                 body=comment or f"By {user['name']}", action_link="/approvals")
    audit_meta = {"comment": comment, "title": req["title"]}
    if decision == "approved" and req.get("type") == "leave":
        audit_meta["leave"] = _apply_leave_approval(db, req)
    audit.record(db, actor_id=user["user_id"], action=f"request_{decision}",
                 entity_type="request", entity_id=req_id, meta=audit_meta)
    return _clean(db.requests.find_one({"req_id": req_id}))


def forward(db: Database, req_id: str, user: dict, comment: str = "") -> dict | None:
    req = _load_for_approver(db, req_id, user)
    if not req:
        return None
    next_id = resolve_approver(db, user)
    if not next_id or next_id == req["approver_id"]:
        return None
    now = dt.datetime.now(dt.timezone.utc)
    entry = {"by": user["user_id"], "by_name": user["name"], "action": "forwarded",
             "comment": comment, "at": now, "to": next_id}
    db.requests.update_one({"req_id": req_id}, {
        "$set": {"approver_id": next_id},
        "$push": {"history": entry},
    })
    names = _names(db, next_id)
    notif.create(db, recipient_id=next_id, type="approval_request",
                 title=f"Forwarded: {req['title']}",
                 body=f"From {req['requester_name']} via {user['name']}",
                 action_link="/approvals")
    notif.create(db, recipient_id=req["requester_id"], type="approval_update",
                 title=f"'{req['title']}' forwarded to {names.get(next_id, 'next approver')}",
                 body=comment, action_link="/approvals")
    audit.record(db, actor_id=user["user_id"], action="request_forwarded",
                 entity_type="request", entity_id=req_id,
                 meta={"to": next_id, "comment": comment, "title": req["title"]})
    return _clean(db.requests.find_one({"req_id": req_id}))


def mine(db: Database, user_id: str) -> list[dict]:
    return [_clean(r) for r in
            db.requests.find({"requester_id": user_id}).sort("created_at", -1)]


def inbox(db: Database, user_id: str) -> list[dict]:
    return [_clean(r) for r in
            db.requests.find({"approver_id": user_id, "status": "pending"})
            .sort("created_at", -1)]
