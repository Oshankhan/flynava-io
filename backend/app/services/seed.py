"""Seed demo departments, users (one per role), projects, tasks, KPI defs.

Idempotent: upserts by natural key. Demo password for every seeded user is
`Passw0rd!` — dev only.
"""
from __future__ import annotations

import datetime as dt

from pymongo.database import Database

from ..core.security import hash_password
from ..kpi.definitions import KPI_DEFINITIONS

DEMO_PASSWORD = "Passw0rd!"

DEPARTMENTS = [
    {"dept_id": "eng", "name": "Engineering"},
    {"dept_id": "hr", "name": "Human Resources"},
    {"dept_id": "fin", "name": "Finance"},
    {"dept_id": "mkt", "name": "Marketing"},
    {"dept_id": "exec", "name": "Leadership"},
]

# Teams are generic units: any department can have one, each led by an L2
# team lead. Members (L1) carry team_id + reports_to → the approval chain.
TEAMS = [
    {"team_id": "team_java", "name": "Java Team", "department": "eng", "lead_id": "u_tl_java"},
    {"team_id": "team_python", "name": "Python Team", "department": "eng", "lead_id": "u_tl_python"},
    {"team_id": "team_qa", "name": "QA Team", "department": "eng", "lead_id": "u_tl_qa"},
    {"team_id": "team_fin", "name": "Finance Team", "department": "fin", "lead_id": "u_tl_fin"},
    {"team_id": "team_hr", "name": "HR Team", "department": "hr", "lead_id": "u_tl_hr"},
    {"team_id": "team_mkt", "name": "Marketing Team", "department": "mkt", "lead_id": "u_tl_mkt"},
]

# Org tree (level 4 → 1). reports_to builds the approval chain: every request
# goes to the direct lead first; leads forward upward when needed.
# (user_id, name, email, role, dept, level, designation, team_id, reports_to)
USERS = [
    # L4 — Super Admin / CEO / Founder
    ("u_admin", "Ada Admin", "admin@flynava.ai", "super_admin", "exec", 4,
     "CEO", None, None),
    ("u_lead", "Leo Lead", "leadership@flynava.ai", "leadership", "exec", 4,
     "Founder", None, None),
    # L3 — Department heads
    ("u_mgr", "Mia Manager", "manager@flynava.ai", "manager", "eng", 3,
     "Engineering Manager", None, "u_admin"),
    ("u_hr", "Hana HR", "hr@flynava.ai", "hr", "hr", 3,
     "HR Manager", None, "u_admin"),
    ("u_fin_head", "Farah Fintch", "finance.head@flynava.ai", "manager", "fin", 3,
     "Finance Manager", None, "u_admin"),
    ("u_mkt", "Marco Marketing", "marketing@flynava.ai", "marketing", "mkt", 3,
     "Marketing Manager", None, "u_admin"),
    # L2 — Team leads
    ("u_tl_java", "Arjun Rao", "java.tl@flynava.ai", "team_lead", "eng", 2,
     "Java Team Lead", "team_java", "u_mgr"),
    ("u_tl_python", "Priya Nair", "python.tl@flynava.ai", "team_lead", "eng", 2,
     "Python Team Lead", "team_python", "u_mgr"),
    ("u_tl_qa", "Vikram Shah", "qa.tl@flynava.ai", "team_lead", "eng", 2,
     "QA Team Lead", "team_qa", "u_mgr"),
    ("u_tl_fin", "Tanya Kapoor", "finance.tl@flynava.ai", "team_lead", "fin", 2,
     "Finance Team Lead", "team_fin", "u_fin_head"),
    ("u_tl_hr", "Rahul Verma", "hr.tl@flynava.ai", "team_lead", "hr", 2,
     "HR Team Lead", "team_hr", "u_hr"),
    ("u_tl_mkt", "Meera Joshi", "marketing.tl@flynava.ai", "team_lead", "mkt", 2,
     "Marketing Team Lead", "team_mkt", "u_mkt"),
    # L1 — Executives / developers / QA / recruiters
    ("u_emp", "Evan Employee", "employee@flynava.ai", "employee", "eng", 1,
     "Python Developer", "team_python", "u_tl_python"),
    ("u_dev_java", "Kiran Kumar", "java.dev@flynava.ai", "employee", "eng", 1,
     "Java Developer", "team_java", "u_tl_java"),
    ("u_qa1", "Sneha Patil", "qa.eng@flynava.ai", "employee", "eng", 1,
     "QA Engineer", "team_qa", "u_tl_qa"),
    ("u_fin1", "Rohit Menon", "finance.exec@flynava.ai", "employee", "fin", 1,
     "Finance Executive", "team_fin", "u_tl_fin"),
    ("u_rec1", "Anita Das", "recruiter@flynava.ai", "employee", "hr", 1,
     "Recruiter", "team_hr", "u_tl_hr"),
    ("u_mkt1", "Dev Sharma", "marketing.exec@flynava.ai", "employee", "mkt", 1,
     "Marketing Executive", "team_mkt", "u_tl_mkt"),
    # External (outside the ladder)
    ("u_inv", "Ivy Investor", "investor@flynava.ai", "investor", "exec", 0,
     "Investor", None, None),
    ("u_partner", "Pat Partner", "partner@flynava.ai", "partner", "exec", 0,
     "Partner", None, None),
]


def seed(db: Database) -> None:
    now = dt.datetime.now(dt.timezone.utc)

    for d in DEPARTMENTS:
        db.departments.update_one(
            {"dept_id": d["dept_id"]},
            {"$set": {**d, "created_at": now}},
            upsert=True,
        )

    for t in TEAMS:
        db.teams.update_one(
            {"team_id": t["team_id"]},
            {"$set": {**t, "created_at": now}},
            upsert=True,
        )

    pw = hash_password(DEMO_PASSWORD)
    for uid, name, email, role, dept, level, designation, team_id, reports_to in USERS:
        db.users.update_one(
            {"user_id": uid},
            {"$set": {
                "user_id": uid, "name": name, "email": email, "role": role,
                "department": dept, "status": "active", "password_hash": pw,
                "level": level, "designation": designation, "team_id": team_id,
                "reports_to": reports_to, "created_at": now,
            }},
            upsert=True,
        )

    # demo projects + tasks (also seeded by OpenProject connector in Phase 2)
    projects = [
        {"project_id": "p_alpha", "name": "Project Alpha", "status": "active",
         "owner_id": "u_mgr", "dept_id": "eng", "source_system": "seed",
         "progress": 42, "expected_progress": 70},
        {"project_id": "p_beta", "name": "Project Beta", "status": "active",
         "owner_id": "u_mgr", "dept_id": "eng", "source_system": "seed",
         "progress": 88, "expected_progress": 80},
    ]
    for p in projects:
        db.projects.update_one({"project_id": p["project_id"]},
                               {"$set": {**p, "created_at": now}}, upsert=True)

    tasks = [
        {"task_id": "t1", "project_id": "p_alpha", "title": "Design schema",
         "assignee_id": "u_emp", "status": "Done", "progress": 100,
         "due_date": "2020-01-01"},
        {"task_id": "t2", "project_id": "p_alpha", "title": "Build ingestion",
         "assignee_id": "u_emp", "status": "In progress", "progress": 30,
         "due_date": "2020-01-01"},  # overdue
        {"task_id": "t3", "project_id": "p_alpha", "title": "Write docs",
         "assignee_id": "u_mgr", "status": "Open", "progress": 0,
         "due_date": "2030-01-01"},
    ]
    for t in tasks:
        db.tasks.update_one({"task_id": t["task_id"]},
                            {"$set": {**t, "source_system": "seed", "created_at": now}},
                            upsert=True)

    for d in KPI_DEFINITIONS:
        db.kpi_defs.update_one({"kpi_id": d["kpi_id"]}, {"$set": d}, upsert=True)
        # Seed placeholder values for KPIs whose integration isn't wired yet,
        # so dashboards render before real data flows. `demo_history` seeds a
        # 12-month monthly series (drives trend charts + change arrows).
        if db.kpi_values.count_documents({"kpi_id": d["kpi_id"]}) > 0:
            continue
        hist = d.get("demo_history")
        if hist:
            for i, v in enumerate(hist):
                ts = now - dt.timedelta(days=30 * (len(hist) - 1 - i))
                db.kpi_values.insert_one({
                    "kpi_id": d["kpi_id"], "value": v,
                    "period_start": ts, "period_end": ts, "calculated_at": ts,
                    "source_data_ref": "demo_seed",
                })
        elif "demo_value" in d:
            db.kpi_values.insert_one({
                "kpi_id": d["kpi_id"], "value": d["demo_value"],
                "period_start": now, "period_end": now, "calculated_at": now,
                "source_data_ref": "demo_seed",
            })

    # Compliance calendar + recruitment pipeline (evidence for Ask IO, per PRD
    # 10.5/10.6, until Veda / Zoho Recruit are connected).
    compliance_items = [
        {"item_id": "c1", "title": "GST quarterly filing", "due_date": "2026-07-20",
         "owner": "Finance", "status": "pending"},
        {"item_id": "c2", "title": "ISO 27001 surveillance audit",
         "due_date": "2026-08-04", "owner": "Compliance", "status": "pending"},
        {"item_id": "c3", "title": "PF/ESI monthly remittance",
         "due_date": "2026-07-15", "owner": "HR", "status": "overdue"},
    ]
    for c in compliance_items:
        db.compliance_items.update_one({"item_id": c["item_id"]}, {"$set": c},
                                       upsert=True)

    positions = [
        {"pos_id": "p1", "title": "Senior Backend Engineer", "dept": "eng",
         "days_open": 52, "candidates": 14, "status": "open"},
        {"pos_id": "p2", "title": "QA Automation Engineer", "dept": "eng",
         "days_open": 21, "candidates": 9, "status": "open"},
        {"pos_id": "p3", "title": "Finance Analyst", "dept": "fin",
         "days_open": 33, "candidates": 6, "status": "open"},
    ]
    for p in positions:
        db.positions.update_one({"pos_id": p["pos_id"]}, {"$set": p}, upsert=True)

    # HR: employees (harvests OpenProject assignee names if synced), payslips,
    # leave balances. Rebuilt each seed run.
    from .hr import seed_hr
    seed_hr(db)

    # Demo meetings around today (calendar + "upcoming" widget).
    from .meetings import seed_meetings
    seed_meetings(db)


if __name__ == "__main__":  # python -m app.services.seed
    from ..db import ensure_indexes, get_db

    database = get_db()
    ensure_indexes(database)
    seed(database)
    print(f"Seeded {len(USERS)} users, {len(DEPARTMENTS)} departments, "
          f"{len(KPI_DEFINITIONS)} KPI defs. Demo password: {DEMO_PASSWORD}")
