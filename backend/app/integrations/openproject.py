"""OpenProject connector (API v3).

Auth: HTTP Basic with username `apikey` and the access token as password.
Pulls projects + ALL work packages (paginated), normalizes to IO's
project/task shape including type (Bug/Epic/...), priority, and status —
which feed the bug KPIs and the bug-status breakdown chart.
"""
from __future__ import annotations

import httpx
from pymongo.database import Database

from ..config import settings
from ..core.tls import combined_ca_bundle
from ..kpi.engine import TERMINAL_STATUSES
from .base import Connector

PAGE_SIZE = 200
MAX_PAGES = 10  # safety cap (2,000 work packages)

# KQ Project (id 48) is slated for archival on the OP side — excluded here in
# the meantime so it doesn't skew live KPIs/insights. Remove this once it's
# actually archived in OpenProject (its own `active` flag will then do the
# job via `_map_project`, same as any other archived project).
EXCLUDED_PROJECT_SOURCE_IDS = {"48"}


def _id_from_href(href: str | None) -> str | None:
    # "/api/v3/projects/12" -> "12"
    if not href:
        return None
    return href.rstrip("/").split("/")[-1]


def _link_title(links: dict, key: str) -> str | None:
    return (links.get(key) or {}).get("title")


def work_package_url(source_id: str | None) -> str | None:
    """Deep-link to a real OpenProject work package — used wherever a bug/task
    entity comes from a live sync (has a `source_id`), so an insight card or
    KPI explanation can open the actual item, not just name it."""
    if not source_id:
        return None
    return f"{settings.openproject_base_url}/work_packages/{source_id}"


class OpenProjectConnector(Connector):
    source = "openproject"

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or settings.openproject_base_url).rstrip("/")
        self.api_key = api_key or settings.openproject_api_key

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            auth=("apikey", self.api_key),
            timeout=30.0,
            headers={"Accept": "application/json"},
            # op.flynava.ai doesn't send its intermediate cert — certifi's
            # roots alone can't complete the chain (see core/tls.py).
            verify=combined_ca_bundle("godaddy_g2_intermediate.pem"),
        )

    def upsert(self, db: Database, data: dict) -> tuple[int, int]:
        fetched, processed = super().upsert(db, data)
        # OpenProject projects have no progress field — derive one so project
        # health is meaningful. Not from percentageDone: confirmed against the
        # real data (2026-07-15) that this team doesn't maintain %Done — 285 of
        # 293 Closed tasks in one project sat at 0%. Status is the real
        # completion signal: % of the project's work items in a terminal
        # status (Closed / Not a Bug / Done).
        for p in data.get("projects", []):
            sid = p["source_id"]
            tasks = list(db.tasks.find(
                {"source_system": self.source, "project_source_id": sid},
                {"status": 1}))
            if tasks:
                closed = sum(1 for t in tasks if t.get("status") in TERMINAL_STATUSES)
                pct = round(closed / len(tasks) * 100, 1)
                db.projects.update_one(
                    {"source_system": self.source, "source_id": sid},
                    {"$set": {"progress": pct}})
        return fetched, processed

    def _paged(self, client: httpx.Client, path: str,
               extra: dict | None = None) -> list[dict]:
        """Fetch every page of a collection endpoint (offset is 1-based page no)."""
        elements: list[dict] = []
        for page in range(1, MAX_PAGES + 1):
            params = {"pageSize": PAGE_SIZE, "offset": page, **(extra or {})}
            payload = client.get(path, params=params).raise_for_status().json()
            batch = payload.get("_embedded", {}).get("elements", [])
            elements.extend(batch)
            total = payload.get("total", len(elements))
            if len(elements) >= total or not batch:
                break
        return elements

    def fetch(self) -> dict:
        if not self.api_key:
            raise RuntimeError("OPENPROJECT_API_KEY not configured")
        with self._client() as c:
            projects_raw = self._paged(c, "/api/v3/projects")
            # filters=[] disables OpenProject's default open-only filter so
            # Closed/Rejected work packages are ingested too (bug closure rate).
            wp_raw = self._paged(c, "/api/v3/work_packages",
                                 extra={"filters": "[]"})
        projects_raw = [p for p in projects_raw
                       if str(p.get("id")) not in EXCLUDED_PROJECT_SOURCE_IDS]
        tasks = [self._map_task(w) for w in wp_raw]
        tasks = [t for t in tasks
                if t["project_source_id"] not in EXCLUDED_PROJECT_SOURCE_IDS]
        return {
            "projects": [self._map_project(p) for p in projects_raw],
            "tasks": tasks,
        }

    @staticmethod
    def _map_project(p: dict) -> dict:
        return {
            "source_id": str(p.get("id")),
            "name": p.get("name"),
            "status": "active" if p.get("active", True) else "archived",
        }

    @staticmethod
    def _map_task(w: dict) -> dict:
        links = w.get("_links", {})
        return {
            "source_id": str(w.get("id")),
            "title": w.get("subject"),
            "progress": w.get("percentageDone") or 0,
            "due_date": w.get("dueDate"),
            "status": _link_title(links, "status"),
            "wp_type": _link_title(links, "type"),        # Bug / Epic / Task ...
            "priority": _link_title(links, "priority"),   # Normal / High / Immediate
            "assignee": _link_title(links, "assignee"),
            "author": _link_title(links, "author"),
            "project_source_id": _id_from_href((links.get("project") or {}).get("href")),
            "created_at": w.get("createdAt"),
            "updated_at": w.get("updatedAt"),
        }
