"""Seed the real FlyNava roster, org tree, client projects, and demo data.

Idempotent: upserts by natural key. Demo password for every seeded user is
`Passw0rd!` — dev only. Two logins are preserved from the earlier demo seed
so existing bookmarks/muscle-memory keep working: `admin@flynava.ai` (now
Mahesh Shastry, CEO) and `hr@flynava.ai` (now Shammi YK, HR head).
"""
from __future__ import annotations

import datetime as dt
import random
import uuid

from pymongo.database import Database

from ..core.security import hash_password
from ..kpi.definitions import KPI_DEFINITIONS

DEMO_PASSWORD = "Passw0rd!"

DEPARTMENTS = [
    {"dept_id": "eng", "name": "Engineering"},
    {"dept_id": "product", "name": "Product"},
    {"dept_id": "mkt", "name": "Marketing"},
    {"dept_id": "hr", "name": "Human Resources"},
    {"dept_id": "fin", "name": "Finance"},
    {"dept_id": "exec", "name": "Leadership"},
]

# Teams are generic units: any department can have one, each led by an L2
# team lead. Members (L1) carry team_id + reports_to → the approval chain.
TEAMS = [
    {"team_id": "team_ui", "name": "UI Team", "department": "eng", "lead_id": "u_birbal"},
    {"team_id": "team_python", "name": "Python Team", "department": "eng", "lead_id": "u_murugan"},
    {"team_id": "team_qa", "name": "QA Team", "department": "eng", "lead_id": "u_prathima"},
    {"team_id": "team_java", "name": "Java Team", "department": "eng", "lead_id": "u_deepashree"},
    {"team_id": "team_devops", "name": "DevOps Team", "department": "eng", "lead_id": "u_kalaiarasan"},
    {"team_id": "team_marketing", "name": "Marketing Team", "department": "mkt", "lead_id": "u_tanvi"},
    {"team_id": "team_product", "name": "Product Team", "department": "product", "lead_id": "u_soochana"},
    {"team_id": "team_hr", "name": "HR Team", "department": "hr", "lead_id": "u_shammi"},
]

# Org tree (level 4 → 1). reports_to builds the approval chain: every request
# goes to the direct lead first; leads forward upward when needed.
# Fields: user_id, name, email, role, department, level, designation,
#         team_id, reports_to, extra_roles (optional, for multi-role people).
#
# Tree shape: CEO → {Harsha (all delivery teams), Meghna (product+marketing,
# multi-role), Shammi (HR, reports straight to CEO), Rakshitha (Finance,
# reports straight to CEO)}. UI has an extra layer: Harsha → Birbal (UI
# Manager) → Mushaheed (UI Lead) → UI devs — both Birbal and Mushaheed are
# level 2 in the schema (only 4 levels exist app-wide); the reports_to chain
# is what actually encodes the extra hop, and org drill-down walks that chain
# regardless of level number.
USERS: list[dict] = [
    # --- L4 ---
    {"user_id": "u_ceo", "name": "Mahesh Shastry", "email": "admin@flynava.ai",
     "role": "super_admin", "department": "exec", "level": 4,
     "designation": "CEO", "team_id": None, "reports_to": None},

    # --- L3 ---
    {"user_id": "u_harsha", "name": "Harsha Varlani", "email": "harsha.varlani@flynava.ai",
     "role": "manager", "department": "eng", "level": 3,
     "designation": "Head of Engineering", "team_id": None, "reports_to": "u_ceo"},
    {"user_id": "u_meghna", "name": "Meghna Mehra", "email": "meghna.mehra@flynava.ai",
     "role": "manager", "department": "product", "level": 3,
     "designation": "Product & Marketing Manager", "team_id": None, "reports_to": "u_ceo",
     "extra_roles": ["marketing"]},
    {"user_id": "u_shammi", "name": "Shammi YK", "email": "hr@flynava.ai",
     "role": "hr", "department": "hr", "level": 3,
     "designation": "HR Head", "team_id": "team_hr", "reports_to": "u_ceo"},
    {"user_id": "u_rakshitha", "name": "Rakshitha S", "email": "rakshitha.s@flynava.ai",
     "role": "manager", "department": "fin", "level": 3,
     "designation": "Finance Manager", "team_id": None, "reports_to": "u_ceo"},

    # --- L2: team leads (+ Birbal, the UI sub-manager) ---
    {"user_id": "u_birbal", "name": "Birbal Kumar", "email": "birbal.kumar@flynava.ai",
     "role": "manager", "department": "eng", "level": 2,
     "designation": "UI Manager", "team_id": "team_ui", "reports_to": "u_harsha"},
    {"user_id": "u_mushaheed", "name": "Mushaheed Khan N", "email": "mushaheed.khan@flynava.ai",
     "role": "team_lead", "department": "eng", "level": 2,
     "designation": "UI Lead", "team_id": "team_ui", "reports_to": "u_birbal"},
    {"user_id": "u_murugan", "name": "Murugan P", "email": "murugan.p@flynava.ai",
     "role": "team_lead", "department": "eng", "level": 2,
     "designation": "Python Team Lead", "team_id": "team_python", "reports_to": "u_harsha"},
    {"user_id": "u_prathima", "name": "Prathima DS", "email": "prathima.ds@flynava.ai",
     "role": "team_lead", "department": "eng", "level": 2,
     "designation": "QA Lead", "team_id": "team_qa", "reports_to": "u_harsha"},
    {"user_id": "u_deepashree", "name": "Deepashree HI", "email": "deepashree.hi@flynava.ai",
     "role": "team_lead", "department": "eng", "level": 2,
     "designation": "Java Team Lead", "team_id": "team_java", "reports_to": "u_harsha"},
    {"user_id": "u_kalaiarasan", "name": "Kalaiarasan D", "email": "kalaiarasan.d@flynava.ai",
     "role": "team_lead", "department": "eng", "level": 2,
     "designation": "DevOps Lead", "team_id": "team_devops", "reports_to": "u_harsha"},
    {"user_id": "u_tanvi", "name": "Tanvi Gupta", "email": "tanvi.gupta@flynava.ai",
     "role": "marketing", "department": "mkt", "level": 2,
     "designation": "Marketing Lead", "team_id": "team_marketing", "reports_to": "u_meghna"},
    {"user_id": "u_soochana", "name": "Soochana Byaravalli", "email": "soochana.byaravalli@flynava.ai",
     "role": "team_lead", "department": "product", "level": 2,
     "designation": "Product Lead", "team_id": "team_product", "reports_to": "u_meghna"},

    # --- L1: UI team ---
    {"user_id": "u_animesh", "name": "Animesh Singh", "email": "animesh.singh@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "UI Designer", "team_id": "team_ui", "reports_to": "u_mushaheed"},
    {"user_id": "u_dinesh", "name": "Dinesh Pandia", "email": "dinesh.pandia@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "UX Designer", "team_id": "team_ui", "reports_to": "u_mushaheed"},
    {"user_id": "u_saghir", "name": "Md Saghir Alam", "email": "saghir.alam@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "UI Developer", "team_id": "team_ui", "reports_to": "u_mushaheed"},
    {"user_id": "u_nagaraj", "name": "Nagaraj Biradar", "email": "nagaraj.biradar@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "UI Designer", "team_id": "team_ui", "reports_to": "u_mushaheed"},
    {"user_id": "u_nayana", "name": "Nayana Anaji", "email": "nayana.anaji@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "UX Designer", "team_id": "team_ui", "reports_to": "u_mushaheed"},
    {"user_id": "u_oshan", "name": "Oshan Khan", "email": "oshan.khan@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "UI Developer", "team_id": "team_ui", "reports_to": "u_mushaheed"},

    # --- L1: Python team ---
    {"user_id": "u_manas", "name": "Manas Ankarla", "email": "manas.ankarla@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "Python Developer", "team_id": "team_python", "reports_to": "u_murugan"},
    {"user_id": "u_sharana", "name": "Sharanabasava SK", "email": "sharanabasava.sk@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "Python Developer", "team_id": "team_python", "reports_to": "u_murugan"},
    {"user_id": "u_pawan", "name": "Pawan Kalyan", "email": "pawan.kalyan@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "Python Developer", "team_id": "team_python", "reports_to": "u_murugan"},
    {"user_id": "u_jashwanth", "name": "Jashwanth Reddy", "email": "jashwanth.reddy@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "Python Developer", "team_id": "team_python", "reports_to": "u_murugan"},
    {"user_id": "u_abhinav", "name": "Abhinav Bonagiri", "email": "abhinav.bonagiri@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "Python Developer", "team_id": "team_python", "reports_to": "u_murugan"},
    {"user_id": "u_rithik", "name": "Rithik Sharma", "email": "rithik.sharma@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "Python Developer", "team_id": "team_python", "reports_to": "u_murugan"},
    {"user_id": "u_jaiveer", "name": "Jaiveer Singh", "email": "jaiveer.singh@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "Python Developer", "team_id": "team_python", "reports_to": "u_murugan"},
    {"user_id": "u_anuvrat", "name": "Anuvrat Gautam", "email": "anuvrat.gautam@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "Python Developer", "team_id": "team_python", "reports_to": "u_murugan"},

    # --- L1: QA team ---
    {"user_id": "u_akshaya", "name": "Akshaya G", "email": "akshaya.g@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "QA Engineer", "team_id": "team_qa", "reports_to": "u_prathima"},
    {"user_id": "u_rahul", "name": "Rahul Kumar", "email": "rahul.kumar@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "QA Engineer", "team_id": "team_qa", "reports_to": "u_prathima"},
    {"user_id": "u_devireddy", "name": "Devireddy Guruvardhanreddy", "email": "devireddy.g@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "QA Engineer", "team_id": "team_qa", "reports_to": "u_prathima"},
    {"user_id": "u_tanuja", "name": "Tanuja Talwar", "email": "tanuja.talwar@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "QA Engineer", "team_id": "team_qa", "reports_to": "u_prathima"},
    {"user_id": "u_nikshitha", "name": "Nikshitha TB", "email": "nikshitha.tb@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "QA Engineer", "team_id": "team_qa", "reports_to": "u_prathima"},

    # --- L1: Java team ---
    {"user_id": "u_mohamed", "name": "Mohamed Absar", "email": "mohamed.absar@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "Java Developer", "team_id": "team_java", "reports_to": "u_deepashree"},

    # --- L1: DevOps team ---
    {"user_id": "u_praveen", "name": "Praveen Jayavel", "email": "praveen.jayavel@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "DevOps Engineer", "team_id": "team_devops", "reports_to": "u_kalaiarasan"},
    {"user_id": "u_aravind", "name": "Aravind Krishnan", "email": "aravind.krishnan@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "DevOps Engineer", "team_id": "team_devops", "reports_to": "u_kalaiarasan"},
    {"user_id": "u_tamilselvan", "name": "Tamil Selvan S", "email": "tamil.selvan@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "DevOps Engineer", "team_id": "team_devops", "reports_to": "u_kalaiarasan"},
    {"user_id": "u_kambam", "name": "Kambam Mythri", "email": "kambam.mythri@flynava.ai",
     "role": "employee", "department": "eng", "level": 1,
     "designation": "DevOps Engineer", "team_id": "team_devops", "reports_to": "u_kalaiarasan"},

    # --- L1: Marketing team ---
    {"user_id": "u_arnav", "name": "Arnav Jain", "email": "arnav.jain@flynava.ai",
     "role": "marketing", "department": "mkt", "level": 1,
     "designation": "Marketing Executive", "team_id": "team_marketing", "reports_to": "u_tanvi"},
    {"user_id": "u_aadhira", "name": "Aadhira S", "email": "aadhira.s@flynava.ai",
     "role": "marketing", "department": "mkt", "level": 1,
     "designation": "Marketing Executive", "team_id": "team_marketing", "reports_to": "u_tanvi"},
    {"user_id": "u_gunnika", "name": "Gunnika Singh", "email": "gunnika.singh@flynava.ai",
     "role": "marketing", "department": "mkt", "level": 1,
     "designation": "Marketing Executive", "team_id": "team_marketing", "reports_to": "u_tanvi"},

    # --- L1: Product team ---
    {"user_id": "u_ronaly", "name": "Ronaly Bojamma", "email": "ronaly.bojamma@flynava.ai",
     "role": "employee", "department": "product", "level": 1,
     "designation": "Product Analyst", "team_id": "team_product", "reports_to": "u_soochana"},
    {"user_id": "u_akasapu", "name": "Akasapu Suma Sri", "email": "akasapu.sumasri@flynava.ai",
     "role": "employee", "department": "product", "level": 1,
     "designation": "Product Analyst", "team_id": "team_product", "reports_to": "u_soochana"},
    {"user_id": "u_ranveer", "name": "Ranveer Singh Panda", "email": "ranveer.panda@flynava.ai",
     "role": "employee", "department": "product", "level": 1,
     "designation": "Business Analyst", "team_id": "team_product", "reports_to": "u_soochana"},
    {"user_id": "u_nikkitha", "name": "Nikkitha Ann Bobby", "email": "nikkitha.bobby@flynava.ai",
     "role": "employee", "department": "product", "level": 1,
     "designation": "Product Analyst", "team_id": "team_product", "reports_to": "u_soochana"},
    {"user_id": "u_akhila", "name": "N Akhila Sri Krishna", "email": "akhila.srikrishna@flynava.ai",
     "role": "employee", "department": "product", "level": 1,
     "designation": "Business Analyst", "team_id": "team_product", "reports_to": "u_soochana"},

    # --- L1: HR team ---
    {"user_id": "u_chandrakala", "name": "Chandrakala Thallapalli", "email": "chandrakala.t@flynava.ai",
     "role": "employee", "department": "hr", "level": 1,
     "designation": "HR Executive", "team_id": "team_hr", "reports_to": "u_shammi"},

    # --- Non-org stakeholder logins (not part of the delivery roster —
    # kept for the roles' distinct RBAC matrix behavior: leadership/investor/
    # partner see materially different module access than any employee role). ---
    {"user_id": "u_lead", "name": "Leo Lead", "email": "leadership@flynava.ai",
     "role": "leadership", "department": "exec", "level": 4,
     "designation": "Founder", "team_id": None, "reports_to": None},
    {"user_id": "u_inv", "name": "Ivy Investor", "email": "investor@flynava.ai",
     "role": "investor", "department": "exec", "level": 0,
     "designation": "Investor", "team_id": None, "reports_to": None},
    {"user_id": "u_partner", "name": "Pat Partner", "email": "partner@flynava.ai",
     "role": "partner", "department": "exec", "level": 0,
     "designation": "Partner", "team_id": None, "reports_to": None},
]


# Generic cross-functional pipeline every client project moves through.
# `owner_team` is a hint for which team typically drives that stage (not
# enforced) — marketing opens a project, product/engineering build it, QA
# signs off, then it settles into steady-state production support.
STAGE_PIPELINE = [
    {"key": "client_acquisition", "name": "Client Acquisition", "owner_team": "marketing"},
    {"key": "rfp_proposal", "name": "RFP / Proposal", "owner_team": "marketing"},
    {"key": "requirements", "name": "Requirements", "owner_team": "product"},
    {"key": "design", "name": "Design", "owner_team": "ui"},
    {"key": "development", "name": "Development", "owner_team": "engineering"},
    {"key": "qa_testing", "name": "QA / Testing", "owner_team": "qa"},
    {"key": "uat_training", "name": "UAT / Training", "owner_team": "product"},
    {"key": "production_maintenance", "name": "Production / Maintenance", "owner_team": "qa"},
]
_STAGE_KEYS = [s["key"] for s in STAGE_PIPELINE]


def _stages_up_to(current_key: str) -> list[dict]:
    idx = _STAGE_KEYS.index(current_key)
    out = []
    for i, s in enumerate(STAGE_PIPELINE):
        status = "done" if i < idx else "active" if i == idx else "pending"
        out.append({**s, "status": status})
    return out


PROJECTS = [
    {
        "project_id": "proj_kq", "code": "KQ", "name": "Kenya Airways",
        "client": "Kenya Airways", "status": "maintenance",
        "current_stage": "production_maintenance",
        "stages": _stages_up_to("production_maintenance"),
        "owner_id": "u_harsha",
        "team_ids": ["team_python", "team_qa", "team_devops", "team_ui"],
        "member_ids": ["u_murugan", "u_manas", "u_sharana", "u_pawan",
                       "u_prathima", "u_akshaya", "u_rahul",
                       "u_kalaiarasan", "u_praveen",
                       "u_mushaheed", "u_animesh"],
        "progress": 100, "expected_progress": 100,
    },
    {
        "project_id": "proj_om", "code": "OM", "name": "Oman Airways",
        "client": "Oman Airways", "status": "pipeline",
        "current_stage": "client_acquisition",
        "stages": _stages_up_to("client_acquisition"),
        "owner_id": "u_meghna",
        "team_ids": ["team_marketing"],
        "member_ids": ["u_meghna", "u_tanvi", "u_arnav", "u_aadhira"],
        "progress": 10, "expected_progress": 20,
    },
    {
        "project_id": "proj_sv", "code": "SV", "name": "Saudia",
        "client": "Saudia", "status": "active",
        "current_stage": "uat_training",
        "stages": _stages_up_to("uat_training"),
        "owner_id": "u_meghna",
        "team_ids": ["team_product", "team_qa"],
        "member_ids": ["u_soochana", "u_ronaly", "u_akasapu", "u_ranveer",
                       "u_prathima", "u_tanuja"],
        "progress": 65, "expected_progress": 75,
    },
]

_BUG_TITLES = [
    ("Booking", "Seat map fails to load for round-trip fares"),
    ("Booking", "Fare rules not refreshed after currency switch"),
    ("Booking", "Duplicate booking created on payment retry"),
    ("Checkin", "Boarding pass QR code renders blank on iOS"),
    ("Checkin", "Baggage allowance not reflecting frequent-flyer tier"),
    ("Checkin", "Kiosk check-in timeout on slow network"),
    ("Payments", "Refund stuck in pending after gateway timeout"),
    ("Payments", "Wallet top-up double-charges on retry"),
    ("Payments", "Tax computed incorrectly for multi-city fares"),
    ("Reports", "Daily revenue report missing cancelled-fare adjustments"),
    ("Reports", "Ops dashboard shows stale load-factor numbers"),
    ("Reports", "Compliance export fails for date ranges > 90 days"),
    ("Notifications", "Flight-delay SMS sent twice to same passenger"),
    ("Notifications", "Push notification missing for gate change"),
    ("Loyalty", "Miles not credited for codeshare flights"),
    ("Loyalty", "Tier upgrade email sent to wrong passenger"),
]
_BUG_STATUSES = ["Open", "In progress", "Reopen", "Closed", "Resolved"]
_BUG_PRIORITIES = ["Immediate", "High", "Normal", "Low"]


def _kq_bugs(now: dt.datetime, assignee_ids: list[str], names: dict[str, str]) -> list[dict]:
    """~40 synthetic prod-support bugs for KQ, spread across real assignees."""
    rng = random.Random(20260712)
    out = []
    n = 40
    for i in range(n):
        module, title = _BUG_TITLES[i % len(_BUG_TITLES)]
        assignee_id = assignee_ids[i % len(assignee_ids)]
        # weight toward closed/resolved so bug_closure_rate looks realistic
        status = rng.choices(_BUG_STATUSES, weights=[30, 20, 10, 25, 15])[0]
        priority = rng.choices(_BUG_PRIORITIES, weights=[15, 30, 40, 15])[0]
        due = (now - dt.timedelta(days=rng.randint(-10, 30))).date().isoformat()
        out.append({
            "task_id": f"bug_kq_{i + 1:03d}", "project_id": "proj_kq",
            "title": f"[{module}] {title} (#{i + 1})", "wp_type": "Bug",
            "status": status, "priority": priority,
            "assignee_id": assignee_id, "assignee": names.get(assignee_id),
            "progress": 100 if status in ("Closed", "Resolved") else rng.choice([0, 25, 50, 75]),
            "due_date": due, "stage": "production_maintenance",
        })
    return out


def _project_tasks(now: dt.datetime, names: dict[str, str]) -> list[dict]:
    """A handful of normal (non-bug) tasks per project, tied to a stage."""
    rng = random.Random(20260712)
    defs = [
        ("proj_kq", "production_maintenance", "u_murugan", "Rotate API keys for booking service", "In progress"),
        ("proj_kq", "production_maintenance", "u_kalaiarasan", "Patch prod DB replica lag alerting", "Open"),
        ("proj_om", "client_acquisition", "u_tanvi", "Prepare Oman Airways pitch deck", "In progress"),
        ("proj_om", "client_acquisition", "u_arnav", "Competitor pricing research", "Open"),
        ("proj_om", "rfp_proposal", "u_meghna", "Draft RFP response outline", "Open"),
        ("proj_sv", "uat_training", "u_soochana", "Schedule Saudia UAT sessions", "In progress"),
        ("proj_sv", "uat_training", "u_ronaly", "Write training manual — booking module", "In progress"),
        ("proj_sv", "qa_testing", "u_prathima", "Sign off SV regression suite", "Done"),
        ("proj_sv", "requirements", "u_akasapu", "Finalize SV loyalty requirements doc", "Done"),
    ]
    out = []
    for i, (pid, stage, uid, title, status) in enumerate(defs):
        due = (now + dt.timedelta(days=rng.randint(-5, 20))).date().isoformat()
        out.append({
            "task_id": f"proj_task_{i + 1:03d}", "project_id": pid, "stage": stage,
            "title": title, "status": status, "assignee_id": uid,
            "assignee": names.get(uid),
            "progress": 100 if status == "Done" else (50 if status == "In progress" else 0),
            "due_date": due,
        })
    return out


AUTOMATION_SCRIPTS = [
    {"script_id": "as1", "title": "Booking flow regression", "module": "Booking",
     "owner": "Prathima DS", "status": "pending"},
    {"script_id": "as2", "title": "Seat selection smoke test", "module": "Booking",
     "owner": "Akshaya G", "status": "in_review"},
    {"script_id": "as3", "title": "Check-in kiosk E2E", "module": "Checkin",
     "owner": "Rahul Kumar", "status": "pending"},
    {"script_id": "as4", "title": "Boarding pass scan test", "module": "Checkin",
     "owner": "Devireddy Guruvardhanreddy", "status": "done"},
    {"script_id": "as5", "title": "Payment gateway retry logic", "module": "Payments",
     "owner": "Tanuja Talwar", "status": "pending"},
    {"script_id": "as6", "title": "Refund workflow automation", "module": "Payments",
     "owner": "Nikshitha TB", "status": "pending"},
    {"script_id": "as7", "title": "Wallet top-up regression", "module": "Payments",
     "owner": "Prathima DS", "status": "in_review"},
    {"script_id": "as8", "title": "Monthly revenue report validation", "module": "Reports",
     "owner": "Akshaya G", "status": "pending"},
    {"script_id": "as9", "title": "Ops dashboard data-accuracy check", "module": "Reports",
     "owner": "Rahul Kumar", "status": "done"},
    {"script_id": "as10", "title": "Compliance report export test", "module": "Reports",
     "owner": "Prathima DS", "status": "pending"},
]


def _product_docs(now: dt.datetime) -> list[dict]:
    return [
        {"pdoc_id": "pd1", "title": "Booking Module — PRD v2", "module": "Booking",
         "status": "pending", "created_at": now - dt.timedelta(days=6)},
        {"pdoc_id": "pd2", "title": "Check-in Module — Spec Update", "module": "Checkin",
         "status": "pending", "created_at": now - dt.timedelta(days=3)},
        {"pdoc_id": "pd3", "title": "Payments Module — PRD v2", "module": "Payments",
         "status": "pending", "created_at": now - dt.timedelta(days=10)},
        {"pdoc_id": "pd4", "title": "Reports Module — Analytics Spec", "module": "Reports",
         "status": "pending", "created_at": now - dt.timedelta(days=1)},
    ]


def _seed_core(db: Database, now: dt.datetime) -> None:
    """Departments, teams, users, projects/tasks, KPI defs+values, compliance,
    positions, automation scripts, product docs.

    Every write is an upsert by natural key, or (for `kpi_values`) an insert
    guarded by a `count_documents == 0` check — never a blanket delete. Safe
    to call repeatedly, including against an already-seeded live database:
    it can only add missing demo rows or refresh known ones back to their
    demo values, never touch a document it doesn't recognize by these ids.
    Split out from `seed()` so `seed_demo_extras()` can reuse it without
    also calling `seed_hr()`, which unconditionally wipes and rebuilds all
    employees/payslips/leaves and would destroy real submissions on a live
    database.
    """
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
    names: dict[str, str] = {}
    for u in USERS:
        roles = [u["role"]] + u.get("extra_roles", [])
        team_ids = [u["team_id"]] if u.get("team_id") else []
        names[u["user_id"]] = u["name"]
        db.users.update_one(
            {"user_id": u["user_id"]},
            {"$set": {
                "user_id": u["user_id"], "name": u["name"], "email": u["email"],
                "role": u["role"], "roles": roles, "department": u["department"],
                "status": "active", "password_hash": pw, "level": u["level"],
                "designation": u["designation"], "team_id": u["team_id"],
                "team_ids": team_ids, "reports_to": u["reports_to"],
                "created_at": now,
            }},
            upsert=True,
        )

    for p in PROJECTS:
        db.projects.update_one({"project_id": p["project_id"]},
                               {"$set": {**p, "created_at": now}}, upsert=True)

    for t in _kq_bugs(now, PROJECTS[0]["member_ids"], names):
        db.tasks.update_one({"task_id": t["task_id"]},
                            {"$set": {**t, "source_system": "seed", "created_at": now}},
                            upsert=True)

    for t in _project_tasks(now, names):
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

    for a in AUTOMATION_SCRIPTS:
        db.automation_scripts.update_one({"script_id": a["script_id"]},
                                         {"$set": {**a, "updated_at": now}}, upsert=True)

    for p in _product_docs(now):
        db.product_docs.update_one({"pdoc_id": p["pdoc_id"]}, {"$set": p}, upsert=True)


def seed_demo_extras(db: Database) -> dict:
    """Refresh all demo seed data except HR, safe to rerun against an
    already-seeded (live) database.

    Backfills everything `_seed_core` covers (departments/teams/users,
    projects/tasks, KPI defs+values, compliance, positions, automation
    scripts, product docs) plus the attendance window and demo meetings.
    Deliberately skips `seed_hr()` — see `_seed_core`'s docstring — so real
    leave requests or payslip data entered through the live app survive.
    """
    now = dt.datetime.now(dt.timezone.utc)
    _seed_core(db, now)

    from .hr import seed_attendance
    attendance_rows = seed_attendance(db)

    from .meetings import seed_meetings
    meetings = seed_meetings(db)

    return {
        "users": len(USERS),
        "automation_scripts": len(AUTOMATION_SCRIPTS),
        "product_docs": len(_product_docs(now)),
        "attendance_rows": attendance_rows,
        "meetings": meetings,
    }


def reset_roster(db: Database) -> dict:
    """Destructive rebuild: wipe every seed-owned collection and reseed from
    scratch with the current roster/projects. Use when the roster itself has
    changed (not just refreshing demo values) — e.g. replacing the old
    placeholder people with the real FlyNava team. Never call this against a
    database with real, non-demo data you care about.
    """
    for coll in ("users", "teams", "departments", "projects", "tasks",
                 "attendance", "leaves", "payslips", "employees", "meetings",
                 "notifications", "automation_scripts", "product_docs"):
        db[coll].delete_many({})
    seed(db)
    return {"users": len(USERS), "teams": len(TEAMS), "projects": len(PROJECTS)}


def seed(db: Database) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    _seed_core(db, now)

    # HR: employees (harvests OpenProject assignee names if synced), payslips,
    # leave balances. Rebuilt each seed run.
    from .hr import seed_attendance, seed_hr
    seed_hr(db)

    # 7 weekdays of biometric-style attendance for every employee (CEO
    # dashboard "who's late/absent today" + individual attendance cards).
    seed_attendance(db)

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
