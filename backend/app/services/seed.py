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


# Default template a brand-new project starts from (STAGE_PIPELINE / _stages_up_to).
# Existing projects carry their OWN editable `stages` list (see PROJECTS below) —
# this template only seeds new projects created via POST /projects.
# `owner_team` is a hint for which team typically drives that stage (not
# enforced) — marketing opens a project, product/engineering build it, QA
# signs off, then it settles into steady-state production support.
STAGE_PIPELINE = [
    {"key": "client_acquisition", "name": "Client Acquisition", "owner_team": "marketing",
     "description": "Prospecting and initial client outreach"},
    {"key": "rfp_proposal", "name": "RFP / Proposal", "owner_team": "marketing",
     "description": "Proposal drafting and contract negotiation"},
    {"key": "requirements", "name": "Requirements", "owner_team": "product",
     "description": "Gathering and documenting client requirements"},
    {"key": "design", "name": "Design", "owner_team": "ui",
     "description": "UI/UX and solution design"},
    {"key": "development", "name": "Development", "owner_team": "engineering",
     "description": "Build and implementation"},
    {"key": "qa_testing", "name": "QA / Testing", "owner_team": "qa",
     "description": "Quality assurance and test cycles"},
    {"key": "uat_training", "name": "UAT / Training", "owner_team": "product",
     "description": "User acceptance testing and client training"},
    {"key": "production_maintenance", "name": "Production / Maintenance", "owner_team": "qa",
     "description": "Live support and ongoing maintenance"},
]
_STAGE_KEYS = [s["key"] for s in STAGE_PIPELINE]


def _stages_up_to(current_key: str) -> list[dict]:
    idx = _STAGE_KEYS.index(current_key)
    out = []
    for i, s in enumerate(STAGE_PIPELINE):
        status = "done" if i < idx else "active" if i == idx else "pending"
        out.append({**s, "status": status, "progress": 100 if status == "done" else 0,
                    "start_date": None, "end_date": None})
    return out


def _stage(key: str, name: str, description: str, status: str, progress: int,
          start: str, end: str) -> dict:
    return {"key": key, "name": name, "description": description, "status": status,
            "progress": progress, "start_date": start, "end_date": end, "owner_team": ""}


PROJECTS = [
    {
        "project_id": "proj_kq", "code": "KQ", "name": "Kenya Airways",
        "client": "Kenya Airways", "status": "active", "logo": "/logos/kq.png",
        "engagement": "Existing Client - Production Support",
        "description": "Production support and maintenance for existing modules. "
                       "Handling bugs, patches and minor enhancements as per client requirements.",
        "priority": "High", "project_manager_id": "u_animesh",
        "start_date": "2026-01-01", "due_date": "2026-12-31",
        "current_stage": "development",
        "stages": [
            _stage("initiation", "Initiation", "Project kickoff and requirement review",
                  "done", 100, "2026-01-01", "2026-01-10"),
            _stage("planning", "Planning", "Resource planning and task estimation",
                  "done", 100, "2026-01-11", "2026-01-25"),
            _stage("development", "Development", "Bug fixing and enhancements",
                  "active", 70, "2026-01-26", "2026-09-30"),
            _stage("testing", "Testing", "QA testing and UAT",
                  "pending", 0, "2026-10-01", "2026-10-31"),
            _stage("deployment", "Deployment", "Release to production",
                  "pending", 0, "2026-11-01", "2026-11-15"),
            _stage("closure", "Closure", "Project closure and handover",
                  "pending", 0, "2026-11-16", "2026-12-31"),
        ],
        "owner_id": "u_harsha",
        "team_ids": ["team_python", "team_qa", "team_devops", "team_ui"],
        "member_ids": ["u_murugan", "u_manas", "u_sharana", "u_pawan",
                       "u_prathima", "u_akshaya", "u_rahul",
                       "u_kalaiarasan", "u_praveen",
                       "u_mushaheed", "u_animesh"],
        "progress": 45, "expected_progress": 50, "open_tasks_target": 12,
        "contract_value": 480000,
    },
    {
        "project_id": "proj_om", "code": "WY", "name": "Oman Airways",
        "client": "Oman Airways", "status": "planning", "logo": "/logos/om.png",
        "engagement": "New Prospect",
        "description": "Marketing phase in progress. If the scenario moves forward, "
                       "development teams will be allocated.",
        "priority": "Medium", "project_manager_id": "u_nayana",
        "start_date": "2026-06-15", "due_date": "2026-11-30",
        "current_stage": "client_acquisition",
        "stages": [
            _stage("client_acquisition", "Client Acquisition",
                  "Prospecting and initial client outreach",
                  "active", 40, "2026-06-15", "2026-08-15"),
            _stage("rfp_proposal", "RFP / Proposal",
                  "Proposal drafting and contract negotiation",
                  "pending", 0, "2026-08-16", "2026-11-30"),
        ],
        "owner_id": "u_meghna",
        "team_ids": ["team_marketing"],
        "member_ids": ["u_meghna", "u_tanvi", "u_arnav", "u_aadhira", "u_gunnika"],
        "progress": 20, "expected_progress": 25, "open_tasks_target": 8,
    },
    {
        "project_id": "proj_sv", "code": "SV", "name": "Saudia Airlines",
        "client": "Saudia Airlines", "status": "active", "logo": "/logos/sv.png",
        "engagement": "Implementation & Training",
        "description": "Client training ongoing for key modules and processes.",
        "priority": "Medium", "project_manager_id": "u_mushaheed",
        "start_date": "2026-05-10", "due_date": "2026-08-31",
        "current_stage": "training_delivery",
        "stages": [
            _stage("requirements", "Requirements", "Confirming modules and rollout scope",
                  "done", 100, "2026-05-10", "2026-05-20"),
            _stage("configuration", "Configuration", "Environment and module setup",
                  "done", 100, "2026-05-21", "2026-06-10"),
            _stage("training_delivery", "Training Delivery",
                  "Running client training sessions", "active", 0, "2026-06-11", "2026-08-10"),
            _stage("go_live", "Go-Live", "Cutover to production usage",
                  "pending", 0, "2026-08-11", "2026-08-20"),
            _stage("closure", "Closure", "Project closure and handover",
                  "pending", 0, "2026-08-21", "2026-08-31"),
        ],
        "owner_id": "u_meghna",
        "team_ids": ["team_product", "team_qa"],
        "member_ids": ["u_soochana", "u_ronaly", "u_akasapu", "u_ranveer",
                       "u_prathima", "u_tanuja"],
        "progress": 40, "expected_progress": 50, "open_tasks_target": 15,
        "contract_value": 260000,
    },
]


def _contact(contact_id: str, project_id: str, name: str, title: str, department: str,
            email: str, phone: str, contact_type: str, status: str, last_contact: str) -> dict:
    slug = name.lower().replace(".", "").replace("'", "").replace(" ", "-")
    return {"contact_id": contact_id, "project_id": project_id, "name": name, "title": title,
            "department": department, "email": email, "phone": phone,
            "linkedin": f"https://linkedin.com/in/{slug}",
            "contact_type": contact_type, "status": status, "last_contact": last_contact,
            "notes": "", "created_by": "u_tanvi", "seed": True}


# Fictional airline-side contacts, SuiteCRM-style (Account -> Contacts), one
# marketing-exclusive tab per project. Names/emails/phones are all made up.
CRM_CONTACTS = [
    # --- Kenya Airways (proj_kq) ---
    _contact("con_kq_01", "proj_kq", "Animesh Sharma", "Production Support Manager", "IT Operations",
             "animesh.sharma@kenya-airways.com", "+254 712 345 678", "primary", "active", "2026-07-12"),
    _contact("con_kq_02", "proj_kq", "Njoroge Mwangi", "IT Infrastructure Lead", "IT Operations",
             "njoroge.mwangi@kenya-airways.com", "+254 723 456 789", "technical", "active", "2026-07-10"),
    _contact("con_kq_03", "proj_kq", "Faith Kamau", "Business Analyst", "Business Systems",
             "faith.kamau@kenya-airways.com", "+254 734 567 890", "business", "active", "2026-07-09"),
    _contact("con_kq_04", "proj_kq", "David Ochieng", "QA Manager", "Quality Assurance",
             "david.ochieng@kenya-airways.com", "+254 745 678 901", "technical", "active", "2026-07-08"),
    _contact("con_kq_05", "proj_kq", "Jane Mutua", "Finance Controller", "Finance",
             "jane.mutua@kenya-airways.com", "+254 756 789 012", "finance", "active", "2026-07-05"),
    _contact("con_kq_06", "proj_kq", "Peter Kariuki", "Training Coordinator", "Training",
             "peter.kariuki@kenya-airways.com", "+254 768 890 123", "other", "active", "2026-07-03"),
    _contact("con_kq_07", "proj_kq", "Lilian Otieno", "Change Manager", "Change Management",
             "lilian.otieno@kenya-airways.com", "+254 779 901 234", "business", "inactive", "2026-06-28"),
    _contact("con_kq_08", "proj_kq", "Ethan Kiptoo", "Vendor Manager", "Procurement",
             "ethan.kiptoo@kenya-airways.com", "+254 780 234 567", "other", "active", "2026-06-25"),
    _contact("con_kq_09", "proj_kq", "Grace Wanjiru", "IT Support Analyst", "IT Operations",
             "grace.wanjiru@kenya-airways.com", "+254 791 345 678", "technical", "active", "2026-06-22"),
    _contact("con_kq_10", "proj_kq", "Samuel Kiptum", "Network Engineer", "IT Operations",
             "samuel.kiptum@kenya-airways.com", "+254 702 456 789", "technical", "active", "2026-06-20"),
    _contact("con_kq_11", "proj_kq", "Mercy Achieng", "Booking Systems Analyst", "Business Systems",
             "mercy.achieng@kenya-airways.com", "+254 713 567 890", "business", "active", "2026-06-18"),
    _contact("con_kq_12", "proj_kq", "Brian Otieno", "Security Officer", "IT Security",
             "brian.otieno@kenya-airways.com", "+254 724 678 901", "technical", "active", "2026-06-15"),
    _contact("con_kq_13", "proj_kq", "Esther Nyambura", "Procurement Officer", "Procurement",
             "esther.nyambura@kenya-airways.com", "+254 735 789 012", "other", "active", "2026-06-12"),
    _contact("con_kq_14", "proj_kq", "Kevin Mutiso", "Data Analyst", "Business Systems",
             "kevin.mutiso@kenya-airways.com", "+254 746 890 123", "business", "active", "2026-06-10"),
    _contact("con_kq_15", "proj_kq", "Winnie Chebet", "HR Business Partner", "Human Resources",
             "winnie.chebet@kenya-airways.com", "+254 757 901 234", "other", "active", "2026-06-08"),
    _contact("con_kq_16", "proj_kq", "Dennis Wafula", "Customer Experience Lead", "Customer Service",
             "dennis.wafula@kenya-airways.com", "+254 768 012 345", "business", "active", "2026-06-05"),
    _contact("con_kq_17", "proj_kq", "Patrick Mwangi", "Ground Operations Director", "Ground Operations",
             "patrick.mwangi@kenya-airways.com", "+254 779 123 456", "business", "active", "2026-06-02"),
    _contact("con_kq_18", "proj_kq", "Caroline Njeri", "Legal & Contracts Officer", "Legal",
             "caroline.njeri@kenya-airways.com", "+254 780 234 890", "other", "inactive", "2026-05-28"),

    # --- Oman Air (proj_om) — prospect, smaller contact set ---
    _contact("con_om_01", "proj_om", "Yousuf Al Balushi", "Digital Transformation Manager", "IT",
             "yousuf.albalushi@omanair.example", "+968 9123 4567", "primary", "active", "2026-07-08"),
    _contact("con_om_02", "proj_om", "Fatma Al Habsi", "Procurement Lead", "Procurement",
             "fatma.alhabsi@omanair.example", "+968 9234 5678", "business", "active", "2026-07-04"),
    _contact("con_om_03", "proj_om", "Salim Al Harthy", "IT Infrastructure Manager", "IT Operations",
             "salim.alharthy@omanair.example", "+968 9345 6789", "technical", "active", "2026-06-30"),
    _contact("con_om_04", "proj_om", "Aisha Al Rawahi", "Marketing Director", "Marketing",
             "aisha.alrawahi@omanair.example", "+968 9456 7890", "business", "active", "2026-06-26"),
    _contact("con_om_05", "proj_om", "Khalid Al Amri", "Revenue Management Lead", "Revenue Management",
             "khalid.alamri@omanair.example", "+968 9567 8901", "business", "active", "2026-06-20"),
    _contact("con_om_06", "proj_om", "Noora Al Balushi", "Business Analyst", "Business Systems",
             "noora.albalushi@omanair.example", "+968 9678 9012", "business", "active", "2026-06-15"),
    _contact("con_om_07", "proj_om", "Hamed Al Siyabi", "Vendor Relations Manager", "Procurement",
             "hamed.alsiyabi@omanair.example", "+968 9789 0123", "other", "active", "2026-06-10"),
    _contact("con_om_08", "proj_om", "Maryam Al Kindi", "Training Coordinator", "Training",
             "maryam.alkindi@omanair.example", "+968 9890 1234", "other", "inactive", "2026-05-30"),

    # --- Saudia Airlines (proj_sv) ---
    _contact("con_sv_01", "proj_sv", "Abdullah Al-Otaibi", "IT Director", "IT",
             "abdullah.alotaibi@saudia.example", "+966 50 123 4567", "primary", "active", "2026-07-11"),
    _contact("con_sv_02", "proj_sv", "Sara Al-Qahtani", "Training Manager", "Training",
             "sara.alqahtani@saudia.example", "+966 50 234 5678", "business", "active", "2026-07-09"),
    _contact("con_sv_03", "proj_sv", "Faisal Al-Dosari", "Systems Integration Lead", "IT Operations",
             "faisal.aldosari@saudia.example", "+966 50 345 6789", "technical", "active", "2026-07-06"),
    _contact("con_sv_04", "proj_sv", "Noura Al-Harbi", "QA Lead", "Quality Assurance",
             "noura.alharbi@saudia.example", "+966 50 456 7890", "technical", "active", "2026-07-02"),
    _contact("con_sv_05", "proj_sv", "Mohammed Al-Ghamdi", "Finance Manager", "Finance",
             "mohammed.alghamdi@saudia.example", "+966 50 567 8901", "finance", "active", "2026-06-28"),
    _contact("con_sv_06", "proj_sv", "Huda Al-Sulaiman", "Change Management Lead", "Change Management",
             "huda.alsulaiman@saudia.example", "+966 50 678 9012", "business", "active", "2026-06-24"),
    _contact("con_sv_07", "proj_sv", "Khalid Al-Zahrani", "Ground Ops Manager", "Ground Operations",
             "khalid.alzahrani@saudia.example", "+966 50 789 0123", "business", "active", "2026-06-19"),
    _contact("con_sv_08", "proj_sv", "Reem Al-Mutairi", "Procurement Officer", "Procurement",
             "reem.almutairi@saudia.example", "+966 50 890 1234", "other", "active", "2026-06-14"),
    _contact("con_sv_09", "proj_sv", "Yara Al-Shehri", "Customer Experience Manager", "Customer Service",
             "yara.alshehri@saudia.example", "+966 50 901 2345", "business", "active", "2026-06-08"),
    _contact("con_sv_10", "proj_sv", "Turki Al-Anazi", "Vendor Manager", "Procurement",
             "turki.alanazi@saudia.example", "+966 50 012 3456", "other", "inactive", "2026-05-25"),
]


def _invoice(invoice_id: str, project_id: str, number: str, date: str, due_date: str,
            amount: float, status: str, description: str) -> dict:
    return {"invoice_id": invoice_id, "project_id": project_id, "number": number,
            "date": date, "due_date": due_date, "amount": amount, "currency": "USD",
            "status": status, "description": description, "seed": True}


# 480k/yr production-support retainer billed monthly; the current month
# (matches "today" = 2026-07-13 in this environment) sits pending.
PROJECT_INVOICES = [
    _invoice("inv_kq_01", "proj_kq", "INV-KQ-2026-001", "2026-01-05", "2026-01-20",
            40000, "paid", "Production support — January 2026"),
    _invoice("inv_kq_02", "proj_kq", "INV-KQ-2026-002", "2026-02-05", "2026-02-20",
            40000, "paid", "Production support — February 2026"),
    _invoice("inv_kq_03", "proj_kq", "INV-KQ-2026-003", "2026-03-05", "2026-03-20",
            40000, "paid", "Production support — March 2026"),
    _invoice("inv_kq_04", "proj_kq", "INV-KQ-2026-004", "2026-04-05", "2026-04-20",
            40000, "paid", "Production support — April 2026"),
    _invoice("inv_kq_05", "proj_kq", "INV-KQ-2026-005", "2026-05-05", "2026-05-20",
            40000, "paid", "Production support — May 2026"),
    _invoice("inv_kq_06", "proj_kq", "INV-KQ-2026-006", "2026-06-05", "2026-06-20",
            40000, "paid", "Production support — June 2026"),
    _invoice("inv_kq_07", "proj_kq", "INV-KQ-2026-007", "2026-07-05", "2026-07-20",
            40000, "pending", "Production support — July 2026"),
    # Saudia: milestone billing against the implementation & training engagement.
    _invoice("inv_sv_01", "proj_sv", "INV-SV-2026-001", "2026-05-15", "2026-05-30",
            90000, "paid", "Kickoff & Configuration milestone"),
    _invoice("inv_sv_02", "proj_sv", "INV-SV-2026-002", "2026-06-15", "2026-06-30",
            100000, "overdue", "Training Delivery milestone"),
    _invoice("inv_sv_03", "proj_sv", "INV-SV-2026-003", "2026-08-01", "2026-08-15",
            70000, "pending", "Go-Live milestone"),
    # Oman Air: still a prospect — no invoices yet.
]


def _seed_crm(db: Database, now: dt.datetime) -> None:
    for c in CRM_CONTACTS:
        db.crm_contacts.update_one({"contact_id": c["contact_id"]},
                                   {"$set": {**c, "created_at": now}}, upsert=True)
    for i in PROJECT_INVOICES:
        db.project_invoices.update_one({"invoice_id": i["invoice_id"]},
                                       {"$set": {**i, "created_at": now}}, upsert=True)


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
            "due_date": due, "stage": "development",
        })
    return out


# Per-project open-task title banks — themed to each engagement (KQ: prod
# support/dev work, OM: marketing/pitch prep, SV: training/rollout) so the
# seeded "Open Tasks" count on each project card matches the mockup exactly.
_OPEN_TASK_TITLES: dict[str, list[str]] = {
    "proj_kq": [
        "Rotate API keys for booking service", "Patch prod DB replica lag alerting",
        "Upgrade payment gateway SDK", "Add rate-limiting to check-in API",
        "Refactor seat-map caching layer", "Migrate booking service logs to structured JSON",
        "Add retry/backoff to loyalty sync job", "Document incident runbook for payments outage",
        "Set up synthetic monitoring for check-in flow", "Clean up dead feature flags in booking service",
        "Improve DB index coverage for reports queries", "Automate weekly compliance export job",
    ],
    "proj_om": [
        "Prepare Oman Airways pitch deck", "Competitor pricing research",
        "Draft RFP response outline", "Schedule stakeholder intro call",
        "Build ROI / cost-savings one-pager", "Localize proposal deck for Arabic market",
        "Coordinate reference-client testimonial", "Finalize pricing tiers for proposal",
    ],
    "proj_sv": [
        "Schedule Saudia UAT sessions", "Write training manual — booking module",
        "Prepare check-in module training slides", "Coordinate on-site trainer travel",
        "Set up sandbox environment for trainees", "Translate training material to Arabic",
        "Collect trainee feedback forms", "Draft go-live readiness checklist",
        "Configure loyalty module for Saudia branding", "Set up helpdesk escalation path",
        "Prepare payments module demo script", "Schedule train-the-trainer session",
        "Draft post-go-live support plan", "Review SLA terms with client",
        "Prepare rollback plan for go-live",
    ],
}


def _project_tasks(now: dt.datetime, names: dict[str, str]) -> list[dict]:
    """Seeds each project's `open_tasks_target` worth of open (non-bug) tasks,
    cycling across its real members and stages — drives the "Open Tasks" stat
    shown on each project card/detail."""
    rng = random.Random(20260712)
    out = []
    for p in PROJECTS:
        pid = p["project_id"]
        titles = _OPEN_TASK_TITLES[pid]
        member_ids = p["member_ids"]
        stage_keys = [s["key"] for s in p["stages"]]
        for i in range(p["open_tasks_target"]):
            uid = member_ids[i % len(member_ids)]
            stage = stage_keys[i % len(stage_keys)]
            progress = rng.choice([0, 25, 50, 75])
            status = "Open" if progress == 0 else "In progress"
            due = (now + dt.timedelta(days=rng.randint(-5, 30))).date().isoformat()
            out.append({
                "task_id": f"proj_task_{pid}_{i + 1:03d}", "project_id": pid, "stage": stage,
                "title": titles[i % len(titles)], "status": status, "assignee_id": uid,
                "assignee": names.get(uid), "progress": progress, "due_date": due,
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


# --- Document Management: folders + document dataset ---
# `access` is {"roles": [...], "teams": [...]}; empty lists mean "everyone".
# L3/L4 and super_admin always see every folder regardless of access lists —
# these lists only widen visibility for L1/L2 people (see api/v1/documents.py
# `_folder_visible`).
FOLDERS = [
    {"folder_id": "brand_guidelines", "name": "Brand & Guidelines",
     "description": "Logos, brand colors, tone-of-voice guidelines", "category": "general",
     "access": {"roles": [], "teams": []}, "target_count": 12},
    {"folder_id": "marketing_collaterals", "name": "Marketing Collaterals",
     "description": "Sales decks, one-pagers, and campaign creative", "category": "marketing",
     "access": {"roles": ["marketing", "manager"], "teams": ["team_marketing"]}, "target_count": 28},
    {"folder_id": "presentations", "name": "Presentations",
     "description": "Client-facing and internal presentation decks", "category": "general",
     "access": {"roles": [], "teams": []}, "target_count": 16},
    {"folder_id": "campaigns", "name": "Campaigns",
     "description": "Campaign briefs, timelines, and creative briefs", "category": "marketing",
     "access": {"roles": ["marketing", "manager"], "teams": ["team_marketing"]}, "target_count": 24},
    {"folder_id": "social_media", "name": "Social Media",
     "description": "Social calendars and post creative", "category": "marketing",
     "access": {"roles": ["marketing", "manager"], "teams": ["team_marketing"]}, "target_count": 18},
    {"folder_id": "product_assets", "name": "Product Assets",
     "description": "Product screenshots, UI kits, and spec docs", "category": "product",
     "access": {"roles": ["manager", "team_lead"], "teams": ["team_product", "team_ui"]},
     "target_count": 10},
    {"folder_id": "events", "name": "Events",
     "description": "Event decks, run-of-show, and attendee lists", "category": "general",
     "access": {"roles": [], "teams": []}, "target_count": 8},
    {"folder_id": "reports", "name": "Reports",
     "description": "Budget trackers and performance reports", "category": "general",
     "access": {"roles": ["manager", "team_lead", "hr"], "teams": []}, "target_count": 12},
]

_MARKETING_OWNERS = ["u_meghna", "u_tanvi", "u_arnav", "u_aadhira", "u_gunnika"]
_PRODUCT_OWNERS = ["u_soochana", "u_ronaly", "u_akasapu", "u_ranveer", "u_nikkitha", "u_akhila"]
_GENERAL_OWNERS = ["u_meghna", "u_soochana", "u_tanvi", "u_harsha", "u_shammi", "u_ronaly"]
_REPORT_OWNERS = ["u_rakshitha", "u_shammi", "u_harsha", "u_meghna"]
_FOLDER_OWNER_POOL = {
    "brand_guidelines": _GENERAL_OWNERS, "presentations": _GENERAL_OWNERS,
    "events": _GENERAL_OWNERS, "marketing_collaterals": _MARKETING_OWNERS,
    "campaigns": _MARKETING_OWNERS, "social_media": _MARKETING_OWNERS,
    "product_assets": _PRODUCT_OWNERS, "reports": _REPORT_OWNERS,
}

_FILE_TYPES = [
    ("pdf", "PDF", 300_000, 2_500_000), ("pptx", "PPT", 1_500_000, 9_000_000),
    ("docx", "DOCX", 150_000, 1_800_000), ("xlsx", "XLSX", 100_000, 900_000),
    ("png", "PNG", 200_000, 4_000_000),
]
_TITLE_BANK = {
    "brand_guidelines": ["Brand Guidelines v{n}", "Logo Usage Rules", "Color Palette Reference",
                        "Tone of Voice Guide", "Letterhead Template"],
    "marketing_collaterals": ["Sales One-Pager — {client}", "Partner Collateral Kit",
                              "Product Fact Sheet v{n}", "Pitch Deck — {client}"],
    "presentations": ["Quarterly Business Review Q{n}", "Board Update Deck",
                      "Client Kickoff Presentation", "Internal All-Hands Deck"],
    "campaigns": ["Campaign Timeline — {client}", "Creative Brief v{n}",
                 "Launch Plan — {client}", "Campaign Performance Recap"],
    "social_media": ["Social Post Pack v{n}", "Content Calendar — Month {n}",
                     "Hashtag & Caption Bank", "Influencer Outreach List"],
    "product_assets": ["UI Kit v{n}", "Feature Screenshot Pack", "Design System Reference",
                      "Product Spec — Module {n}"],
    "events": ["Run of Show — {client} Summit", "Attendee List v{n}", "Booth Design Deck"],
    "reports": ["Monthly Spend Report", "Vendor Invoice Log v{n}", "Cost Center Summary"],
}
_HEADLINE_DOCS = [
    {"doc_id": "doc_hl_01", "folder_id": "presentations", "title": "Product Overview Presentation",
     "ext": "pptx", "owner_id": "u_akasapu", "project_id": "proj_kq", "status": "approved",
     "size": 8_700_000, "days_ago": 2},
    {"doc_id": "doc_hl_02", "folder_id": "campaigns", "title": "Campaign Brief - Q3 2026",
     "ext": "docx", "owner_id": "u_tanvi", "project_id": "proj_om", "status": "pending",
     "size": 1_200_000, "days_ago": 3},
    {"doc_id": "doc_hl_03", "folder_id": "reports", "title": "Marketing Budget Tracker",
     "ext": "xlsx", "owner_id": "u_meghna", "project_id": "proj_sv", "status": "approved",
     "size": 520_000, "days_ago": 4},
    {"doc_id": "doc_hl_04", "folder_id": "brand_guidelines", "title": "FlyNava Logo Pack",
     "ext": "zip", "owner_id": "u_meghna", "project_id": None, "status": "approved",
     "size": 12_800_000, "days_ago": 5},
    {"doc_id": "doc_hl_05", "folder_id": "social_media", "title": "Social Media Calendar - July",
     "ext": "pdf", "owner_id": "u_akasapu", "project_id": None, "status": "draft",
     "size": 1_100_000, "days_ago": 6},
    {"doc_id": "doc_hl_06", "folder_id": "events", "title": "Event Deck - Aviation Summit",
     "ext": "pptx", "owner_id": "u_gunnika", "project_id": "proj_om", "status": "pending",
     "size": 5_600_000, "days_ago": 7},
]
_DOC_STATUSES = ["approved", "approved", "approved", "pending", "draft"]


def _seed_documents(now: dt.datetime, names: dict[str, str]) -> list[dict]:
    """~128 documents across the 8 folders — a handful of named "headline"
    docs matching the reference mockup exactly, the rest generated to fill
    each folder up to its target count with real-roster owners and varied
    file types/statuses/dates."""
    rng = random.Random(20260713)
    out: list[dict] = []
    seen_by_folder: dict[str, int] = {}

    for h in _HEADLINE_DOCS:
        seen_by_folder[h["folder_id"]] = seen_by_folder.get(h["folder_id"], 0) + 1
        updated = now - dt.timedelta(days=h["days_ago"])
        out.append({
            "doc_id": h["doc_id"], "title": h["title"], "kind": "document",
            "folder_id": h["folder_id"], "project_id": h["project_id"],
            "filename": f"{h['title']}.{h['ext']}", "file_type": h["ext"],
            "size": h["size"], "uploaded_by": h["owner_id"],
            "uploaded_by_name": names.get(h["owner_id"]), "status": h["status"],
            "created_at": updated, "updated_at": updated,
            "decided_by": "u_ceo" if h["status"] == "approved" else None,
            "decided_at": updated if h["status"] == "approved" else None,
            "comment": "", "path": None, "source": "seed",
            "shared_with": [], "starred_by": [], "downloads": rng.randint(0, 40),
        })

    for folder in FOLDERS:
        fid = folder["folder_id"]
        owners = _FOLDER_OWNER_POOL[fid]
        titles = _TITLE_BANK[fid]
        remaining = folder["target_count"] - seen_by_folder.get(fid, 0)
        for i in range(remaining):
            ext, _label, size_min, size_max = rng.choice(_FILE_TYPES)
            title = titles[i % len(titles)].format(n=i + 1, client=rng.choice(
                ["Kenya Airways", "Oman Airways", "Saudia Airlines", "FlyNava"]))
            owner_id = owners[i % len(owners)]
            status = rng.choice(_DOC_STATUSES)
            days_ago = rng.randint(1, 90)
            updated = now - dt.timedelta(days=days_ago)
            doc_id = f"doc_{fid}_{i + 1:03d}"
            out.append({
                "doc_id": doc_id, "title": title, "kind": "document",
                "folder_id": fid, "project_id": None,
                "filename": f"{title}.{ext}", "file_type": ext,
                "size": rng.randint(size_min, size_max), "uploaded_by": owner_id,
                "uploaded_by_name": names.get(owner_id), "status": status,
                "created_at": updated, "updated_at": updated,
                "decided_by": "u_ceo" if status == "approved" else None,
                "decided_at": updated if status == "approved" else None,
                "comment": "", "path": None, "source": "seed",
                "shared_with": [], "starred_by": [], "downloads": rng.randint(0, 30),
            })
    return out


# --- Enterprise Reporting Hub: report definitions ---
# Real-roster owners; confidential defs are additionally allowlisted (everyone
# else is filtered out by `report_store.report_visible` regardless of role).
# Run history + AWS cost/utilization data are seeded once the simulated AWS
# connector exists (see `_seed_report_runs` / `integrations/aws_sim.py`),
# so historical run snapshots for the AWS-domain reports have real numbers.
REPORT_DEFS: list[dict] = [
    {"report_id": "rep_bug_summary", "name": "Bug Status Summary",
     "description": "Open/closed bug breakdown for KQ production support.",
     "domain": "development", "type": "tabular", "owner_id": "u_harsha",
     "sections": [{"kind": "tasks_table", "params": {"bug_only": True}, "title": None},
                  {"kind": "tasks_breakdown", "params": {"bug_only": True, "group_by": "status"}, "title": None}],
     "visibility": "org", "access": {"roles": [], "teams": []}, "confidential": False,
     "allowed_user_ids": [], "recipients": ["admin@flynava.ai", "harsha.varlani@flynava.ai"],
     "schedule": {"frequency": "daily", "time": "09:00"}},
    {"report_id": "rep_team_progress", "name": "Team Task Progress",
     "description": "Task progress across teams and projects.",
     "domain": "development", "type": "tabular", "owner_id": "u_murugan",
     "sections": [{"kind": "tasks_table", "params": {}, "title": None},
                  {"kind": "tasks_breakdown", "params": {"group_by": "status"}, "title": None}],
     "visibility": "restricted", "access": {"roles": ["manager", "team_lead"], "teams": []},
     "confidential": False, "allowed_user_ids": [], "recipients": ["murugan.p@flynava.ai"],
     "schedule": {"frequency": "weekly", "time": "09:30", "weekday": 0}},
    {"report_id": "rep_test_exec", "name": "Test Case Execution",
     "description": "Automation test run results and pass rate.",
     "domain": "qa", "type": "tabular", "owner_id": "u_prathima",
     "sections": [{"kind": "test_execution", "params": {}, "title": None},
                  {"kind": "test_execution_stats", "params": {}, "title": None}],
     "visibility": "org", "access": {"roles": [], "teams": []}, "confidential": False,
     "allowed_user_ids": [], "recipients": ["prathima.ds@flynava.ai"],
     "schedule": {"frequency": "weekly", "time": "17:00", "weekday": 4}},
    {"report_id": "rep_resource_util", "name": "Resource Utilization",
     "description": "Operations KPI trend and snapshot.",
     "domain": "operations", "type": "chart", "owner_id": "u_harsha",
     "sections": [{"kind": "kpi_stats", "params": {"module": "operations"}, "title": None},
                  {"kind": "kpi_trend", "params": {"module": "operations"}, "title": None}],
     "visibility": "restricted", "access": {"roles": ["manager"], "teams": []}, "confidential": False,
     "allowed_user_ids": [], "recipients": ["harsha.varlani@flynava.ai"],
     "schedule": {"frequency": "monthly", "time": "08:00", "day_of_month": 1}},
    {"report_id": "rep_campaign", "name": "Campaign Performance",
     "description": "Marketing funnel KPI trend.",
     "domain": "marketing", "type": "chart", "owner_id": "u_tanvi",
     "sections": [{"kind": "kpi_trend", "params": {"module": "marketing_sales"}, "title": None}],
     "visibility": "org", "access": {"roles": [], "teams": []}, "confidential": False,
     "allowed_user_ids": [], "recipients": ["tanvi.gupta@flynava.ai"],
     "schedule": {"frequency": "monthly", "time": "10:00", "day_of_month": 1}},
    {"report_id": "rep_mkt_funnel", "name": "Marketing Funnel Summary",
     "description": "Leads, conversion, pipeline snapshot.",
     "domain": "marketing", "type": "summary", "owner_id": "u_meghna",
     "sections": [{"kind": "kpi_stats", "params": {"module": "marketing_sales"}, "title": None}],
     "visibility": "org", "access": {"roles": [], "teams": []}, "confidential": False,
     "allowed_user_ids": [], "recipients": [], "schedule": None},
    {"report_id": "rep_doc_summary", "name": "Document Upload Summary",
     "description": "Document uploads by status and downloads.",
     "domain": "operations", "type": "tabular", "owner_id": "u_shammi",
     "sections": [{"kind": "documents_stats", "params": {}, "title": None}],
     "visibility": "org", "access": {"roles": [], "teams": []}, "confidential": False,
     "allowed_user_ids": [], "recipients": ["hr@flynava.ai"],
     "schedule": {"frequency": "monthly", "time": "09:00", "day_of_month": 1}},
    {"report_id": "rep_attendance", "name": "Attendance & Leave Summary",
     "description": "Attendance and leave request snapshot.",
     "domain": "hr", "type": "summary", "owner_id": "u_shammi",
     "sections": [{"kind": "attendance_summary", "params": {"days": 7}, "title": None},
                  {"kind": "leaves_summary", "params": {}, "title": None}],
     "visibility": "restricted", "access": {"roles": ["hr", "manager"], "teams": []}, "confidential": False,
     "allowed_user_ids": [], "recipients": ["hr@flynava.ai"],
     "schedule": {"frequency": "monthly", "time": "09:00", "day_of_month": 1}},
    {"report_id": "rep_payroll", "name": "Payroll Cost Summary",
     "description": "Monthly payroll cost totals.",
     "domain": "finance", "type": "tabular", "owner_id": "u_rakshitha",
     "sections": [{"kind": "payroll_summary", "params": {}, "title": None}],
     "visibility": "restricted", "access": {"roles": [], "teams": []}, "confidential": True,
     "allowed_user_ids": ["u_ceo", "u_shammi"], "recipients": ["admin@flynava.ai"],
     "schedule": {"frequency": "monthly", "time": "09:00", "day_of_month": 1}},
    {"report_id": "rep_budget_actual", "name": "Budget vs Actual",
     "description": "Revenue budget vs actual trend.",
     "domain": "finance", "type": "chart", "owner_id": "u_rakshitha",
     "sections": [{"kind": "finance_budget", "params": {"kpi_id": "fin_revenue_mtd"}, "title": None}],
     "visibility": "restricted", "access": {"roles": [], "teams": []}, "confidential": True,
     "allowed_user_ids": ["u_ceo"], "recipients": ["admin@flynava.ai"],
     "schedule": {"frequency": "quarterly", "time": "09:00", "day_of_month": 1}},
    {"report_id": "rep_aws_monthly", "name": "AWS Monthly Cost",
     "description": "Total AWS spend trend.",
     "domain": "infrastructure", "type": "chart", "owner_id": "u_kalaiarasan",
     "sections": [{"kind": "aws_monthly_cost", "params": {}, "title": None}],
     "visibility": "restricted", "access": {"roles": [], "teams": []}, "confidential": True,
     "allowed_user_ids": ["u_ceo", "u_harsha"], "recipients": ["admin@flynava.ai"],
     "schedule": {"frequency": "monthly", "time": "07:00", "day_of_month": 1}},
    {"report_id": "rep_aws_services", "name": "AWS Cost by Service",
     "description": "Latest-month spend by AWS service.",
     "domain": "infrastructure", "type": "tabular", "owner_id": "u_kalaiarasan",
     "sections": [{"kind": "aws_cost_by_service", "params": {}, "title": None}],
     "visibility": "restricted", "access": {"roles": [], "teams": []}, "confidential": True,
     "allowed_user_ids": ["u_ceo", "u_harsha"], "recipients": ["admin@flynava.ai"],
     "schedule": {"frequency": "monthly", "time": "07:15", "day_of_month": 1}},
    {"report_id": "rep_aws_health", "name": "AWS Utilization & Health",
     "description": "Resource utilization and health dashboard.",
     "domain": "infrastructure", "type": "dashboard", "owner_id": "u_kalaiarasan",
     "sections": [{"kind": "aws_utilization", "params": {}, "title": None},
                  {"kind": "aws_resource_health", "params": {}, "title": None}],
     "visibility": "restricted", "access": {"roles": ["manager", "team_lead"], "teams": []},
     "confidential": False, "allowed_user_ids": [], "recipients": ["kalaiarasan.d@flynava.ai"],
     "schedule": {"frequency": "weekly", "time": "07:30", "weekday": 0}},
    {"report_id": "rep_aws_optim", "name": "AWS Optimization Recommendations",
     "description": "Cost-saving recommendations across AWS resources.",
     "domain": "infrastructure", "type": "summary", "owner_id": "u_kalaiarasan",
     "sections": [{"kind": "aws_optimization", "params": {}, "title": None},
                  {"kind": "aws_budget_vs_actual", "params": {}, "title": None}],
     "visibility": "restricted", "access": {"roles": [], "teams": []}, "confidential": True,
     "allowed_user_ids": ["u_ceo", "u_harsha"], "recipients": [], "schedule": None},
    {"report_id": "rep_my_tasks", "name": "My Task Summary",
     "description": "Personal task breakdown.",
     "domain": "development", "type": "summary", "owner_id": "u_oshan",
     "sections": [{"kind": "tasks_breakdown",
                  "params": {"assignee_id": "u_oshan", "group_by": "status"}, "title": None}],
     "visibility": "private", "access": {"roles": [], "teams": []}, "confidential": False,
     "allowed_user_ids": [], "recipients": [], "schedule": None},
]


def _seed_report_defs(db: Database, now: dt.datetime) -> None:
    from .report_scheduler import compute_next_run

    for spec in REPORT_DEFS:
        schedule = None
        if spec.get("schedule"):
            schedule = {**spec["schedule"], "recipients": spec.get("recipients", []),
                       "active": True, "last_run_at": None}
            schedule["next_run_at"] = compute_next_run(schedule, now)
        doc = {
            "report_id": spec["report_id"], "name": spec["name"], "description": spec["description"],
            "domain": spec["domain"], "project_id": spec.get("project_id"), "type": spec["type"],
            "sections": spec["sections"], "visibility": spec["visibility"], "access": spec["access"],
            "confidential": spec["confidential"], "allowed_user_ids": spec["allowed_user_ids"],
            "shared_with": [], "recipients": spec.get("recipients", []), "schedule": schedule,
            "owner_id": spec["owner_id"], "archived": False, "downloads": 0, "run_count": 0,
            "created_at": now, "updated_at": now, "seed": True,
        }
        db.report_defs.update_one({"report_id": doc["report_id"]}, {"$set": doc}, upsert=True)


def _seed_report_runs(db: Database, now: dt.datetime) -> None:
    """A handful of real run snapshots per seeded report — drives history/
    versioning, the stats tiles, and a realistic (not literally 100%)
    delivery-success rate. Guarded so this only ever runs once; it never
    regenerates on top of real usage."""
    if db.report_runs.count_documents({}) > 0:
        return
    from . import report_engine as engine

    rng = random.Random("report-runs-seed")
    users_by_id = {u["user_id"]: u for u in db.users.find({})}
    for rd in db.report_defs.find({}):
        owner = users_by_id.get(rd["owner_id"])
        if not owner:
            continue
        n = rng.randint(2, 4)
        # Oldest first, so later calls (higher version numbers) land closer
        # to "now" — keeps version order consistent with chronological order.
        for days_ago in sorted(rng.sample(range(1, 30), n), reverse=True):
            try:
                run = engine.run_report(db, rd, owner,
                                        triggered_by=rng.choice(["manual", "schedule"]))
            except Exception:  # noqa: BLE001 - one bad def shouldn't break seeding
                continue
            at = now - dt.timedelta(days=days_ago, hours=rng.randint(0, 23))
            # "error" here models a historical delivery failure — send_email()
            # itself only ever returns sent/preview; this is seed-only variety.
            status_ = rng.choices(["sent", "preview", "error"], weights=[55, 40, 5])[0]
            db.report_runs.update_one({"run_id": run["run_id"]}, {"$set": {
                "at": at, "recipients": rd.get("recipients", []),
                "delivery": {"status": status_, "detail": "seed history"},
            }})
            downloads_inc = rng.randint(0, 6)
            if downloads_inc:
                db.report_defs.update_one({"report_id": rd["report_id"]},
                                          {"$inc": {"downloads": downloads_inc}})


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
        doc = {k: v for k, v in p.items() if k != "open_tasks_target"}
        db.projects.update_one({"project_id": doc["project_id"]},
                               {"$set": {**doc, "created_at": now}}, upsert=True)

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

    for f in FOLDERS:
        folder = {k: v for k, v in f.items() if k != "target_count"}
        db.folders.update_one({"folder_id": folder["folder_id"]},
                              {"$set": {**folder, "created_by": "u_ceo", "created_at": now}},
                              upsert=True)

    for d in _seed_documents(now, names):
        db.documents.update_one({"doc_id": d["doc_id"]}, {"$set": d}, upsert=True)

    _seed_report_defs(db, now)
    _seed_crm(db, now)

    from ..integrations.aws_sim import AwsSimConnector
    from .ingest import run_connector

    run_connector(db, AwsSimConnector())
    _seed_report_runs(db, now)


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
                 "notifications", "automation_scripts", "product_docs",
                 "kpi_values", "kpi_defs", "folders", "documents",
                 "report_defs", "report_runs", "report_views",
                 "aws_costs", "aws_resources", "aws_budgets",
                 "crm_contacts", "project_invoices"):
        db[coll].delete_many({})
    seed(db)
    # Compute the live KPI values now so dashboards show real numbers (the
    # seeded demo_history gives each card its trailing sparkline; this appends
    # the real current value as the latest point).
    from ..kpi import engine
    engine.run_all(db)
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
