"""Rotate the seeded demo-account passwords on a target database.

`README.md` publishes `Passw0rd!` for eight `@flynava.ai` demo accounts, and
the repo is public — so those credentials are effectively anonymous logins
against whatever database the deployed backend points at. This replaces them
with per-account random passwords and prints the result exactly once.

    python -m scripts.rotate_demo_passwords --target atlas
    python -m scripts.rotate_demo_passwords --target atlas --apply

Nothing is written without --apply. Accounts outside the demo set are never
touched, and a demo account whose password is already non-default is skipped
unless --force is given.
"""
from __future__ import annotations

import argparse
import os
import secrets
import string
import sys
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import PyMongoError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import hash_password, verify_password  # noqa: E402

DEFAULT_PASSWORD = "Passw0rd!"
DEMO_EMAILS = [
    "admin@flynava.ai", "leadership@flynava.ai", "manager@flynava.ai",
    "hr@flynava.ai", "employee@flynava.ai", "marketing@flynava.ai",
    "investor@flynava.ai", "partner@flynava.ai",
]
LOCAL_URI = "mongodb://127.0.0.1:27017"
DB_NAME = os.environ.get("MONGO_DB", "io")
ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_"


def _load_dotenv() -> None:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


def _uri(which: str) -> str:
    if which == "local":
        return LOCAL_URI
    uri = os.environ.get("ATLAS_URI", "")
    if not uri:
        sys.exit("ATLAS_URI is not set — add it to backend/.env (gitignored).")
    return uri


def main() -> None:
    _load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", choices=["local", "atlas"], required=True)
    ap.add_argument("--apply", action="store_true", help="required to actually write")
    ap.add_argument("--force", action="store_true",
                    help="rotate even if the password is no longer the default")
    args = ap.parse_args()

    client = MongoClient(_uri(args.target), serverSelectionTimeoutMS=15000)
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        sys.exit(f"cannot reach {args.target}: {type(exc).__name__}: {exc}")
    db = client[DB_NAME]

    plan: list[tuple[str, str]] = []
    for email in DEMO_EMAILS:
        user = db.users.find_one({"email": email})
        if not user:
            print(f"  {email:28} absent — skipped")
            continue
        if not args.force and not verify_password(
                DEFAULT_PASSWORD, user.get("password_hash", "")):
            print(f"  {email:28} already rotated — skipped (use --force to override)")
            continue
        plan.append((email, "".join(secrets.choice(ALPHABET) for _ in range(20))))

    if not plan:
        print("\nnothing to rotate.")
        return

    if not args.apply:
        print(f"\ndry run — {len(plan)} account(s) would be rotated. "
              f"re-run with --apply to write.")
        return

    print(f"\n{'email':28} new password")
    print("-" * 56)
    for email, pw in plan:
        db.users.update_one({"email": email},
                            {"$set": {"password_hash": hash_password(pw)}})
        print(f"{email:28} {pw}")
    print("-" * 56)
    print("SAVE THESE NOW — they are not stored anywhere and not recoverable.")
    print("Then remove the credential block from README.md:48-50.")


if __name__ == "__main__":
    main()
