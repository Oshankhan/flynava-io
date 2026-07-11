import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import Dashboard from "./Dashboard";

const payload = {
  key: "leadership",
  title: "Leadership",
  kpis: [
    {
      kpi_id: "ops_active_projects",
      name: "Active Projects",
      module: "operations",
      value: 2,
      unit: "count",
      target: null,
      direction: "higher",
      rag: "grey",
    },
  ],
  projects: [
    {
      project_id: "p_alpha",
      name: "Project Alpha",
      progress: 42,
      expected_progress: 70,
      rag: "red",
    },
  ],
  alerts: [],
};

afterEach(() => vi.restoreAllMocks());

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/dashboard/:key" element={<Dashboard />} />
      </Routes>
    </MemoryRouter>
  );
}

test("renders KPIs and project health from API", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => payload }))
  );
  renderAt("/dashboard/leadership");
  await waitFor(() =>
    expect(screen.getByText("Active Projects")).toBeInTheDocument()
  );
  expect(screen.getByText("Project Alpha")).toBeInTheDocument();
});

test("shows error message on failed load", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      json: async () => ({ detail: "no access to this dashboard" }),
    }))
  );
  renderAt("/dashboard/finance");
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("no access")
  );
});
