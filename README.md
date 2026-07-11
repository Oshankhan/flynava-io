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

## Deploy (free tier)
Three free services, no credit card required beyond normal signup:

1. **Database — MongoDB Atlas (free M0 cluster)**
   Create a cluster at atlas.mongodb.com, add a DB user, allow network access
   (`0.0.0.0/0` for simplicity), copy the `mongodb+srv://...` connection string.

2. **Backend — Render** (`render.yaml` at repo root, `rootDir: backend`)
   Render → New → Blueprint → point at this repo → it reads `render.yaml`.
   Fill in the `sync: false` env vars in the Render dashboard: `MONGO_URI`
   (from step 1), `CORS_ORIGINS` (your Vercel URL from step 3), plus any
   integration keys you want live (`OPENPROJECT_API_KEY`, `OPENAI_API_KEY`/
   `ANTHROPIC_API_KEY`, SMTP). `JWT_SECRET` auto-generates. Free tier sleeps
   after 15 min idle — first request after that takes ~30s to wake up.
   After first deploy, seed demo data once via the Render Shell tab:
   `python -m app.services.seed`

3. **Frontend — Vercel** (`frontend/vercel.json`)
   Vercel → Import Project → this repo → root directory `frontend` (Vite
   preset auto-detected). Set env var `VITE_API_BASE_URL` to the Render
   backend URL from step 2. Deploy, then paste the resulting Vercel URL back
   into Render's `CORS_ORIGINS` and redeploy the backend.

`docker-compose.yml` remains the local-dev path; it isn't used for either
deployment target above.
