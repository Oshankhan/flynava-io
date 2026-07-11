"""Request/approval endpoints. Routing: direct lead first (see services/approvals)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from pymongo.database import Database

from ...services import approvals
from ..deps import get_current_user, get_db

router = APIRouter(tags=["requests"])


class RequestIn(BaseModel):
    type: str
    title: str = Field(min_length=1, max_length=300)
    body: str = ""
    attachment_doc_id: str | None = None
    # Leave-only fields (required by services.approvals.submit when type=="leave")
    leave_type: str | None = None
    from_date: str | None = None
    to_date: str | None = None


class ActionIn(BaseModel):
    comment: str = ""


@router.post("/requests")
def submit_request(body: RequestIn, user: dict = Depends(get_current_user),
                   db: Database = Depends(get_db)) -> dict:
    if body.type not in approvals.REQUEST_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"type must be one of {approvals.REQUEST_TYPES}")
    try:
        return approvals.submit(db, requester=user, type=body.type,
                                title=body.title, body=body.body,
                                attachment_doc_id=body.attachment_doc_id,
                                leave_type=body.leave_type, from_date=body.from_date,
                                to_date=body.to_date)
    except approvals.LeaveRequestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/requests/my")
def my_requests(user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)) -> list[dict]:
    return approvals.mine(db, user["user_id"])


@router.get("/requests/inbox")
def approval_inbox(user: dict = Depends(get_current_user),
                   db: Database = Depends(get_db)) -> list[dict]:
    return approvals.inbox(db, user["user_id"])


def _act(db: Database, req_id: str, user: dict, action: str, comment: str) -> dict:
    if action == "forward":
        result = approvals.forward(db, req_id, user, comment)
    else:
        result = approvals.decide(db, req_id, user, action, comment)
    if not result:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "request not found, already decided, or not yours to act on")
    return result


@router.post("/requests/{req_id}/approve")
def approve(req_id: str, body: ActionIn, user: dict = Depends(get_current_user),
            db: Database = Depends(get_db)) -> dict:
    return _act(db, req_id, user, "approved", body.comment)


@router.post("/requests/{req_id}/reject")
def reject(req_id: str, body: ActionIn, user: dict = Depends(get_current_user),
           db: Database = Depends(get_db)) -> dict:
    return _act(db, req_id, user, "rejected", body.comment)


@router.post("/requests/{req_id}/forward")
def forward(req_id: str, body: ActionIn, user: dict = Depends(get_current_user),
            db: Database = Depends(get_db)) -> dict:
    return _act(db, req_id, user, "forward", body.comment)
