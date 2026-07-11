import { expect, test } from "@playwright/test";

// Smoke: unauthenticated user is redirected to login, can sign in with the
// seeded leadership account, and lands on a dashboard with KPI cards.
test("login and land on the leadership dashboard", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: /sign in/i })).toBeVisible();

  await page.getByLabel("Email").fill("leadership@flynava.ai");
  await page.getByLabel("Password").fill("Passw0rd!");
  await page.getByRole("button", { name: /sign in/i }).click();

  // Sidebar shows role dashboards; main area renders KPI content.
  await expect(page).toHaveURL(/\/dashboard\//);
  await expect(page.getByText("Project Health")).toBeVisible();
});

test("Ask IO input is present on the dashboard", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Email").fill("leadership@flynava.ai");
  await page.getByLabel("Password").fill("Passw0rd!");
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByLabel("Ask IO")).toBeVisible();
});
