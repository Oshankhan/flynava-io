"""Per-project CRM: airline account contacts (marketing-only) and billing/
invoices (finance-only). Both live under an existing project, gated
independently of the project's own membership check — a marketing L1 with
no other project access still sees contacts; a non-marketing L3 does not."""
from __future__ import annotations

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from pymongo.database import Database

from ...core import audit
from ...core.rbac import user_level, user_roles
from ..deps import get_current_user, get_db

router = APIRouter(tags=["crm"])


class ContactCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    title: str = ""
    department: str = ""
    email: str = ""
    phone: str = ""
    contact_type: str = "other"
    status: str = "active"
    last_contact: str | None = None
    notes: str = ""


class ContactUpdate(BaseModel):
    name: str | None = None
    title: str | None = None
    department: str | None = None
    email: str | None = None
    phone: str | None = None
    contact_type: str | None = None
    status: str | None = None
    last_contact: str | None = None
    notes: str | None = None


class InvoiceCreate(BaseModel):
    number: str = Field(min_length=1, max_length=60)
    date: str
    due_date: str | None = None
    amount: float = Field(ge=0)
    currency: str = "USD"
    status: str = "pending"
    description: str = ""


class InvoiceUpdate(BaseModel):
    date: str | None = None
    due_date: str | None = None
    amount: float | None = Field(default=None, ge=0)
    currency: str | None = None
    status: str | None = None
    description: str | None = None


def _require_marketing(user: dict) -> None:
    if "marketing" not in user_roles(user) and user.get("role") != "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "requires marketing access")


def _require_marketing_l2(user: dict) -> None:
    _require_marketing(user)
    if user_level(user) < 2 and user.get("role") != "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "requires marketing team lead or above")


def _require_finance(user: dict) -> None:
    if user.get("department") != "fin" and user.get("role") != "super_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "requires finance access")


def _get_project_or_404(db: Database, project_id: str) -> dict:
    p = db.projects.find_one({"project_id": project_id})
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    return p


def _contact_out(c: dict) -> dict:
    c = dict(c)
    c.pop("_id", None)
    return c


def _invoice_out(inv: dict) -> dict:
    inv = dict(inv)
    inv.pop("_id", None)
    return inv


@router.get("/projects/{project_id}/contacts")
def list_contacts(project_id: str, user: dict = Depends(get_current_user),
                  db: Database = Depends(get_db)) -> list[dict]:
    _require_marketing(user)
    _get_project_or_404(db, project_id)
    rows = db.crm_contacts.find({"project_id": project_id}).sort("name", 1)
    return [_contact_out(c) for c in rows]


@router.post("/projects/{project_id}/contacts")
def create_contact(project_id: str, body: ContactCreate,
                   user: dict = Depends(get_current_user),
                   db: Database = Depends(get_db)) -> dict:
    _require_marketing(user)
    _get_project_or_404(db, project_id)
    now = dt.datetime.now(dt.timezone.utc)
    contact = {
        "contact_id": "con_" + uuid.uuid4().hex[:8], "project_id": project_id,
        **body.model_dump(), "created_by": user["user_id"], "created_at": now,
    }
    db.crm_contacts.insert_one(contact)
    audit.record(db, actor_id=user["user_id"], action="crm_contact_added",
                entity_type="project", entity_id=project_id,
                meta={"contact_id": contact["contact_id"], "name": contact["name"]})
    return _contact_out(contact)


@router.patch("/projects/{project_id}/contacts/{contact_id}")
def update_contact(project_id: str, contact_id: str, body: ContactUpdate,
                   user: dict = Depends(get_current_user),
                   db: Database = Depends(get_db)) -> dict:
    _require_marketing(user)
    _get_project_or_404(db, project_id)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if patch:
        db.crm_contacts.update_one({"contact_id": contact_id, "project_id": project_id},
                                  {"$set": patch})
    c = db.crm_contacts.find_one({"contact_id": contact_id, "project_id": project_id})
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "contact not found")
    audit.record(db, actor_id=user["user_id"], action="crm_contact_updated",
                entity_type="project", entity_id=project_id, meta={"contact_id": contact_id})
    return _contact_out(c)


@router.delete("/projects/{project_id}/contacts/{contact_id}")
def delete_contact(project_id: str, contact_id: str,
                   user: dict = Depends(get_current_user),
                   db: Database = Depends(get_db)) -> dict:
    _require_marketing_l2(user)
    _get_project_or_404(db, project_id)
    db.crm_contacts.delete_one({"contact_id": contact_id, "project_id": project_id})
    audit.record(db, actor_id=user["user_id"], action="crm_contact_deleted",
                entity_type="project", entity_id=project_id, meta={"contact_id": contact_id})
    return {"deleted": contact_id}


@router.get("/projects/{project_id}/billing")
def get_billing(project_id: str, user: dict = Depends(get_current_user),
               db: Database = Depends(get_db)) -> dict:
    _require_finance(user)
    project = _get_project_or_404(db, project_id)
    invoices = [_invoice_out(i) for i in
               db.project_invoices.find({"project_id": project_id}).sort("date", 1)]
    invoiced = sum(i["amount"] for i in invoices)
    paid = sum(i["amount"] for i in invoices if i["status"] == "paid")
    outstanding = sum(i["amount"] for i in invoices if i["status"] != "paid")
    return {
        "contract_value": project.get("contract_value"),
        "currency": invoices[0]["currency"] if invoices else "USD",
        "invoiced": invoiced, "paid": paid, "outstanding": outstanding,
        "invoices": invoices,
    }


@router.post("/projects/{project_id}/invoices")
def create_invoice(project_id: str, body: InvoiceCreate,
                   user: dict = Depends(get_current_user),
                   db: Database = Depends(get_db)) -> dict:
    _require_finance(user)
    _get_project_or_404(db, project_id)
    now = dt.datetime.now(dt.timezone.utc)
    invoice = {
        "invoice_id": "inv_" + uuid.uuid4().hex[:8], "project_id": project_id,
        **body.model_dump(), "created_at": now,
    }
    db.project_invoices.insert_one(invoice)
    audit.record(db, actor_id=user["user_id"], action="invoice_created",
                entity_type="project", entity_id=project_id,
                meta={"invoice_id": invoice["invoice_id"], "number": invoice["number"]})
    return _invoice_out(invoice)


@router.patch("/projects/{project_id}/invoices/{invoice_id}")
def update_invoice(project_id: str, invoice_id: str, body: InvoiceUpdate,
                   user: dict = Depends(get_current_user),
                   db: Database = Depends(get_db)) -> dict:
    _require_finance(user)
    _get_project_or_404(db, project_id)
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if patch:
        db.project_invoices.update_one({"invoice_id": invoice_id, "project_id": project_id},
                                       {"$set": patch})
    inv = db.project_invoices.find_one({"invoice_id": invoice_id, "project_id": project_id})
    if not inv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invoice not found")
    audit.record(db, actor_id=user["user_id"], action="invoice_updated",
                entity_type="project", entity_id=project_id, meta={"invoice_id": invoice_id})
    return _invoice_out(inv)
