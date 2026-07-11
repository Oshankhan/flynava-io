import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests. Requires the backend running (uvicorn on :8000, seeded)
 * and browsers installed (`npx playwright install`). Playwright starts the
 * frontend dev server automatically.
 *
 *   cd backend && python -m app.services.seed && uvicorn app.main:app
 *   cd frontend && npm run e2e
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 60000,
  },
});
