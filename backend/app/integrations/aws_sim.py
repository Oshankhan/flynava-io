"""Simulated AWS Cost Explorer / CloudWatch connector.

No real AWS credentials or API calls — generates a deterministic 12-month
cost + utilization dataset so the Infrastructure report domain (monthly
cost, cost by service, utilization, resource health, spending trends,
optimization recommendations, budget vs actual) works out of the box in
this demo environment. Swapping in real `boto3` Cost Explorer/CloudWatch
calls later only touches `fetch()` — the registry entry, `upsert()`, and
every AWS report builder in `services/report_engine.py` stay the same.
"""
from __future__ import annotations

import datetime as dt
import random

from pymongo.database import Database

from .base import Connector

_SERVICES = [("EC2", 1400), ("RDS", 620), ("S3", 310), ("CloudFront", 180), ("Lambda", 95)]
_RESOURCES = [
    ("EC2", "web-server-1", "us-east-1"), ("EC2", "web-server-2", "us-east-1"),
    ("EC2", "web-server-3", "ap-south-1"), ("EC2", "api-server-1", "ap-south-1"),
    ("EC2", "api-server-2", "eu-west-1"),
    ("RDS", "prod-db-primary", "us-east-1"), ("RDS", "prod-db-replica", "us-east-1"),
    ("RDS", "analytics-db", "ap-south-1"),
    ("S3", "app-assets-bucket", "us-east-1"), ("S3", "backups-bucket", "us-east-1"),
    ("S3", "logs-bucket", "ap-south-1"),
    ("Lambda", "image-resize-fn", "us-east-1"), ("Lambda", "notification-fn", "ap-south-1"),
    ("Lambda", "report-generator-fn", "ap-south-1"),
    ("CloudFront", "cdn-distribution-main", "us-east-1"),
]
_MONTHS = 12
_SEED = "aws-sim-2026"


def _recent_months(n: int) -> list[str]:
    out, d = [], dt.date.today().replace(day=1)
    for _ in range(n):
        out.append(d.strftime("%Y-%m"))
        d = (d - dt.timedelta(days=1)).replace(day=1)
    out.reverse()
    return out


class AwsSimConnector(Connector):
    source = "aws"

    def fetch(self) -> dict:
        rng = random.Random(_SEED)
        months = _recent_months(_MONTHS)
        costs: list[dict] = []
        month_totals: dict[str, float] = {}
        for service, base in _SERVICES:
            cost = float(base)
            for m in months:
                cost *= 1 + rng.uniform(0.01, 0.04)  # gentle month-over-month growth
                jittered = round(cost * rng.uniform(0.95, 1.05), 2)
                costs.append({"source_id": f"{m}:{service}", "month": m,
                             "service": service, "cost": jittered})
                month_totals[m] = month_totals.get(m, 0) + jittered

        resources: list[dict] = []
        counts = {s: sum(1 for svc, _, _ in _RESOURCES if svc == s) for s, _ in _SERVICES}
        latest_by_service = {s: next(c["cost"] for c in reversed(costs) if c["service"] == s)
                             for s, _ in _SERVICES}
        for i, (service, name, region) in enumerate(_RESOURCES):
            utilization = round(rng.uniform(8, 92), 1)
            # Health is modeled independently of utilization — a healthy
            # resource can still be under-utilized, and vice versa — so the
            # optimization builder's two recommendation types (rightsizing
            # vs. health) don't always fire on the same resources.
            health = rng.choices(["ok", "warning", "critical"], weights=[70, 20, 10])[0]
            monthly_cost = round(latest_by_service[service] / counts[service] * rng.uniform(0.8, 1.2), 2)
            resources.append({"source_id": f"res-{i + 1:03d}", "service": service, "name": name,
                              "region": region, "utilization_pct": utilization, "health": health,
                              "monthly_cost": monthly_cost})

        budgets = [{"source_id": m, "month": m, "amount": round(month_totals[m] * 1.08, 2)}
                  for m in months]
        return {"costs": costs, "resources": resources, "budgets": budgets}

    def upsert(self, db: Database, data: dict) -> tuple[int, int]:
        fetched = processed = 0
        for coll_name, rows in (("aws_costs", data.get("costs", [])),
                                ("aws_resources", data.get("resources", [])),
                                ("aws_budgets", data.get("budgets", []))):
            coll = db[coll_name]
            for row in rows:
                fetched += 1
                coll.update_one({"source_system": self.source, "source_id": row["source_id"]},
                               {"$set": {**row, "source_system": self.source}}, upsert=True)
                processed += 1
        return fetched, processed
