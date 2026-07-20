"""Chunk builders + incremental embedding index for Ask IO's semantic recall.

Mirrors `kpi/engine.py`'s `@computer` registry pattern: each `@chunk_source`
is a plain `(db) -> list[dict]` function returning the CURRENT set of chunks
for one Mongo collection. `reindex()` diffs each chunk's content hash against
what's already stored in `rag_chunks` — only new or changed text gets
re-embedded — then prunes chunks whose source row no longer exists. Safe (and
cheap, once initially warm) to call as often as you like; `services/ingest.py`
calls it after every successful OpenProject sync.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
from typing import Callable

from pymongo.database import Database

from ..ai.embeddings import get_embedder
from ..config import settings
from ..integrations.openproject import work_package_url

ChunkBuilder = Callable[[Database], list[dict]]
_BUILDERS: dict[str, ChunkBuilder] = {}
_UNKNOWN_PROJECT = "an unknown project"


def chunk_source(name: str):
    def wrap(fn: ChunkBuilder) -> ChunkBuilder:
        _BUILDERS[name] = fn
        return fn

    return wrap


def sources() -> list[str]:
    return list(_BUILDERS)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk(source: str, source_id: str, text: str, meta: dict | None = None) -> dict:
    return {
        "chunk_id": f"{source}:{source_id}",
        "source": source,
        "source_id": str(source_id),
        "text": text,
        "meta": meta or {},
        "content_hash": _hash(text),
    }


def _project_names(db: Database) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in db.projects.find({}, {"source_id": 1, "project_id": 1, "name": 1}):
        for key in (p.get("source_id"), p.get("project_id")):
            if key:
                out[str(key)] = p.get("name", "")
    return out


_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def _clean_description(raw: str, cap: int = 500) -> str:
    """Strip markdown image tags (attachment links, not useful as text) and
    collapse whitespace before truncating — OP descriptions are markdown."""
    text = _MD_IMAGE_RE.sub("", raw or "")
    return " ".join(text.split())[:cap]


def _task_chunk(t: dict, pnames: dict[str, str]) -> dict | None:
    tid = t.get("source_id") or t.get("task_id")
    title = t.get("title")
    if not tid or not title:
        return None
    pid = t.get("project_source_id") or t.get("project_id")
    pname = pnames.get(str(pid), _UNKNOWN_PROJECT)
    who = t.get("assignee") or t.get("assignee_id") or "Unassigned"
    wp = t.get("wp_type") or "Item"
    due = f", due {t['due_date']}" if t.get("due_date") else ""
    # Real OP-synced items get their deep link folded right into the text —
    # so it's part of what both the LLM sees (it can quote the link in its
    # prose answer) and what the frontend can auto-linkify out of the
    # evidence bullets.
    url = work_package_url(t.get("source_id"))
    link = f" Link: {url}" if url else ""
    description = _clean_description(t.get("description") or "")
    desc_bit = f' Description: "{description}"' if description else ""
    text = (f'{wp} in {pname}: "{title}" — status {t.get("status")}, '
           f'priority {t.get("priority") or "Normal"}, assignee {who}{due}.'
           f'{desc_bit}{link}')
    return _chunk("tasks", tid, text,
                 {"project": pname, "status": t.get("status"), "wp_type": wp, "url": url})


@chunk_source("tasks")
def _tasks(db: Database) -> list[dict]:
    pnames = _project_names(db)
    rows = db.tasks.find({}, {"title": 1, "wp_type": 1, "status": 1, "priority": 1,
                              "assignee": 1, "assignee_id": 1, "project_id": 1,
                              "project_source_id": 1, "task_id": 1, "source_id": 1,
                              "due_date": 1, "description": 1})
    chunks = (_task_chunk(t, pnames) for t in rows)
    return [c for c in chunks if c is not None]


@chunk_source("task_comments")
def _task_comments(db: Database) -> list[dict]:
    """One chunk per real OpenProject comment, pulled from the Activity
    journal (`integrations/openproject.py`'s `_sync_journals`) rather than
    just a work package's title — comments are where the actual bug context,
    retest notes, and closure reasoning live. Capped to the most recent
    `openproject_journal_comment_cap` comments per work package so a heavily-
    discussed bug doesn't crowd out everything else in the index."""
    pnames = _project_names(db)
    task_meta = {
        str(t.get("source_id")): t
        for t in db.tasks.find({"source_system": "openproject"},
                               {"source_id": 1, "title": 1, "wp_type": 1,
                                "project_source_id": 1})
    }
    by_wp: dict[str, list[dict]] = {}
    for c in db.task_journals.find({"kind": "comment"}).sort("created_at", 1):
        by_wp.setdefault(c["wp_source_id"], []).append(c)

    out = []
    for wp_id, comments in by_wp.items():
        meta = task_meta.get(wp_id)
        if not meta:
            continue
        title = meta.get("title") or "Untitled"
        wp = meta.get("wp_type") or "Item"
        pname = pnames.get(str(meta.get("project_source_id")), _UNKNOWN_PROJECT)
        url = work_package_url(wp_id)
        for c in comments[-settings.openproject_journal_comment_cap:]:
            body = (c.get("comment") or "")[:600]
            who = c.get("user") or "someone"
            when = c.get("created_at")
            text = (f'Comment on {wp} #{wp_id} "{title}" ({pname}) by {who} on {when}: '
                   f'"{body}"' + (f" Link: {url}" if url else ""))
            out.append(_chunk("task_comments", c["source_id"], text,
                              {"project": pname, "wp_id": wp_id, "url": url}))
    return out


def _timeline_steps(history: list[dict]) -> str:
    steps = []
    for h in history[-12:]:
        who = f" by {h['by']}" if h.get("by") else ""
        frm = h.get("from") or "(created)"
        steps.append(f"{frm} → {h.get('to')}{who} on {h.get('at')}")
    return "; ".join(steps)


def _timeline_chunk(t: dict, pnames: dict[str, str]) -> dict | None:
    wp_id = t.get("source_id")
    history = t.get("status_history") or []
    if not wp_id or not history:
        return None
    pname = pnames.get(str(t.get("project_source_id")), _UNKNOWN_PROJECT)
    wp = t.get("wp_type") or "Item"
    title = t.get("title") or "Untitled"
    url = work_package_url(wp_id)

    closed_bit = (f" Closed by {t['closed_by']} on {t['closed_at']}."
                 if t.get("closed_at") else " Not yet closed.")
    reopen_bit = f" Reopened {t['reopen_count']} time(s)." if t.get("reopen_count") else ""

    text = (f'{wp} #{wp_id} "{title}" ({pname}) timeline: {_timeline_steps(history)}.'
           f'{closed_bit}{reopen_bit} Current status: {t.get("status")}.'
           + (f" Link: {url}" if url else ""))
    return _chunk("task_timeline", wp_id, text,
                 {"project": pname, "status": t.get("status"), "url": url})


@chunk_source("task_timeline")
def _task_timeline(db: Database) -> list[dict]:
    """One chunk per journal-synced work package: a condensed status story —
    when it closed, by whom, how many times it's been reopened — so Inaya
    can answer "who closed this and when" / "what's still pending" from the
    Activity journal instead of just the current status snapshot."""
    pnames = _project_names(db)
    rows = db.tasks.find(
        {"source_system": "openproject", "journal_synced_updated_at": {"$exists": True}},
        {"source_id": 1, "title": 1, "wp_type": 1, "status": 1, "project_source_id": 1,
         "status_history": 1, "reopen_count": 1, "closed_at": 1, "closed_by": 1},
    )
    chunks = (_timeline_chunk(t, pnames) for t in rows)
    return [c for c in chunks if c is not None]


@chunk_source("projects")
def _projects(db: Database) -> list[dict]:
    out = []
    for p in db.projects.find({}, {"name": 1, "status": 1, "progress": 1,
                                   "expected_progress": 1, "project_id": 1, "source_id": 1}):
        pid = p.get("project_id") or p.get("source_id")
        name = p.get("name")
        if not pid or not name:
            continue
        exp = p.get("expected_progress")
        flag = " This project is AT RISK." if exp and p.get("progress", 0) < 0.7 * exp else ""
        text = (f'Project {name} ({p.get("status")}): {p.get("progress", 0)}% complete'
               + (f", expected {exp}%." if exp else ".") + flag)
        out.append(_chunk("projects", pid, text, {"status": p.get("status")}))
    return out


@chunk_source("compliance_items")
def _compliance(db: Database) -> list[dict]:
    out = []
    for c in db.compliance_items.find({}):
        cid = c.get("item_id")
        if not cid:
            continue
        text = (f'Compliance item "{c.get("title")}" due {c.get("due_date")}, '
               f'owner {c.get("owner")}, status {c.get("status")}.')
        out.append(_chunk("compliance_items", cid, text, {"status": c.get("status")}))
    return out


@chunk_source("positions")
def _positions(db: Database) -> list[dict]:
    out = []
    for p in db.positions.find({}):
        pid = p.get("pos_id")
        if not pid:
            continue
        text = (f'Open position "{p.get("title")}" in {p.get("dept")}: open '
               f'{p.get("days_open")} day(s), {p.get("candidates")} candidate(s), '
               f'status {p.get("status")}.')
        out.append(_chunk("positions", pid, text, {"status": p.get("status"), "dept": p.get("dept")}))
    return out


@chunk_source("crm_contacts")
def _contacts(db: Database) -> list[dict]:
    pnames = {p.get("project_id"): p.get("name") for p in
             db.projects.find({}, {"project_id": 1, "name": 1})}
    out = []
    for c in db.crm_contacts.find({}):
        cid = c.get("contact_id")
        if not cid:
            continue
        pname = pnames.get(c.get("project_id"), c.get("project_id"))
        text = (f'{pname} contact {c.get("name")} ({c.get("title")}, {c.get("contact_type")}) '
               f'— status {c.get("status")}, last contact {c.get("last_contact") or "never"}.')
        out.append(_chunk("crm_contacts", cid, text, {"project": pname, "status": c.get("status")}))
    return out


@chunk_source("project_invoices")
def _invoices(db: Database) -> list[dict]:
    pnames = {p.get("project_id"): p.get("name") for p in
             db.projects.find({}, {"project_id": 1, "name": 1})}
    out = []
    for i in db.project_invoices.find({}):
        iid = i.get("invoice_id")
        if not iid:
            continue
        pname = pnames.get(i.get("project_id"), i.get("project_id"))
        amount = i.get("amount", 0)
        text = (f'{pname} invoice {i.get("number")}: ${amount:,.0f} due {i.get("due_date")}, '
               f'status {i.get("status")} — {i.get("description", "")}.')
        out.append(_chunk("project_invoices", iid, text,
                          {"project": pname, "status": i.get("status")}))
    return out


@chunk_source("documents")
def _documents(db: Database) -> list[dict]:
    out = []
    for d in db.documents.find({}):
        did = d.get("doc_id")
        if not did:
            continue
        text = f'Document "{d.get("title")}" ({d.get("kind")}) — status {d.get("status")}.'
        out.append(_chunk("documents", did, text, {"status": d.get("status")}))
    return out


@chunk_source("product_docs")
def _product_docs(db: Database) -> list[dict]:
    out = []
    for d in db.product_docs.find({}):
        did = d.get("pdoc_id")
        if not did:
            continue
        text = f'Product doc "{d.get("title")}" ({d.get("module")}) — status {d.get("status")}.'
        out.append(_chunk("product_docs", did, text, {"status": d.get("status")}))
    return out


def reindex(db: Database, sources: list[str] | None = None, force: bool = False) -> dict:
    """Rebuild chunks for the given sources (default: every registered
    source). Only chunks whose content actually changed get re-embedded;
    chunks whose source row has since vanished are pruned. Bumps
    `rag_index_meta`'s version counter so `ai/vectorstore`'s cached matrix
    knows to reload on the next search."""
    targets = sources or list(_BUILDERS)
    embedder = get_embedder()
    stats: dict = {"sources": {}, "embedded": 0, "unchanged": 0, "pruned": 0}

    for name in targets:
        fn = _BUILDERS.get(name)
        if fn is None:
            continue
        chunks = fn(db)
        existing = {c["chunk_id"]: c.get("content_hash")
                   for c in db.rag_chunks.find({"source": name}, {"chunk_id": 1, "content_hash": 1})}
        seen_ids: list[str] = []
        to_embed = []
        for c in chunks:
            seen_ids.append(c["chunk_id"])
            if not force and existing.get(c["chunk_id"]) == c["content_hash"]:
                stats["unchanged"] += 1
                continue
            to_embed.append(c)

        if to_embed:
            now = dt.datetime.now(dt.timezone.utc)
            vectors = embedder.embed([c["text"] for c in to_embed])
            for c, vec in zip(to_embed, vectors):
                db.rag_chunks.update_one(
                    {"chunk_id": c["chunk_id"]},
                    {"$set": {**c, "embedding": vec, "embedder": embedder.name, "updated_at": now}},
                    upsert=True,
                )
            stats["embedded"] += len(to_embed)

        pruned = db.rag_chunks.delete_many({"source": name, "chunk_id": {"$nin": seen_ids}})
        stats["pruned"] += pruned.deleted_count
        stats["sources"][name] = len(chunks)

    if stats["embedded"] or stats["pruned"]:
        db.rag_index_meta.update_one({"_id": "version"}, {"$inc": {"value": 1}}, upsert=True)
    return stats
