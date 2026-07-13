"""Simulated AWS connector: deterministic, idempotent seed data feeding the
Infrastructure report domain's builders."""
from __future__ import annotations

from app.integrations.aws_sim import AwsSimConnector
from app.services.ingest import run_connector


def test_seed_populates_aws_collections(db):
    # seed() (via the `db` fixture) already ran the connector once.
    assert db.aws_costs.count_documents({}) == 12 * 5  # 12 months x 5 services
    assert db.aws_resources.count_documents({}) == 15
    assert db.aws_budgets.count_documents({}) == 12


def test_rerun_is_idempotent(db):
    before = db.aws_costs.count_documents({})
    log = run_connector(db, AwsSimConnector())
    assert log["status"] == "ok"
    assert db.aws_costs.count_documents({}) == before
    assert db.aws_resources.count_documents({}) == 15


def test_aws_report_builders_return_non_empty_sections(client, auth_header):
    headers = auth_header("kalaiarasan.d@flynava.ai")  # owner of the AWS-domain defs

    health = client.post("/api/v1/reports/defs/rep_aws_health/run", headers=headers, json={}).json()
    util = next(s for s in health["sections"] if s["title"] == "Resource Utilization")
    res_health = next(s for s in health["sections"] if s["title"] == "Resource Health & Availability")
    assert len(util["rows"]) == 15
    assert len(res_health["rows"]) == 15

    monthly = client.post("/api/v1/reports/defs/rep_aws_monthly/run", headers=headers, json={}).json()
    assert len(monthly["sections"][0]["series"][0]["points"]) == 12

    services = client.post("/api/v1/reports/defs/rep_aws_services/run", headers=headers, json={}).json()
    assert len(services["sections"][0]["rows"]) == 5  # one row per AWS service

    optim = client.post("/api/v1/reports/defs/rep_aws_optim/run", headers=headers, json={}).json()
    text_section = next(s for s in optim["sections"] if s["kind"] == "text")
    assert text_section["text"]
    chart_section = next(s for s in optim["sections"] if s["kind"] == "chart")
    assert len(chart_section["series"]) == 2  # Actual + Budget
