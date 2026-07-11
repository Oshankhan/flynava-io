# IO — Integrated Organizational Intelligence Platform

FlyNava Technologies. React + FastAPI + MongoDB. Green/white theme.

## Stack
- **Frontend**: React 18 + TypeScript + Tailwind + Recharts (Vite)
- **Backend**: FastAPI + pymongo
- **DB**: MongoDB
- **Tests**: pytest (backend), vitest + React Testing Library (frontend), Playwright e2e (later phase)

## Quick start (Docker)
```bash
cp .env.example .env      # fill real keys, never commit
docker compose up --build
# API   -> http://localhost:8000/api/v1/health
# Web   -> http://localhost:5173
# Docs  -> http://localhost:8000/docs
```

## Local dev
Backend:
```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload
pytest
```
Frontend:
```bash
cd frontend
npm install
npm run dev
npm test
```

## Build phases
- [x] **Phase 0** — Scaffold, health check, CI, green/white tokens
- [x] **Phase 1** — Auth (JWT) + RBAC (8 roles × 11 modules) + core data model + seed
- [x] **Phase 2** — Ingestion framework + OpenProject connector + Integration_Log
- [x] **Phase 3** — Config-driven KPI engine + Operations KPIs
- [x] **Phase 4** — Dashboard shell + Leadership dashboard
- [x] **Phase 5** — Pluggable AI/RAG (Ask IO, Anthropic + Echo fallback)
- [x] **Phase 6** — HR, Finance, Marketing, Manager, Employee dashboards
- [x] **Phase 7** — Notifications + Awards & Recognition + Admin panel
- [x] **Phase 8** — Playwright e2e scaffold + security middleware + audit trail

## Demo accounts (seeded, password `Passw0rd!`)
`admin@` (super_admin) · `leadership@` · `manager@` · `hr@` · `employee@` ·
`marketing@` · `investor@` · `partner@` — all `@flynava.ai`.

Seed the DB: `cd backend && python -m app.services.seed`

## Tests
- Backend: `cd backend && pytest` — 51 tests, ~90% coverage (gate ≥70%)
- Frontend unit: `cd frontend && npm test` — 9 tests (vitest + RTL)
- E2E (needs running app + `npx playwright install`): `cd frontend && npm run e2e`

## Security
Secrets live in `.env` only (gitignored). Never commit keys. Rotate any key shared over chat.
