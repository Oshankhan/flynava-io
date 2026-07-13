"""Per-project CRM: marketing-only account contacts, finance-only billing."""
from __future__ import annotations


def test_marketing_l1_lists_contacts(client, auth_header):
    r = client.get("/api/v1/projects/proj_kq/contacts",
                   headers=auth_header("arnav.jain@flynava.ai"))
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 18
    primary = next(c for c in rows if c["contact_type"] == "primary")
    assert primary["name"] == "Animesh Sharma"


def test_non_marketing_denied_even_at_l3(client, auth_header):
    denied_employee = client.get("/api/v1/projects/proj_kq/contacts",
                                 headers=auth_header("manas.ankarla@flynava.ai"))
    assert denied_employee.status_code == 403

    denied_manager = client.get("/api/v1/projects/proj_kq/contacts",
                                headers=auth_header("harsha.varlani@flynava.ai"))
    assert denied_manager.status_code == 403


def test_multi_role_marketing_manager_allowed(client, auth_header):
    # Meghna is a "manager" whose extra_roles include "marketing".
    r = client.get("/api/v1/projects/proj_om/contacts",
                   headers=auth_header("meghna.mehra@flynava.ai"))
    assert r.status_code == 200


def test_super_admin_allowed(client, auth_header):
    r = client.get("/api/v1/projects/proj_sv/contacts",
                   headers=auth_header("admin@flynava.ai"))
    assert r.status_code == 200
    assert len(r.json()) == 10


def test_contacts_404_for_unknown_project(client, auth_header):
    r = client.get("/api/v1/projects/does_not_exist/contacts",
                   headers=auth_header("arnav.jain@flynava.ai"))
    assert r.status_code == 404


def test_create_and_update_contact(client, auth_header):
    h = auth_header("tanvi.gupta@flynava.ai")
    created = client.post("/api/v1/projects/proj_kq/contacts", headers=h,
                          json={"name": "New Contact", "title": "Ops Lead",
                               "department": "Operations", "email": "new@kenya-airways.com",
                               "phone": "+254 700 000 000", "contact_type": "other",
                               "status": "active"})
    assert created.status_code == 200
    contact_id = created.json()["contact_id"]

    updated = client.patch(f"/api/v1/projects/proj_kq/contacts/{contact_id}", headers=h,
                           json={"status": "inactive"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "inactive"


def test_delete_contact_requires_marketing_l2(client, auth_header):
    h = auth_header("tanvi.gupta@flynava.ai")
    created = client.post("/api/v1/projects/proj_kq/contacts", headers=h,
                          json={"name": "Temp Contact"})
    contact_id = created.json()["contact_id"]

    denied = client.delete(f"/api/v1/projects/proj_kq/contacts/{contact_id}",
                           headers=auth_header("arnav.jain@flynava.ai"))
    assert denied.status_code == 403

    ok = client.delete(f"/api/v1/projects/proj_kq/contacts/{contact_id}", headers=h)
    assert ok.status_code == 200


def test_billing_finance_only(client, auth_header):
    ok = client.get("/api/v1/projects/proj_kq/billing",
                    headers=auth_header("rakshitha.s@flynava.ai"))
    assert ok.status_code == 200
    body = ok.json()
    assert body["contract_value"] == 480000
    assert body["invoiced"] == 280000
    assert body["paid"] == 240000
    assert body["outstanding"] == 40000
    assert len(body["invoices"]) == 7

    denied = client.get("/api/v1/projects/proj_kq/billing",
                        headers=auth_header("arnav.jain@flynava.ai"))
    assert denied.status_code == 403

    admin_ok = client.get("/api/v1/projects/proj_kq/billing",
                          headers=auth_header("admin@flynava.ai"))
    assert admin_ok.status_code == 200


def test_billing_empty_for_prospect(client, auth_header):
    r = client.get("/api/v1/projects/proj_om/billing",
                   headers=auth_header("rakshitha.s@flynava.ai"))
    assert r.status_code == 200
    body = r.json()
    assert body["contract_value"] is None
    assert body["invoices"] == []
    assert body["invoiced"] == 0


def test_create_invoice_finance_only(client, auth_header):
    denied = client.post("/api/v1/projects/proj_kq/invoices",
                         headers=auth_header("arnav.jain@flynava.ai"),
                         json={"number": "INV-KQ-2026-008", "date": "2026-08-05",
                              "amount": 40000})
    assert denied.status_code == 403

    ok = client.post("/api/v1/projects/proj_kq/invoices",
                     headers=auth_header("rakshitha.s@flynava.ai"),
                     json={"number": "INV-KQ-2026-008", "date": "2026-08-05",
                          "amount": 40000, "status": "pending"})
    assert ok.status_code == 200
    assert ok.json()["number"] == "INV-KQ-2026-008"

    billing = client.get("/api/v1/projects/proj_kq/billing",
                         headers=auth_header("rakshitha.s@flynava.ai")).json()
    assert len(billing["invoices"]) == 8
