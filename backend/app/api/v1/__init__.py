"""Aggregate all v1 routers under /api/v1."""
from fastapi import APIRouter

from . import (auth, users, rbac, integrations, kpis, dashboards, ai,
               notifications, awards, admin, documents, reports, report_hub, hr,
               org, tasks, meetings, requests, workspace, compliance,
               positions, analytics, projects)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(rbac.router)
api_router.include_router(integrations.router)
api_router.include_router(kpis.router)
api_router.include_router(dashboards.router)
api_router.include_router(ai.router)
api_router.include_router(notifications.router)
api_router.include_router(awards.router)
api_router.include_router(admin.router)
api_router.include_router(documents.router)
api_router.include_router(reports.router)
api_router.include_router(report_hub.router)
api_router.include_router(hr.router)
api_router.include_router(org.router)
api_router.include_router(tasks.router)
api_router.include_router(meetings.router)
api_router.include_router(requests.router)
api_router.include_router(workspace.router)
api_router.include_router(compliance.router)
api_router.include_router(positions.router)
api_router.include_router(analytics.router)
api_router.include_router(projects.router)
