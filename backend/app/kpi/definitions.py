"""KPI definitions — stored in DB, editable via Admin Panel (PRD NFR-012/013).

`formula` names a computer in kpi/engine.py. `demo_value` seeds a placeholder
for KPIs whose source integration isn't connected yet; `demo_history` seeds a
12-month monthly series (oldest→newest) so trend charts + change arrows render
realistically before real data flows. Computed formulas (operations, bugs)
always take precedence once their integration is live.
"""
from __future__ import annotations

KPI_DEFINITIONS: list[dict] = [
    # --- Operations (computed live from projects/tasks) ---
    {"kpi_id": "ops_project_completion", "name": "Project Completion Rate",
     "module": "operations", "formula": "project_completion_rate", "unit": "%",
     "target": 90, "direction": "higher"},
    {"kpi_id": "ops_task_completion", "name": "Task Completion Rate",
     "module": "operations", "formula": "task_completion_rate", "unit": "%",
     "target": 85, "direction": "higher"},
    {"kpi_id": "ops_overdue_tasks", "name": "Overdue Tasks",
     "module": "operations", "formula": "overdue_task_count", "unit": "count",
     "target": 0, "direction": "lower"},
    {"kpi_id": "ops_at_risk_projects", "name": "At-Risk Projects",
     "module": "operations", "formula": "at_risk_project_count", "unit": "count",
     "target": 0, "direction": "lower"},
    {"kpi_id": "ops_active_projects", "name": "Active Projects",
     "module": "operations", "formula": "active_project_count", "unit": "count",
     "target": None, "direction": "higher"},

    # --- Product Development (bugs computed live from OpenProject) ---
    {"kpi_id": "pd_open_bugs", "name": "Open Bugs",
     "module": "product_dev", "formula": "open_bug_count", "unit": "count",
     "target": 25, "direction": "lower"},
    {"kpi_id": "pd_critical_bugs", "name": "High/Immediate Open Bugs",
     "module": "product_dev", "formula": "critical_bug_count", "unit": "count",
     "target": 0, "direction": "lower"},
    {"kpi_id": "pd_bug_closure", "name": "Bug Closure Rate",
     "module": "product_dev", "formula": "bug_closure_rate", "unit": "%",
     "target": 80, "direction": "higher"},
    {"kpi_id": "pd_deploy_freq", "name": "Deployments / Week",
     "module": "product_dev", "formula": "static", "unit": "count",
     "target": 3, "direction": "higher", "demo_value": 3.2,
     "demo_history": [1.8, 2.0, 2.1, 2.4, 2.2, 2.6, 2.8, 2.7, 3.0, 2.9, 3.1, 3.2]},

    # --- HR (demo until GreytHR connected) ---
    {"kpi_id": "hr_headcount", "name": "Total Headcount", "module": "hr",
     "formula": "static", "unit": "count", "target": None, "direction": "higher",
     "demo_value": 128,
     "demo_history": [96, 99, 103, 106, 108, 112, 115, 118, 120, 123, 126, 128]},
    {"kpi_id": "hr_attrition", "name": "Attrition Rate", "module": "hr",
     "formula": "static", "unit": "%", "target": 8, "direction": "lower",
     "demo_value": 6.4,
     "demo_history": [9.1, 8.8, 8.9, 8.4, 8.2, 7.9, 7.6, 7.4, 7.1, 6.9, 6.6, 6.4]},
    {"kpi_id": "hr_absenteeism", "name": "Absenteeism Rate", "module": "hr",
     "formula": "static", "unit": "%", "target": 3, "direction": "lower",
     "demo_value": 2.1},
    {"kpi_id": "hr_training", "name": "Training Completion", "module": "hr",
     "formula": "static", "unit": "%", "target": 90, "direction": "higher",
     "demo_value": 76},

    # --- Finance (demo until ERP connected) ---
    {"kpi_id": "fin_revenue_mtd", "name": "Revenue (MTD)", "module": "finance",
     "formula": "static", "unit": "USD", "target": 500000, "direction": "higher",
     "demo_value": 432000,
     "demo_history": [310000, 322000, 348000, 335000, 361000, 378000, 372000,
                      395000, 401000, 415000, 424000, 432000]},
    {"kpi_id": "fin_expenses_mtd", "name": "Operating Expenses (MTD)",
     "module": "finance", "formula": "static", "unit": "USD", "target": 350000,
     "direction": "lower", "demo_value": 318000},
    {"kpi_id": "fin_gross_margin", "name": "Gross Margin", "module": "finance",
     "formula": "static", "unit": "%", "target": 60, "direction": "higher",
     "demo_value": 57.5,
     "demo_history": [51.2, 52.0, 53.1, 52.6, 54.0, 54.8, 54.4, 55.6, 56.1,
                      56.8, 57.2, 57.5]},
    {"kpi_id": "fin_burn_rate", "name": "Burn Rate (monthly)", "module": "finance",
     "formula": "static", "unit": "USD", "target": 300000, "direction": "lower",
     "demo_value": 265000},
    {"kpi_id": "fin_ar_over_60", "name": "AR Aging > 60 days", "module": "finance",
     "formula": "static", "unit": "USD", "target": 50000, "direction": "lower",
     "demo_value": 82000},

    # --- Marketing & Sales (demo until HubSpot/GA connected) ---
    {"kpi_id": "mkt_leads", "name": "Leads (30d)", "module": "marketing_sales",
     "formula": "static", "unit": "count", "target": 400, "direction": "higher",
     "demo_value": 356,
     "demo_history": [180, 205, 220, 240, 236, 258, 275, 290, 301, 322, 340, 356]},
    {"kpi_id": "mkt_conversion", "name": "Lead→Opp Conversion",
     "module": "marketing_sales", "formula": "static", "unit": "%", "target": 20,
     "direction": "higher", "demo_value": 17.8},
    {"kpi_id": "mkt_pipeline", "name": "Pipeline Value",
     "module": "marketing_sales", "formula": "static", "unit": "USD",
     "target": 2000000, "direction": "higher", "demo_value": 1740000},
    {"kpi_id": "mkt_sessions", "name": "Website Sessions (30d)",
     "module": "marketing_sales", "formula": "static", "unit": "count",
     "target": None, "direction": "higher", "demo_value": 24500,
     "demo_history": [15200, 16100, 16800, 17500, 17200, 18400, 19600, 20300,
                      21500, 22400, 23600, 24500]},

    # --- Recruitment (demo until GreytHR/LinkedIn connected) ---
    {"kpi_id": "rec_open_positions", "name": "Open Positions",
     "module": "recruitment", "formula": "static", "unit": "count",
     "target": None, "direction": "lower", "demo_value": 12},
    {"kpi_id": "rec_time_to_fill", "name": "Time to Fill (days)",
     "module": "recruitment", "formula": "static", "unit": "days", "target": 45,
     "direction": "lower", "demo_value": 38},
    {"kpi_id": "rec_offer_acceptance", "name": "Offer Acceptance Rate",
     "module": "recruitment", "formula": "static", "unit": "%", "target": 80,
     "direction": "higher", "demo_value": 82},

    # --- Compliance (demo until Veda connected) ---
    {"kpi_id": "com_upcoming_30d", "name": "Deadlines (next 30d)",
     "module": "compliance", "formula": "static", "unit": "count",
     "target": None, "direction": "lower", "demo_value": 5},
    {"kpi_id": "com_overdue", "name": "Overdue Compliance Items",
     "module": "compliance", "formula": "static", "unit": "count", "target": 0,
     "direction": "lower", "demo_value": 1},
    {"kpi_id": "com_policy_ack", "name": "Policy Acknowledgment",
     "module": "compliance", "formula": "static", "unit": "%", "target": 95,
     "direction": "higher", "demo_value": 91},

    # --- Customer Support (demo until Zoho Desk connected) ---
    {"kpi_id": "sup_open_tickets", "name": "Open Tickets",
     "module": "customer_support", "formula": "static", "unit": "count",
     "target": 40, "direction": "lower", "demo_value": 47},
    {"kpi_id": "sup_first_response", "name": "Avg First Response (h)",
     "module": "customer_support", "formula": "static", "unit": "h", "target": 4,
     "direction": "lower", "demo_value": 2.4},
    {"kpi_id": "sup_sla", "name": "SLA Compliance",
     "module": "customer_support", "formula": "static", "unit": "%", "target": 95,
     "direction": "higher", "demo_value": 93.5},
    {"kpi_id": "sup_csat", "name": "CSAT", "module": "customer_support",
     "formula": "static", "unit": "%", "target": 90, "direction": "higher",
     "demo_value": 86,
     "demo_history": [78, 79, 80, 79, 81, 82, 83, 82, 84, 85, 85, 86]},
]
