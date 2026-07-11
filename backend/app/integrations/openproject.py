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
from ..core.tls import use_os_trust_store
from .base import Connector

PAGE_SIZE = 200
MAX_PAGES = 10  # safety cap (2,000 work packages)


def _id_from_href(href: str | None) -> str | None:
    # "/api/v3/projects/12" -> "12"
    if not href:
        return None
    return href.rstrip("/").split("/")[-1]


def _link_title(links: dict, key: str) -> str | None:
    return (links.get(key) or {}).get("title")


class OpenProjectConnector(Connector):
    source = "openproject"

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or settings.openproject_base_url).rstrip("/")
        self.api_key = api_key or settings.openproject_api_key

    def _client(self) -> httpx.Client:
        use_os_trust_store()  # verify against the OS cert store (chain fix)
        return httpx.Client(
            base_url=self.base_url,
            auth=("apikey", self.api_key),
            timeout=30.0,
            headers={"Accept": "application/json"},
        )

    def upsert(self, db: Database, data: dict) -> tuple[int, int]:
        fetched, processed = super().upsert(db, data)
        # OpenProject projects have no progress field — derive it from the mean
        # percentageDone of their work packages so project health is meaningful.
        for p in data.get("projects", []):
            sid = p["source_id"]
            tasks = list(db.tasks.find(
                {"source_system": self.source, "project_source_id": sid},
                {"progress": 1}))
            if tasks:
                avg = round(sum(t.get("progress") or 0 for t in tasks) / len(tasks), 1)
                db.projects.update_one(
                    {"source_system": self.source, "source_id": sid},
                    {"$set": {"progress": avg}})
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
        return {
            "projects": [self._map_project(p) for p in projects_raw],
            "tasks": [self._map_task(w) for w in wp_raw],
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
        }
