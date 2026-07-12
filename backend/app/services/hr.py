"""HR module — employee master, payslips, leaves, and the attendance ERP.

Employee names are harvested from OpenProject assignees where available (so the
directory feels real), topped up with the seeded login users. Payslips and leave
balances are generated deterministically. Attendance is ingested from a biometric
CSV export, stored, summarised, and emailed.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import random
import uuid

from pymongo.database import Database

DESIGNATIONS = {
    "eng": ["Software Engineer", "Senior Engineer", "QA Engineer", "Tech Lead", "DevOps Engineer"],
    "hr": ["HR Executive", "HR Manager", "Recruiter"],
    "fin": ["Accountant", "Finance Analyst", "Finance Manager"],
    "mkt": ["Marketing Executive", "Content Lead", "SEO Analyst"],
    "ui": ["UI Designer", "UX Designer", "UI Manager"],
    "exec": ["Director", "VP", "Chief of Staff"],
}
DEPTS = list(DESIGNATIONS)
LEAVE_TYPES = ["Casual", "Sick", "Earned"]


def _email_from_name(name: str) -> str:
    slug = "".join(c for c in name.lower() if c.isalnum() or c == " ").strip()
    parts = slug.split()
    handle = ".".join(parts[:2]) if parts else "employee"
    return f"{handle}@flynava.ai"


def _salary(band: int) -> dict:
    gross = band
    basic = round(gross * 0.5)
    hra = round(gross * 0.2)
    allowances = gross - basic - hra
    pf = round(basic * 0.12)
    tax = round(gross * 0.08)
    net = gross - pf - tax
    return {"gross": gross, "basic": basic, "hra": hra, "allowances": allowances,
            "pf": pf, "tax": tax, "net": net}


def _recent_months(n: int) -> list[str]:
    out, d = [], dt.date.today().replace(day=1)
    for _ in range(n):
        d = (d - dt.timedelta(days=1)).replace(day=1)
        out.append(d.strftime("%Y-%m"))
    return out


def seed_hr(db: Database) -> dict:
    """Idempotent-ish: (re)builds the HR collections. Returns counts."""
    rng = random.Random(42)
    db.employees.delete_many({})
    db.payslips.delete_many({})
    db.leaves.delete_many({})

    # 1) login users become employees (so 'My Payslip' works for demo logins).
    # Org users carry department + designation now — keep them in sync here.
    roster: list[tuple[str, str, str, str | None]] = []  # (name, email, dept, designation)
    for u in db.users.find({}):
        dept = u.get("department") if u.get("department") in DESIGNATIONS else "eng"
        roster.append((u["name"], u["email"], dept, u.get("designation")))

    # 2) harvest distinct OpenProject assignees as extra employees
    seen = {e.lower() for _, e, _, _ in roster}
    op_names = {t.get("assignee") for t in db.tasks.find(
        {"source_system": "openproject", "assignee": {"$ne": None}}, {"assignee": 1})}
    for name in sorted(n for n in op_names if n):
        email = _email_from_name(name)
        if email in seen:
            continue
        seen.add(email)
        roster.append((name, email, "eng", None))
        if len(roster) >= 30:
            break

    months = _recent_months(3)
    emp_ids = []
    for i, (name, email, dept, designation) in enumerate(roster, start=1):
        emp_id = f"E{i:04d}"
        emp_ids.append((emp_id, name))
        band = rng.choice([45000, 55000, 68000, 82000, 95000, 120000])
        emp = {
            "emp_id": emp_id, "name": name, "email": email.lower(),
            "designation": designation or rng.choice(DESIGNATIONS[dept]),
            "department": dept,
            "status": "active",
            "doj": (dt.date.today() - dt.timedelta(days=rng.randint(120, 1800))).isoformat(),
            "leave_balance": {"Casual": rng.randint(2, 12), "Sick": rng.randint(1, 10),
                              "Earned": rng.randint(0, 18)},
            "salary": _salary(band),
        }
        db.employees.insert_one(emp)
        for m in months:
            db.payslips.insert_one({
                "emp_id": emp_id, "month": m, **_salary(band),
                "lop_days": rng.choice([0, 0, 0, 1, 2]),
            })
        for _ in range(rng.randint(1, 3)):
            frm = dt.date.today() - dt.timedelta(days=rng.randint(5, 120))
            days = rng.randint(1, 3)
            db.leaves.insert_one({
                "leave_id": uuid.uuid4().hex[:8], "emp_id": emp_id,
                "type": rng.choice(LEAVE_TYPES), "from": frm.isoformat(),
                "to": (frm + dt.timedelta(days=days - 1)).isoformat(), "days": days,
                "status": rng.choice(["Approved", "Approved", "Pending"]),
            })

    return {"employees": len(emp_ids), "months": months}


# --- Reads ---
def _clean(doc: dict) -> dict:
    doc.pop("_id", None)
    return doc


def list_employees(db: Database) -> list[dict]:
    return [_clean(e) for e in db.employees.find().sort("emp_id", 1)]


def get_employee(db: Database, emp_id: str) -> dict | None:
    e = db.employees.find_one({"emp_id": emp_id})
    if not e:
        return None
    e = _clean(e)
    e["payslips"] = [_clean(p) for p in db.payslips.find({"emp_id": emp_id}).sort("month", -1)]
    e["leaves"] = [_clean(x) for x in db.leaves.find({"emp_id": emp_id}).sort("from", -1)]
    return e


def employee_by_email(db: Database, email: str) -> dict | None:
    e = db.employees.find_one({"email": email.lower()})
    return get_employee(db, e["emp_id"]) if e else None


# --- Leave decisions (shared by the request-approval engine and the HR
# Pending Leaves queue below — one place decrements a balance) ---
def decrement_leave_balance(db: Database, emp_id: str, leave_type: str, days: int) -> dict:
    """Floors at 0; insufficient balance is flagged, not blocked."""
    emp = db.employees.find_one({"emp_id": emp_id})
    current = emp.get("leave_balance", {}).get(leave_type, 0) if emp else 0
    new_balance = max(0, current - days)
    if emp:
        db.employees.update_one({"emp_id": emp_id},
                                {"$set": {f"leave_balance.{leave_type}": new_balance}})
    return {"balance_before": current, "balance_after": new_balance,
            "insufficient": current < days}


def list_pending_leaves(db: Database) -> list[dict]:
    """Seeded/historical leave entries awaiting an HR decision (distinct from
    the request-approval flow in services/approvals.py — these are leave rows
    already on an employee's record, e.g. from a legacy import)."""
    rows = [_clean(r) for r in db.leaves.find({"status": "Pending"}).sort("from", 1)]
    emp_ids = {r["emp_id"] for r in rows}
    emps = {e["emp_id"]: e for e in
            db.employees.find({"emp_id": {"$in": list(emp_ids)}},
                              {"emp_id": 1, "name": 1, "department": 1})}
    for r in rows:
        e = emps.get(r["emp_id"])
        r["emp_name"] = e["name"] if e else r["emp_id"]
        r["department"] = e.get("department") if e else None
    return rows


def decide_leave(db: Database, leave_id: str, decision: str) -> dict | None:
    """decision: 'Approved' or 'Rejected'. Approving decrements the balance."""
    leave = db.leaves.find_one({"leave_id": leave_id, "status": "Pending"})
    if not leave:
        return None
    db.leaves.update_one({"leave_id": leave_id}, {"$set": {"status": decision}})
    result = {"leave_id": leave_id, "emp_id": leave["emp_id"], "status": decision}
    if decision == "Approved":
        result["balance"] = decrement_leave_balance(
            db, leave["emp_id"], leave["type"], leave["days"])
    return result


# --- Attendance (biometric ERP) ---
def _pick(headers: list[str], *needles: str) -> str | None:
    for h in headers:
        low = h.lower()
        if any(n in low for n in needles):
            return h
    return None


def parse_attendance(raw: bytes) -> list[dict]:
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    h_status = _pick(headers, "status")
    h_date = _pick(headers, "date")
    h_out = _pick(headers, "out")
    h_in = _pick(headers, "in", "punch")
    h_name = _pick(headers, "name", "employee")
    h_emp = _pick(headers, "code", "emp id", "empid", "id")

    rows: list[dict] = []
    for r in reader:
        name = (r.get(h_name) or "").strip() if h_name else ""
        if not name and not (h_emp and r.get(h_emp)):
            continue
        in_t = (r.get(h_in) or "").strip() if h_in else ""
        out_t = (r.get(h_out) or "").strip() if h_out else ""
        status = (r.get(h_status) or "").strip() if h_status else ""
        if not status:
            status = "Present" if in_t and out_t else "Absent"
        rows.append({
            "emp_code": (r.get(h_emp) or "").strip() if h_emp else "",
            "name": name, "date": (r.get(h_date) or "").strip() if h_date else "",
            "in_time": in_t, "out_time": out_t, "status": status.title(),
            "hours": _hours(in_t, out_t),
        })
    return rows


def _hours(a: str, b: str) -> float | None:
    try:
        fmt = "%H:%M" if len(a) <= 5 else "%H:%M:%S"
        t1 = dt.datetime.strptime(a[:8], fmt if len(a) <= 5 else "%H:%M:%S")
        t2 = dt.datetime.strptime(b[:8], fmt if len(b) <= 5 else "%H:%M:%S")
        return round((t2 - t1).seconds / 3600, 2)
    except (ValueError, TypeError):
        return None


def _summary(rows: list[dict]) -> dict:
    s: dict[str, int] = {}
    for r in rows:
        s[r["status"]] = s.get(r["status"], 0) + 1
    return {"total": len(rows), "by_status": s}


def store_attendance(db: Database, rows: list[dict], uploaded_by: str,
                     filename: str) -> dict:
    upload_id = uuid.uuid4().hex[:10]
    now = dt.datetime.now(dt.timezone.utc)
    for r in rows:
        db.attendance.insert_one({**r, "upload_id": upload_id,
                                  "uploaded_by": uploaded_by, "uploaded_at": now})
    db.attendance_uploads.insert_one({
        "upload_id": upload_id, "filename": filename, "rows": len(rows),
        "uploaded_by": uploaded_by, "uploaded_at": now, "summary": _summary(rows)})
    return {"upload_id": upload_id, "rows": len(rows), "summary": _summary(rows),
            "preview": rows[:200]}


def render_attendance_html(title: str, rows: list[dict], summary: dict) -> str:
    import html as h

    def td(v):
        return f'<td style="border:1px solid #d9d9d9;padding:6px 10px;font-size:13px;">{h.escape(str(v or "—"))}</td>'

    head = "".join(
        f'<th style="border:1px solid #d9d9d9;padding:6px 10px;background:#157f52;'
        f'color:#fff;font-size:13px;text-align:left;">{c}</th>'
        for c in ["Employee", "Date", "In", "Out", "Hours", "Status"])
    body = "".join(
        "<tr>" + td(r["name"]) + td(r["date"]) + td(r["in_time"]) + td(r["out_time"])
        + td(r["hours"]) + td(r["status"]) + "</tr>" for r in rows)
    chips = " · ".join(f"{k}: {v}" for k, v in summary["by_status"].items())
    return (
        f'<div style="font-family:Segoe UI,Arial,sans-serif;color:#1f1f1f;">'
        f"<p>Hi Team,</p><p>Attendance report — {summary['total']} record(s). {chips}</p>"
        f'<table style="border-collapse:collapse;margin-top:8px;">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
        f'<p style="margin-top:12px;color:#6b7280;font-size:12px;">'
        f"Generated by IO — FlyNava Technologies</p></div>")


def _last_weekdays(n: int) -> list[dt.date]:
    """Last n weekdays (Mon-Fri) ending today, oldest first."""
    out: list[dt.date] = []
    d = dt.date.today()
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= dt.timedelta(days=1)
    out.reverse()
    return out


_SEED_ATTENDANCE_TAG = "seed_history"


def seed_attendance(db: Database) -> int:
    """7 weekdays of biometric-style attendance for every seeded employee —
    powers the CEO 'attendance today' tile and each person's attendance card.
    Scoped delete (only rows tagged seed_history) so it never touches real
    attendance uploaded via the HR Attendance ERP."""
    db.attendance.delete_many({"upload_id": _SEED_ATTENDANCE_TAG})
    rng = random.Random(7)
    now = dt.datetime.now(dt.timezone.utc)
    dates = _last_weekdays(7)
    rows = 0
    for e in db.employees.find({}, {"emp_id": 1, "name": 1}):
        for d in dates:
            roll = rng.random()
            if roll < 0.10:
                status, in_t, out_t = "Absent", "", ""
            elif roll < 0.30:
                status = "Late"
                in_t = rng.choice(["09:35", "09:50", "10:05", "10:20"])
                out_t = rng.choice(["18:10", "18:30", "19:00"])
            else:
                status = "Present"
                in_t = rng.choice(["08:55", "09:05", "09:15", "09:25"])
                out_t = rng.choice(["18:00", "18:15", "18:30"])
            db.attendance.insert_one({
                "emp_code": e["emp_id"], "name": e["name"], "date": d.isoformat(),
                "in_time": in_t, "out_time": out_t, "status": status,
                "hours": _hours(in_t, out_t) if in_t and out_t else None,
                "upload_id": _SEED_ATTENDANCE_TAG, "uploaded_by": "system",
                "uploaded_at": now,
            })
            rows += 1
    return rows


def attendance_for(db: Database, name: str, days: int = 7) -> dict:
    """Recent attendance rows + a summary for one person, by employee name
    (matches the name-based join used across tasks/attendance elsewhere)."""
    rows = [_clean(r) for r in
            db.attendance.find({"name": name}).sort("date", -1).limit(days)]
    late = sum(1 for r in rows if r["status"] == "Late")
    absent = sum(1 for r in rows if r["status"] == "Absent")
    present_hours = [r["hours"] for r in rows if r.get("hours") is not None]
    avg_hours = round(sum(present_hours) / len(present_hours), 1) if present_hours else None
    return {"rows": rows, "late_count": late, "absent_count": absent,
            "present_count": len(rows) - late - absent, "avg_hours": avg_hours}


def sample_csv(db: Database) -> str:
    """A realistic biometric export for the seeded employees (for demo upload)."""
    rng = random.Random()
    today = dt.date.today().isoformat()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Emp Code", "Employee Name", "Date", "In Time", "Out Time", "Status"])
    for e in db.employees.find().limit(25):
        roll = rng.random()
        if roll < 0.08:
            w.writerow([e["emp_id"], e["name"], today, "", "", "Absent"])
        else:
            ih = rng.choice(["09:02", "09:15", "09:47", "10:05", "08:55"])
            oh = rng.choice(["18:05", "18:32", "19:10", "17:50", "18:00"])
            late = ih > "09:30"
            w.writerow([e["emp_id"], e["name"], today, ih, oh,
                        "Late" if late else "Present"])
    return out.getvalue()
