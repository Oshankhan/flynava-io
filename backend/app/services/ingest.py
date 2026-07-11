"""Run a connector, upsert its data, and always write an Integration_Log.

A failed fetch is caught and logged (status=error) without raising — the pipeline
survives bad integrations and can resume on the next scheduled/on-demand run
(PRD NFR-007, acceptance 18.1).
"""
from __future__ import annotations

import datetime as dt
import time

from pymongo.database import Database

from ..integrations.base import Connector


def run_connector(db: Database, connector: Connector) -> dict:
    run_at = dt.datetime.now(dt.timezone.utc)
    t0 = time.perf_counter()
    fetched = processed = 0
    errors: list[str] = []
    try:
        data = connector.fetch()
        fetched, processed = connector.upsert(db, data)
    except Exception as exc:  # noqa: BLE001 - record failure, never crash pipeline
        errors.append(str(exc))

    log = {
        "source": connector.source,
        "run_at": run_at,
        "records_fetched": fetched,
        "records_processed": processed,
        "errors": errors,
        "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
        "status": "error" if errors else "ok",
    }
    db.integration_logs.insert_one(log)
    log.pop("_id", None)
    return log
