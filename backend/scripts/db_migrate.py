"""Local -> Atlas data migration with a full pre-flight backup.

Three modes, in the order they are meant to be run:

    python -m scripts.db_migrate backup --target atlas   # rollback point
    python -m scripts.db_migrate report                  # dry run, changes nothing
    python -m scripts.db_migrate merge --apply           # the real thing

Merge semantics (chosen deliberately, see the conflict table in `report`):
documents are upserted from local into the target by *natural key* — the
unique indexes declared in `app/db.py::ensure_indexes`. A document present
only in the target is never touched, so nothing already live is lost. A
document present on both sides is overwritten by the local copy.

Collections without a unique index fall back to `_id`. That keeps target-only
documents safe, but it cannot recognise "same record, different ObjectId" —
those insert as duplicates. `report` counts that risk per collection before
you commit to anything.

Connection strings are read from env / backend/.env and are never printed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

from bson import json_util
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Natural keys := the unique indexes in app/db.py::ensure_indexes. `projects`
# has a non-unique (source_system, source_id) index, but that pair *is* the
# real identity of a project row, so it is used here too.
NATURAL_KEYS: dict[str, tuple[str, ...]] = {
    "users": ("email",),
    "departments": ("dept_id",),
    "teams": ("team_id",),
    "kpi_defs": ("kpi_id",),
    "kpi_explanations": ("kpi_id",),
    "crm_contacts": ("contact_id",),
    "project_invoices": ("invoice_id",),
    "ai_insights": ("insight_id",),
    "rag_chunks": ("chunk_id",),
    "milestones": ("milestone_id",),
    "task_journals": ("source_system", "source_id"),
    # `project_id` is null on 8 of 11 rows and `source_system` on 3 (manually
    # created projects never went through the OpenProject connector), so name
    # is the only field that actually identifies all of them.
    "projects": ("name",),
    "traffic_daily": ("date",),
    "startup_daily": ("date",),
    "ops_daily": ("date",),
    "central_monthly": ("month",),
    "org_monthly": ("month",),
    "marketing_monthly": ("month",),
    "finance_monthly": ("month",),
    "startup_monthly": ("month",),
    "ops_monthly": ("month",),
    "forecaster_monthly": ("month",),

    # No unique index, but each of these carries its own id field. Without
    # them the fallback is `_id`, and since local and prod were seeded from
    # separate `seed()` runs every ObjectId differs — a merge would then
    # insert a second copy of all 147 payslips and all 49 employees rather
    # than matching them. Verified: 147/147 payslips and 49/49 employees are
    # content-identical across the two databases.
    "payslips": ("emp_id", "month"),
    "employees": ("emp_id",),
    "attendance": ("emp_code", "date"),
    "leaves": ("leave_id",),
    "aws_budgets": ("source_system", "source_id"),
    "aws_costs": ("source_system", "source_id"),
    "aws_resources": ("source_system", "source_id"),
    "automation_scripts": ("script_id",),
    "compliance_items": ("item_id",),
    "documents": ("doc_id",),
    "folders": ("folder_id",),
    "integration_logs": ("source", "run_at"),
    # The same KPI is recalculated repeatedly for one period, so the timestamp
    # is part of the identity — without it 42 rows collapse into one.
    "kpi_values": ("kpi_id", "period_start", "calculated_at"),
    "meetings": ("meeting_id",),
    "notifications": ("notif_id",),
    "positions": ("pos_id",),
    "product_docs": ("pdoc_id",),
    "report_defs": ("report_id",),
    "report_runs": ("run_id",),
    # Two populations share this collection: OpenProject-synced rows carry
    # source_id with a null task_id, locally created rows the other way round.
    # Only the composite identifies both (891/891 distinct).
    "tasks": ("task_id", "source_system", "source_id"),
    # Append-only event log with no id of its own; this tuple is what makes
    # one entry distinct from the next.
    "audit_logs": ("actor_id", "action", "entity_id", "created_at"),
}

LOCAL_URI = "mongodb://127.0.0.1:27017"
DB_NAME = os.environ.get("MONGO_DB", "io")
BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"


def _load_dotenv() -> None:
    """Read backend/.env into os.environ without overwriting real env vars."""
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


def _atlas_uri() -> str:
    uri = os.environ.get("ATLAS_URI", "")
    if not uri:
        sys.exit(
            "ATLAS_URI is not set.\n"
            "Add it to backend/.env (which is gitignored):\n"
            "    ATLAS_URI=mongodb+srv://<user>:<pass>@cluster0.xxxxx.mongodb.net/\n"
            "Leave MONGO_URI pointing at local until the merge has succeeded."
        )
    return uri


def _connect(uri: str, label: str) -> MongoClient:
    client = MongoClient(uri, serverSelectionTimeoutMS=15000)
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        sys.exit(f"cannot reach {label}: {type(exc).__name__}: {exc}")
    return client


def _key_of(coll: str, doc: dict) -> tuple | None:
    """Natural key of `doc`, or None to fall back to `_id`.

    A missing field and an explicitly-null one mean the same thing here: some
    collections mix populations that each fill in only half the key (an
    OpenProject-synced task omits `task_id` outright, a locally created one
    omits `source_id`), so requiring every field to be present would leave
    both halves unkeyed. Only an all-null tuple is treated as no key at all.
    """
    fields = NATURAL_KEYS.get(coll)
    if not fields:
        return None
    key = tuple(doc.get(f) for f in fields)
    return None if all(v is None for v in key) else key


def cmd_backup(which: str) -> None:
    uri, label = (_atlas_uri(), "atlas") if which == "atlas" else (LOCAL_URI, "local")
    db = _connect(uri, label)[DB_NAME]
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = BACKUP_DIR / f"{label}-{stamp}.json"

    total = 0
    with out.open("w", encoding="utf-8") as fh:
        for coll in sorted(db.list_collection_names()):
            docs = list(db[coll].find({}))
            total += len(docs)
            fh.write(json_util.dumps({"collection": coll, "documents": docs}) + "\n")
            print(f"  {coll:32} {len(docs):>7}")
    size_mb = out.stat().st_size / 1_048_576
    print(f"\nbacked up {total} docs -> {out}  ({size_mb:.1f} MB)")
    print("restore with:  python -m scripts.db_migrate restore --file <path> --target <local|atlas>")


def cmd_restore(file: str, which: str) -> None:
    uri, label = (_atlas_uri(), "atlas") if which == "atlas" else (LOCAL_URI, "local")
    path = Path(file)
    if not path.exists():
        sys.exit(f"no such backup file: {path}")
    db = _connect(uri, label)[DB_NAME]
    print(f"!! restoring into {label} — each collection in the file is DROPPED first")
    if input("type RESTORE to continue: ").strip() != "RESTORE":
        sys.exit("aborted")
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        blob = json_util.loads(line)
        coll, docs = blob["collection"], blob["documents"]
        db[coll].drop()
        if docs:
            db[coll].insert_many(docs)
        print(f"  {coll:32} {len(docs):>7}")
    print("restore complete")


def _analyse(src_db, dst_db) -> list[dict]:
    rows = []
    for coll in sorted(set(src_db.list_collection_names()) |
                       set(dst_db.list_collection_names())):
        src_docs = list(src_db[coll].find({}))
        dst_docs = list(dst_db[coll].find({}))
        keyed = coll in NATURAL_KEYS

        if keyed:
            src_keys = {k for d in src_docs if (k := _key_of(coll, d)) is not None}
            dst_keys = {k for d in dst_docs if (k := _key_of(coll, d)) is not None}
        else:
            src_keys = {d["_id"] for d in src_docs}
            dst_keys = {d["_id"] for d in dst_docs}

        # A key that is not unique *within* a database is worse than no key:
        # several documents collapse onto one another and the extras are lost.
        collapse = (len(src_docs) - len(src_keys)) + (len(dst_docs) - len(dst_keys))

        rows.append({
            "collection": coll,
            "local": len(src_docs),
            "prod": len(dst_docs),
            "key": ",".join(NATURAL_KEYS[coll]) if keyed else "_id (fallback)",
            "overwrite": len(src_keys & dst_keys),
            "insert": len(src_keys - dst_keys),
            "prod_only": len(dst_keys - src_keys),
            "risky": not keyed and len(dst_docs) > 0,
            "collapse": collapse,
        })
    return rows


def cmd_report() -> None:
    src = _connect(LOCAL_URI, "local")[DB_NAME]
    dst = _connect(_atlas_uri(), "atlas")[DB_NAME]
    rows = _analyse(src, dst)

    print(f"{'collection':30} {'local':>6} {'prod':>6} {'overwr':>7} "
          f"{'insert':>7} {'prod-only':>10}  key")
    print("-" * 96)
    for r in rows:
        flag = "  <-- COLLAPSE" if r["collapse"] else ("  <-- dup risk" if r["risky"] else "")
        print(f"{r['collection']:30} {r['local']:>6} {r['prod']:>6} "
              f"{r['overwrite']:>7} {r['insert']:>7} {r['prod_only']:>10}  "
              f"{r['key']}{flag}")
    print("-" * 96)
    print(f"totals: local={sum(r['local'] for r in rows)} "
          f"prod={sum(r['prod'] for r in rows)} "
          f"overwrite={sum(r['overwrite'] for r in rows)} "
          f"insert={sum(r['insert'] for r in rows)} "
          f"prod-only-kept={sum(r['prod_only'] for r in rows)}")

    risky = [r for r in rows if r["risky"]]
    if risky:
        print("\n'dup risk' = no unique index, so identity falls back to _id. If prod")
        print("holds the same logical record under a different ObjectId, the local")
        print("copy inserts alongside it instead of replacing it:")
        for r in risky:
            print(f"  - {r['collection']}: {r['prod']} prod docs matched only by _id")

    collapsing = [r for r in rows if r["collapse"]]
    if collapsing:
        print("\nSTOP — these keys are not unique within a database, so documents")
        print("would collapse onto each other and the extras would be LOST:")
        for r in collapsing:
            print(f"  - {r['collection']}: {r['collapse']} doc(s) share a key "
                  f"({r['key']}) — widen the key before merging")
    else:
        print("\nkey uniqueness: OK — every key identifies exactly one document "
              "on both sides")


def cmd_merge(apply: bool) -> None:
    src = _connect(LOCAL_URI, "local")[DB_NAME]
    dst = _connect(_atlas_uri(), "atlas")[DB_NAME]

    if not apply:
        sys.exit("refusing to write without --apply (run `report` first)")

    latest = sorted(BACKUP_DIR.glob("atlas-*.json")) if BACKUP_DIR.exists() else []
    if not latest:
        sys.exit("no atlas backup found in backend/backups — run `backup --target atlas` first")
    print(f"rollback point: {latest[-1].name}")
    if input("type MERGE to write to production: ").strip() != "MERGE":
        sys.exit("aborted")

    ins = upd = 0
    for coll in sorted(src.list_collection_names()):
        c_ins = c_upd = 0
        for doc in src[coll].find({}):
            key = _key_of(coll, doc)
            # `.get()` mirrors _key_of: a field absent from the local document
            # queries as None, which Mongo matches against both missing and
            # explicitly-null fields on the target.
            flt = ({f: doc.get(f) for f in NATURAL_KEYS[coll]} if key is not None
                   else {"_id": doc["_id"]})
            existing = dst[coll].find_one(flt, {"_id": 1})
            if existing:
                # _id is immutable — keep the target's, replace everything else.
                body = {k: v for k, v in doc.items() if k != "_id"}
                dst[coll].replace_one({"_id": existing["_id"]}, body)
                c_upd += 1
            else:
                dst[coll].insert_one(doc)
                c_ins += 1
        ins, upd = ins + c_ins, upd + c_upd
        if c_ins or c_upd:
            print(f"  {coll:32} +{c_ins:<6} ~{c_upd}")

    print(f"\nmerged: {ins} inserted, {upd} overwritten, prod-only docs untouched")
    print("now rebuild indexes on the target:")
    print("  python -c \"from app.db import ensure_indexes; from pymongo import MongoClient; "
          "import os; ensure_indexes(MongoClient(os.environ['ATLAS_URI'])['io'])\"")


def main() -> None:
    _load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backup", help="dump a database to backend/backups/")
    b.add_argument("--target", choices=["local", "atlas"], required=True)

    r = sub.add_parser("restore", help="reload a dump (DROPS each collection first)")
    r.add_argument("--file", required=True)
    r.add_argument("--target", choices=["local", "atlas"], required=True)

    sub.add_parser("report", help="dry-run diff, writes nothing")

    m = sub.add_parser("merge", help="upsert local into atlas by natural key")
    m.add_argument("--apply", action="store_true", help="required to actually write")

    args = ap.parse_args()
    if args.cmd == "backup":
        cmd_backup(args.target)
    elif args.cmd == "restore":
        cmd_restore(args.file, args.target)
    elif args.cmd == "report":
        cmd_report()
    elif args.cmd == "merge":
        cmd_merge(args.apply)


if __name__ == "__main__":
    main()
