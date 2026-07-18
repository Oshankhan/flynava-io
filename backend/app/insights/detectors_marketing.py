"""Marketing problem-statement detector.

Data source: `crm_contacts` — per-client-project airline contacts (real seed
data, SuiteCRM-style). No CRM lead/pipeline integration is connected yet
(HubSpot is Phase 2 per `integrations/registry.py`), so this is the one
marketing problem statement groundable in real data today.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from pymongo.database import Database

from .engine import detector
from .util import project_names

STALE_AFTER_DAYS = 21


@detector("mkt_stale_contacts", "marketing", "Client accounts going cold")
def _stale_contacts(db: Database, project: str | None = None) -> dict | None:
    contacts = list(db.crm_contacts.find({"status": "active"}))
    if not contacts:
        return None
    today = dt.date.today()
    pnames = project_names(db)

    by_project: dict[str, list[bool]] = defaultdict(list)
    stale: list[tuple[dict, int | None]] = []
    for c in contacts:
        last = c.get("last_contact")
        days_since = None
        is_stale = True
        if last:
            try:
                days_since = (today - dt.date.fromisoformat(str(last)[:10])).days
                is_stale = days_since > STALE_AFTER_DAYS
            except ValueError:
                pass
        by_project[c.get("project_id")].append(is_stale)
        if is_stale:
            stale.append((c, days_since))

    if not stale:
        return None
    coverage_gaps = [pid for pid, flags in by_project.items() if all(flags)]
    stale.sort(key=lambda cd: -(cd[1] if cd[1] is not None else 10_000))

    problem = f"{len(stale)} active contact(s) have not been touched in over {STALE_AFTER_DAYS} days."
    if coverage_gaps:
        gap_names = [pnames.get(pid, pid) for pid in coverage_gaps]
        problem += (f" {len(coverage_gaps)} client account(s) have NO recently-contacted "
                   f"person at all: {', '.join(gap_names)}.")

    top_contact, top_days = stale[0]
    return {
        "severity": "high" if coverage_gaps else "medium",
        "problem": problem,
        "metrics": [{"label": "Stale contacts", "value": len(stale), "unit": ""},
                    {"label": "Accounts with a full coverage gap", "value": len(coverage_gaps), "unit": ""}],
        "entities": [{"kind": "contact", "id": c.get("contact_id"), "label": c.get("name"),
                      "extra": {"project": pnames.get(c.get("project_id"), c.get("project_id")),
                                "days_since_contact": days}} for c, days in stale[:8]],
        "evidence": [f"{c.get('name')} ({c.get('title')}) — "
                    f"{pnames.get(c.get('project_id'), c.get('project_id'))}, "
                    f"{'never contacted' if days is None else f'{days}d since last contact'}"
                    for c, days in stale[:8]],
        "chart": None,
        "action_hint": f"Re-engage {top_contact.get('name')} at "
                       f"{pnames.get(top_contact.get('project_id'), '')} first.",
    }
