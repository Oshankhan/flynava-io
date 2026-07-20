"""MongoDB access via pymongo.

Single lazily-created client. `ping()` is isolated so tests can stub it
without a live database. `get_db()` is the FastAPI dependency; tests override
it with a mongomock database.
"""
from __future__ import annotations

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database

from .config import settings

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)
    return _client


def get_db() -> Database:
    """FastAPI dependency returning the app database."""
    return get_client()[settings.mongo_db]


def ping() -> None:
    """Raise if MongoDB is unreachable."""
    get_client().admin.command("ping")


def ensure_indexes(db: Database) -> None:
    """Create indexes used across modules. Idempotent."""
    db.users.create_index([("email", ASCENDING)], unique=True)
    db.departments.create_index([("dept_id", ASCENDING)], unique=True)
    db.projects.create_index([("source_system", ASCENDING), ("source_id", ASCENDING)])
    db.tasks.create_index([("project_id", ASCENDING)])
    db.kpi_defs.create_index([("kpi_id", ASCENDING)], unique=True)
    db.kpi_values.create_index(
        [("kpi_id", ASCENDING), ("period_start", ASCENDING)]
    )
    db.integration_logs.create_index([("source", ASCENDING), ("run_at", ASCENDING)])
    db.audit_logs.create_index([("created_at", ASCENDING)])
    db.audit_logs.create_index([("actor_id", ASCENDING), ("created_at", ASCENDING)])
    db.notifications.create_index([("recipient_id", ASCENDING), ("status", ASCENDING)])
    db.teams.create_index([("team_id", ASCENDING)], unique=True)
    db.users.create_index([("team_id", ASCENDING)])
    db.users.create_index([("reports_to", ASCENDING)])
    db.tasks.create_index([("assignee", ASCENDING)])
    db.meetings.create_index([("attendee_ids", ASCENDING), ("start", ASCENDING)])
    db.requests.create_index([("approver_id", ASCENDING), ("status", ASCENDING)])
    db.requests.create_index([("requester_id", ASCENDING)])
    db.tasks.create_index([("author", ASCENDING)])
    db.leaves.create_index([("status", ASCENDING)])
    db.positions.create_index([("status", ASCENDING), ("dept", ASCENDING)])
    db.attendance.create_index([("name", ASCENDING), ("date", ASCENDING)])
    db.attendance.create_index([("date", ASCENDING)])
    db.automation_scripts.create_index([("module", ASCENDING), ("status", ASCENDING)])
    db.product_docs.create_index([("status", ASCENDING)])
    db.crm_contacts.create_index([("project_id", ASCENDING)])
    db.crm_contacts.create_index([("contact_id", ASCENDING)], unique=True)
    db.project_invoices.create_index([("project_id", ASCENDING)])
    db.project_invoices.create_index([("invoice_id", ASCENDING)], unique=True)
    db.kpi_explanations.create_index([("kpi_id", ASCENDING)], unique=True)
    db.ai_insights.create_index([("insight_id", ASCENDING)], unique=True)
    db.ai_insights.create_index([("dept", ASCENDING), ("updated_at", ASCENDING)])
    db.rag_chunks.create_index([("chunk_id", ASCENDING)], unique=True)
    db.rag_chunks.create_index([("source", ASCENDING)])
    db.task_journals.create_index(
        [("source_system", ASCENDING), ("source_id", ASCENDING)], unique=True)
    db.task_journals.create_index([("wp_source_id", ASCENDING)])
    db.traffic_daily.create_index([("date", ASCENDING)], unique=True)
    db.central_monthly.create_index([("month", ASCENDING)], unique=True)
    db.org_monthly.create_index([("month", ASCENDING)], unique=True)
    db.marketing_monthly.create_index([("month", ASCENDING)], unique=True)
    db.finance_monthly.create_index([("month", ASCENDING)], unique=True)
    db.startup_monthly.create_index([("month", ASCENDING)], unique=True)
    db.startup_daily.create_index([("date", ASCENDING)], unique=True)
    db.ops_monthly.create_index([("month", ASCENDING)], unique=True)
    db.ops_daily.create_index([("date", ASCENDING)], unique=True)
    db.milestones.create_index([("milestone_id", ASCENDING)], unique=True)
    db.forecaster_monthly.create_index([("month", ASCENDING)], unique=True)
