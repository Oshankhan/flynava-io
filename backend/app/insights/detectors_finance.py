"""Finance problem-statement detectors.

Data sources: `project_invoices` (real per-project billing), `payslips`
(monthly payroll cost), `aws_costs` (simulated infra spend). Aggregates only
— no individual salary rows ever appear in evidence (module access includes
"summary"-level investor/leadership roles).
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict

from pymongo.database import Database

from .engine import detector
from .util import project_names

AGING_BUCKETS = ["current", "1-30", "31-60", "61-90", "90+"]


def _aging_bucket(days_past_due: int) -> str:
    if days_past_due <= 0:
        return "current"
    if days_past_due <= 30:
        return "1-30"
    if days_past_due <= 60:
        return "31-60"
    if days_past_due <= 90:
        return "61-90"
    return "90+"


def _recent_months(n: int) -> list[str]:
    out, d = [], dt.date.today().replace(day=1)
    for _ in range(n):
        out.append(d.strftime("%Y-%m"))
        d = (d - dt.timedelta(days=1)).replace(day=1)
    out.reverse()
    return out


@detector("fin_cash_position", "finance", "Cash collected vs outstanding")
def _cash_position(db: Database, project: str | None = None) -> dict | None:
    invoices = list(db.project_invoices.find({}))
    if not invoices:
        return None
    today = dt.date.today()
    collected = sum(i.get("amount", 0) for i in invoices if i.get("status") == "paid")
    unpaid = [i for i in invoices if i.get("status") != "paid"]
    outstanding = sum(i.get("amount", 0) for i in unpaid)
    if outstanding == 0:
        return None

    buckets: dict[str, float] = {b: 0.0 for b in AGING_BUCKETS}
    for i in unpaid:
        days_past = 0
        due = i.get("due_date")
        if due:
            try:
                days_past = (today - dt.date.fromisoformat(str(due)[:10])).days
            except ValueError:
                pass
        buckets[_aging_bucket(days_past)] += i.get("amount", 0)
    over_60 = buckets["61-90"] + buckets["90+"]

    pnames = project_names(db)
    worst = sorted(unpaid, key=lambda i: -i.get("amount", 0))[:8]
    evidence = [f"{i.get('number')} — ${i.get('amount', 0):,.0f}, due {i.get('due_date')}, "
               f"status {i.get('status')}, project {pnames.get(str(i.get('project_id')), i.get('project_id'))}"
               for i in worst]

    problem = (f"${outstanding:,.0f} is outstanding across {len(unpaid)} unpaid invoice(s), "
              f"against ${collected:,.0f} collected.")
    if over_60:
        problem += f" ${over_60:,.0f} of that is more than 60 days past due."

    return {
        "severity": "high" if over_60 > 0 else "medium" if outstanding > collected * 0.25 else "low",
        "problem": problem,
        "metrics": [{"label": "Collected", "value": round(collected, 2), "unit": "USD"},
                    {"label": "Outstanding", "value": round(outstanding, 2), "unit": "USD"}]
                  + [{"label": f"Aging {b}", "value": round(buckets[b], 2), "unit": "USD"}
                     for b in AGING_BUCKETS],
        "entities": [{"kind": "invoice", "id": i.get("invoice_id"), "label": i.get("number"),
                      "extra": {"amount": i.get("amount"), "status": i.get("status"),
                                "due_date": i.get("due_date")}} for i in worst],
        "evidence": evidence,
        "chart": {"kind": "bars", "points": [{"label": b, "value": round(buckets[b], 2)}
                                             for b in AGING_BUCKETS]},
        "action_hint": "Follow up on invoices more than 60 days past due first." if over_60
                      else "Follow up on the largest outstanding invoices.",
    }


@detector("fin_burn_vs_collections", "finance", "Burn is outpacing collections")
def _burn_vs_collections(db: Database, project: str | None = None) -> dict | None:
    months = _recent_months(6)
    payroll_by_month: dict[str, float] = defaultdict(float)
    for r in db.payslips.find({}, {"month": 1, "gross": 1}):
        if r.get("month") in months:
            payroll_by_month[r["month"]] += r.get("gross", 0)
    aws_by_month: dict[str, float] = defaultdict(float)
    for r in db.aws_costs.find({}, {"month": 1, "cost": 1}):
        if r.get("month") in months:
            aws_by_month[r["month"]] += r.get("cost", 0)
    collected_by_month: dict[str, float] = defaultdict(float)
    for i in db.project_invoices.find({"status": "paid"}, {"date": 1, "amount": 1}):
        m = str(i.get("date") or "")[:7]
        if m in months:
            collected_by_month[m] += i.get("amount", 0)

    if not payroll_by_month and not aws_by_month and not collected_by_month:
        return None

    rows = [(m, payroll_by_month.get(m, 0) + aws_by_month.get(m, 0), collected_by_month.get(m, 0))
           for m in months]
    # Trim trailing months with no data at all (e.g. the current, still-open
    # month before payroll/AWS have posted) so "latest" means the latest
    # month with an actual number behind it, not an empty one.
    while rows and rows[-1][1] == 0 and rows[-1][2] == 0:
        rows.pop()
    if not rows:
        return None
    _, latest_burn, latest_collected = rows[-1]
    net_latest = latest_collected - latest_burn
    negative_months = [r for r in rows if r[2] - r[1] < 0]
    if not negative_months:
        return None
    worsening = len(rows) >= 2 and (rows[-1][2] - rows[-1][1]) < (rows[-2][2] - rows[-2][1])

    problem = (f"In {rows[-1][0]}, burn (payroll + AWS, ${latest_burn:,.0f}) "
              f"{'exceeded' if net_latest < 0 else 'was below'} the "
              f"${latest_collected:,.0f} collected from tracked client invoices "
              f"(this reflects invoiced client accounts, not total company revenue).")
    if len(negative_months) > 1:
        problem += f" {len(negative_months)} of the last {len(rows)} months ran net-negative."

    return {
        "severity": "high" if net_latest < 0 and worsening else "medium",
        "problem": problem,
        "metrics": [{"label": f"{m} burn", "value": round(b, 2), "unit": "USD"} for m, b, c in rows[-3:]]
                  + [{"label": f"{m} collected", "value": round(c, 2), "unit": "USD"} for m, b, c in rows[-3:]],
        "entities": [],
        "evidence": [f"{m}: burn ${b:,.0f} (payroll+AWS), collected ${c:,.0f}, net ${c - b:,.0f}"
                    for m, b, c in rows],
        "chart": {"kind": "bars", "points": [{"label": m, "value": round(c - b, 2)} for m, b, c in rows]},
        "action_hint": "Accelerate outstanding client invoice collection." if net_latest < 0
                      else "Monitor the burn-vs-collections trend.",
    }


@detector("fin_late_clients", "finance", "Clients with recurring late payments")
def _late_clients(db: Database, project: str | None = None) -> dict | None:
    invoices = list(db.project_invoices.find({}))
    if not invoices:
        return None
    today = dt.date.today()
    projects = {p.get("project_id"): p for p in
               db.projects.find({}, {"project_id": 1, "name": 1, "client": 1})}

    by_client: dict[str, dict[str, float]] = defaultdict(
        lambda: {"overdue_now": 0, "overdue_amount": 0.0})
    for i in invoices:
        proj = projects.get(i.get("project_id"), {})
        client = proj.get("client") or proj.get("name") or i.get("project_id") or "Unknown"
        status = i.get("status")
        past_due = False
        due = i.get("due_date")
        if due and status != "paid":
            try:
                past_due = dt.date.fromisoformat(str(due)[:10]) < today
            except ValueError:
                pass
        if status == "overdue" or past_due:
            by_client[client]["overdue_now"] += 1
            by_client[client]["overdue_amount"] += i.get("amount", 0)

    if not by_client:
        return None
    worst = sorted(by_client.items(), key=lambda kv: -kv[1]["overdue_amount"])
    top_client, top_stats = worst[0]

    problem = (f"{top_client} has ${top_stats['overdue_amount']:,.0f} in overdue invoice(s) "
              f"({int(top_stats['overdue_now'])} invoice(s)).")
    if len(worst) > 1:
        problem += f" {len(worst)} client(s) currently have overdue invoices."

    return {
        "severity": "high" if top_stats["overdue_amount"] >= 50000 else "medium",
        "problem": problem,
        "metrics": [{"label": "Clients with overdue invoices", "value": len(worst), "unit": ""},
                    {"label": f"{top_client} overdue amount",
                     "value": round(top_stats["overdue_amount"], 2), "unit": "USD"}],
        "entities": [{"kind": "client", "id": c, "label": c, "extra": s} for c, s in worst[:8]],
        "evidence": [f"{c} — {int(s['overdue_now'])} overdue invoice(s), ${s['overdue_amount']:,.0f}"
                    for c, s in worst[:8]],
        "chart": {"kind": "bars", "points": [{"label": c, "value": round(s["overdue_amount"], 2)}
                                             for c, s in worst[:5]]},
        "action_hint": f"Follow up with {top_client} on the "
                       f"${top_stats['overdue_amount']:,.0f} overdue balance.",
    }
