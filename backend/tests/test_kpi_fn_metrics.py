"""KPIs extracted from Priority_docs/FN KPIs.docx and wired into kpi/engine.py:
finance (revenue/burn/net burn/AR aging/AR days), HR (headcount/absenteeism/
late rate), product (bug resolution time/reopen rate), marketing (contact
coverage). Each computer is cross-checked against the actual seeded data
(derived here, not hardcoded) so these stay robust to the seed roster/dataset
changing over time — same convention as test_kpi.py's operations test.
"""
from __future__ import annotations

import datetime as dt

from app.kpi import engine


def _snap(db, module=None):
    return {r["kpi_id"]: r for r in engine.run_all(db, module)}


def test_invoice_collections_mtd_matches_paid_invoices_this_month(db):
    month = dt.date.today().strftime("%Y-%m")
    expected = round(sum(
        i.get("amount", 0) for i in db.project_invoices.find({"status": "paid"})
        if str(i.get("date", "")).startswith(month)
    ), 2)
    snap = _snap(db, "finance")
    assert snap["fin_revenue_mtd"]["value"] == expected


def test_gross_burn_monthly_sums_payroll_for_latest_payroll_month(db):
    # payroll (INR) and AWS cost (USD) are different currencies — the KPI
    # deliberately doesn't combine them without a real FX conversion.
    month_row = db.payslips.find_one(sort=[("month", -1)])
    assert month_row, "seed must produce payslips"
    month = month_row["month"]
    expected = round(sum(p.get("gross", 0) for p in db.payslips.find({"month": month})), 2)
    snap = _snap(db, "finance")
    assert snap["fin_burn_rate"]["value"] == expected


def test_ar_over_60_sums_unpaid_invoices_past_due_more_than_60_days(db):
    today = dt.date.today()
    expected = 0.0
    for inv in db.project_invoices.find({"status": {"$in": ["pending", "overdue"]}}):
        due = inv.get("due_date")
        if due and (today - dt.date.fromisoformat(str(due)[:10])).days > 60:
            expected += inv.get("amount", 0)
    snap = _snap(db, "finance")
    assert snap["fin_ar_over_60"]["value"] == round(expected, 2)


def test_ar_days_outstanding_is_mean_days_past_due(db):
    today = dt.date.today()
    days = []
    for inv in db.project_invoices.find({"status": {"$in": ["pending", "overdue"]}}):
        due = inv.get("due_date")
        if due:
            d = (today - dt.date.fromisoformat(str(due)[:10])).days
            if d > 0:
                days.append(d)
    expected = round(sum(days) / len(days), 1) if days else 0.0
    snap = _snap(db, "finance")
    assert snap["fin_ar_days"]["value"] == expected


def test_active_headcount_matches_active_employees(db):
    expected = db.employees.count_documents({"status": "active"})
    assert expected > 0, "seed must produce active employees"
    snap = _snap(db, "hr")
    assert snap["hr_headcount"]["value"] == expected


def test_absenteeism_and_late_rate_match_last_30_days_attendance(db):
    cutoff = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    total = db.attendance.count_documents({"date": {"$gte": cutoff}})
    assert total > 0, "seed must produce recent attendance rows"
    absent = db.attendance.count_documents({"date": {"$gte": cutoff}, "status": "Absent"})
    late = db.attendance.count_documents({"date": {"$gte": cutoff}, "status": "Late"})
    snap = _snap(db, "hr")
    assert snap["hr_absenteeism"]["value"] == round(absent / total * 100, 2)
    assert snap["hr_late_rate"]["value"] == round(late / total * 100, 2)


def test_bug_resolution_days_only_counts_bugs_with_both_timestamps(db):
    # Seed-only bugs lack updated_at (only real OpenProject syncs carry it) —
    # this environment has no OP sync, so the KPI has nothing to average yet.
    snap = _snap(db, "product_dev")
    assert snap["pd_bug_resolution_days"]["value"] is None

    now = dt.datetime.now(dt.timezone.utc)
    db.tasks.insert_one({
        "source_system": "openproject", "source_id": "res1", "wp_type": "Bug",
        "title": "Resolved bug", "status": "Closed",
        "created_at": (now - dt.timedelta(days=5)).isoformat(),
        "updated_at": now.isoformat(),
    })
    snap2 = _snap(db, "product_dev")
    assert snap2["pd_bug_resolution_days"]["value"] == 5.0


def test_bug_reopen_rate_counts_reopened_vs_cleanly_closed(db):
    db.tasks.insert_many([
        {"source_system": "openproject", "source_id": "r1", "wp_type": "Bug",
         "title": "Reopened once", "status": "In progress", "reopen_count": 1},
        {"source_system": "openproject", "source_id": "r2", "wp_type": "Bug",
         "title": "Currently reopen", "status": "Reopen", "reopen_count": 0},
        {"source_system": "openproject", "source_id": "r3", "wp_type": "Bug",
         "title": "Closed cleanly", "status": "Closed", "reopen_count": 0},
    ])
    snap = _snap(db, "product_dev")
    docs = list(db.tasks.find({"wp_type": {"$regex": "bug", "$options": "i"}},
                              {"status": 1, "reopen_count": 1}))
    reopened = sum(1 for d in docs
                   if (d.get("reopen_count") or 0) >= 1 or d.get("status") == "Reopen")
    terminal_clean = sum(1 for d in docs if d.get("status") in engine.CLOSED_BUG_STATUSES
                         and (d.get("reopen_count") or 0) < 1)
    expected = round(reopened / (reopened + terminal_clean) * 100, 2)
    assert snap["pd_reopen_rate"]["value"] == expected


def test_contact_coverage_30d_matches_recently_contacted_active_contacts(db):
    today = dt.date.today()
    active = list(db.crm_contacts.find({"status": "active"}, {"last_contact": 1}))
    assert active, "seed must produce active CRM contacts"
    fresh = sum(1 for c in active
               if c.get("last_contact") and
               (today - dt.date.fromisoformat(str(c["last_contact"])[:10])).days <= 30)
    snap = _snap(db, "marketing_sales")
    assert snap["mkt_contact_coverage"]["value"] == round(fresh / len(active) * 100, 2)


def test_pd_kpis_are_project_scoped(db):
    # a clean project with exactly one, currently-reopened bug -> 100% scoped
    # reopen rate, regardless of whatever the rest of the seeded bug data looks
    # like once every bug across every project is mixed together.
    db.tasks.insert_one({
        "source_system": "openproject", "source_id": "px1", "wp_type": "Bug",
        "title": "Scoped reopen", "status": "Reopen", "reopen_count": 0,
        "project_source_id": "unscoped_test_project_77",
    })
    d = db.kpi_defs.find_one({"kpi_id": "pd_reopen_rate"})
    scoped = engine.compute(db, d, project="unscoped_test_project_77")
    assert scoped == 100.0


def test_new_finance_hr_kpis_appear_on_their_dashboards(client, auth_header, db):
    engine.run_all(db)
    r = client.get("/api/v1/dashboards/finance", headers=auth_header("leadership@flynava.ai"))
    ids = {k["kpi_id"] for k in r.json()["kpis"]}
    assert "fin_ar_days" in ids

    r2 = client.get("/api/v1/dashboards/hr", headers=auth_header("hr@flynava.ai"))
    ids2 = {k["kpi_id"] for k in r2.json()["kpis"]}
    assert "hr_late_rate" in ids2
