import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import Awards from "./Awards";
import { AuthProvider } from "../lib/auth";

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem(
    "io_user",
    JSON.stringify({ user_id: "u_emp", name: "Evan", email: "e@f.ai", role: "employee" })
  );
});
afterEach(() => vi.restoreAllMocks());

test("renders recognition feed and leaderboard from API", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.endsWith("/awards/leaderboard"))
        return { ok: true, status: 200, json: async () => [{ recipient_id: "u_emp", name: "Evan", count: 2 }] };
      if (url.endsWith("/awards/categories"))
        return { ok: true, status: 200, json: async () => ["Innovation Award"] };
      if (url.endsWith("/awards"))
        return {
          ok: true,
          status: 200,
          json: async () => [
            {
              award_id: "a1",
              recipient_id: "u_emp",
              issuer_id: "u_hr",
              category: "Innovation Award",
              title: "Innovation Star",
              description: "Shipped IO",
              awarded_at: new Date().toISOString(),
              reactions: { clap: 3 },
            },
          ],
        };
      return { ok: true, status: 200, json: async () => [] };
    })
  );

  render(
    <AuthProvider>
      <Awards />
    </AuthProvider>
  );

  await waitFor(() => expect(screen.getByText("Innovation Star")).toBeInTheDocument());
  expect(screen.getByText("Leaderboard")).toBeInTheDocument();
  // employee (not a creator) should NOT see the create form
  expect(screen.queryByText("Give Recognition")).not.toBeInTheDocument();
});
