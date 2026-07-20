"""OpenProject connector (API v3).

Auth: HTTP Basic with username `apikey` and the access token as password.
Pulls projects + ALL work packages (paginated), normalizes to IO's
project/task shape including type (Bug/Epic/...), priority, and status —
which feed the bug KPIs and the bug-status breakdown chart.
"""
from __future__ import annotations

import datetime as dt
import re

import httpx
from pymongo.database import Database

from ..config import settings
from ..core.tls import combined_ca_bundle
from ..kpi.engine import TERMINAL_STATUSES
from .base import STATUS_HISTORY_CAP, _REOPEN_RE, Connector

PAGE_SIZE = 200
MAX_PAGES = 10  # safety cap (2,000 work packages)

# Verified against the real op.flynava.ai Activity API (2026-07-19, work
# package #6973): a status-change detail's `raw` text is
# "Status changed from <Old> \nto <New>" (a literal newline before "to") for
# a transition, or "Status set to <New>" for the work package's very first
# journal entry (creation). Whitespace is normalized before matching so the
# embedded newline doesn't matter.
_STATUS_CHANGE_RE = re.compile(r"Status changed from (.+?) to (.+)", re.IGNORECASE)
_STATUS_SET_RE = re.compile(r"Status set to (.+)", re.IGNORECASE)

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


def _is_reopen_transition(old: str | None, new: str) -> bool:
    """A bug bouncing OUT of a terminal status (Closed/Not a Bug/Done/...) is
    a real reopen even when the status it lands on isn't literally named
    "Reopen" — verified against real data: OpenProject bug #6973 went
    Closed -> Developed, a true reopen the literal-name check alone would
    have missed entirely."""
    if new and _REOPEN_RE.search(new):
        return True
    return bool(old and old in TERMINAL_STATUSES and new not in TERMINAL_STATUSES)


class _JournalTimeline:
    """Accumulates one work package's derived fields while walking its
    Activity journal in chronological order — kept separate from the HTTP/DB
    plumbing in `_sync_one_journal` so that method stays flat and readable."""

    def __init__(self) -> None:
        self.status_history: list[dict] = []
        self.reopen_count = 0
        self.closed_at: str | None = None
        self.closed_by: str | None = None
        self.comment_count = 0
        self.last_comment_at: str | None = None

    def add_comment(self, when: str | None) -> None:
        self.comment_count += 1
        self.last_comment_at = when

    def add_transition(self, old: str | None, new: str, when: str | None,
                       who: str | None) -> None:
        self.status_history.append({"from": old, "to": new, "at": when, "by": who})
        if _is_reopen_transition(old, new):
            self.reopen_count += 1
        if new in TERMINAL_STATUSES:
            self.closed_at, self.closed_by = when, who


def _parse_status_transitions(details: list[dict]) -> list[tuple[str | None, str]]:
    """Extract (old_status, new_status) pairs from one activity's `details`
    array. `old_status` is None for a work package's very first journal entry
    (creation: "Status set to X" — nothing to transition from)."""
    out: list[tuple[str | None, str]] = []
    for d in details:
        raw = (d.get("raw") or "").replace("\n", " ").strip()
        m = _STATUS_CHANGE_RE.search(raw)
        if m:
            out.append((m.group(1).strip(), m.group(2).strip()))
            continue
        m2 = _STATUS_SET_RE.search(raw)
        if m2:
            out.append((None, m2.group(1).strip()))
    return out


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

        try:
            self._sync_journals(db, data.get("tasks", []))
        except Exception:  # noqa: BLE001 - comment/journal enrichment must never fail the sync
            pass
        return fetched, processed

    def _sync_journals(self, db: Database, tasks: list[dict]) -> None:
        """Backfills/refreshes each work package's Activity journal (comments +
        status timeline). Sync-diffing in base.py's `upsert()` only sees a
        status change that happens BETWEEN two of our syncs — it can't know a
        bug's true historical reopen count or who closed it and when. The
        Activity API returns a work package's FULL history on every call, so
        each journal (re)sync overwrites the derived fields with the
        complete, accurate picture — the journal is the source of truth
        whenever it's available.

        Capped to `openproject_journal_batch` work packages per sync run (one
        HTTP call each); a work package only re-qualifies once its own
        `updated_at` has moved past the value recorded the last time we
        pulled its journal, so steady-state syncs only touch what changed.
        """
        if not tasks or not self.api_key:
            return
        source_ids = [t["source_id"] for t in tasks]
        synced_marks = {
            r["source_id"]: r.get("journal_synced_updated_at")
            for r in db.tasks.find(
                {"source_system": self.source, "source_id": {"$in": source_ids}},
                {"source_id": 1, "journal_synced_updated_at": 1})
        }
        candidates = [
            t for t in tasks
            if t.get("updated_at") and synced_marks.get(t["source_id"]) != t["updated_at"]
        ][: settings.openproject_journal_batch]
        if not candidates:
            return

        user_cache: dict[str, str] = {}
        with self._client() as c:
            for t in candidates:
                try:
                    self._sync_one_journal(db, c, t["source_id"], t["updated_at"], user_cache)
                except Exception:  # noqa: BLE001 - one bad work package must not stop the batch
                    continue

    def _resolve_activity_user(self, client: httpx.Client, activity: dict,
                               cache: dict[str, str]) -> str | None:
        href = (activity.get("_links", {}).get("user") or {}).get("href")
        if not href:
            return None
        uid = _id_from_href(href)
        if uid in cache:
            return cache[uid]
        # Activity-level `_links.user` is href-only (unlike work-package-level
        # links such as `assignee`, which embed a `.title`) — verified against
        # real data. One extra call per *distinct* user in a batch, cached, so
        # this stays cheap even across hundreds of activities.
        try:
            r = client.get(f"/api/v3/users/{uid}")
            r.raise_for_status()
            name = r.json().get("name") or f"User #{uid}"
        except Exception:  # noqa: BLE001
            name = f"User #{uid}"
        cache[uid] = name
        return name

    def _record_comment(self, db: Database, wp_id: str, activity: dict,
                        who: str | None, comment_raw: str) -> None:
        db.task_journals.update_one(
            {"source_system": self.source, "source_id": f"{wp_id}:{activity['id']}"},
            {"$set": {"source_system": self.source, "wp_source_id": wp_id,
                     "kind": "comment", "user": who, "created_at": activity.get("createdAt"),
                     "comment": comment_raw[:2000]}},
            upsert=True,
        )

    def _sync_one_journal(self, db: Database, client: httpx.Client, wp_id: str,
                          updated_at: str, user_cache: dict[str, str]) -> None:
        resp = client.get(f"/api/v3/work_packages/{wp_id}/activities",
                          params={"pageSize": PAGE_SIZE})
        resp.raise_for_status()
        activities = resp.json().get("_embedded", {}).get("elements", [])

        timeline = _JournalTimeline()
        for a in activities:
            who = self._resolve_activity_user(client, a, user_cache)
            when = a.get("createdAt")
            comment_raw = ((a.get("comment") or {}).get("raw") or "").strip()
            if comment_raw:
                timeline.add_comment(when)
                self._record_comment(db, wp_id, a, who, comment_raw)
            for old, new in _parse_status_transitions(a.get("details") or []):
                timeline.add_transition(old, new, when, who)

        db.tasks.update_one(
            {"source_system": self.source, "source_id": wp_id},
            {"$set": {
                "status_history": timeline.status_history[-STATUS_HISTORY_CAP:],
                "reopen_count": timeline.reopen_count,
                "closed_at": timeline.closed_at, "closed_by": timeline.closed_by,
                "comment_count": timeline.comment_count,
                "last_comment_at": timeline.last_comment_at,
                "journal_synced_updated_at": updated_at,
                "journal_synced_at": dt.datetime.now(dt.timezone.utc),
            }},
        )

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
            # Already present on every element of the bulk work_packages list
            # response (verified 2026-07-19) — no extra per-WP call needed,
            # unlike comments/journal below.
            "description": (w.get("description") or {}).get("raw") or "",
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
