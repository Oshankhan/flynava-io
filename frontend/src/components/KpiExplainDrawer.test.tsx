import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import KpiExplainDrawer from "./KpiExplainDrawer";

const explanation = {
  kpi_id: "ops_project_completion",
  name: "Project Completion Rate",
  module: "operations",
  unit: "%",
  target: 90,
  direction: "higher",
  value: 42.5,
  rag: "amber",
  formula_text: "Mean of `progress` across every project with status = active.",
  computation: "Mean progress across 2 active project(s): (Kenya Airways 45% + Saudia 40%) / 2 = 42.5%",
  inputs: [],
  evidence: [
    { kind: "project", id: "proj_kq", label: "Kenya Airways", url: null, extra: { progress: 45 } },
    { kind: "bug", id: "7582", label: "Footnote data mismatch",
      url: "https://op.flynava.ai/work_packages/7582", extra: { priority: "High" } },
  ],
  source: {
    system: "Seed data", collection: "projects", live: false, last_sync: null,
    note: "Demo seed data — the OpenProject connector has not synced in this environment yet.",
  },
  history: [],
  answer: "42.5% is the mean progress of the two active projects.",
  reason: "Mean of progress across active projects.",
  recommended_action: "No action needed — this recomputes automatically.",
  confidence: "High",
  ai_provider: "echo",
  generated_at: new Date().toISOString(),
};

afterEach(() => vi.restoreAllMocks());

test("renders formula, computation, evidence, source, and AI explanation", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => explanation }))
  );
  render(<KpiExplainDrawer kpiId="ops_project_completion" onClose={vi.fn()} />);

  await waitFor(() =>
    expect(screen.getByText(/Mean progress across 2 active/)).toBeInTheDocument()
  );
  // no url on this row -> plain label, no id prefix (id here is just an
  // internal key, not a real distinct reference worth surfacing)
  expect(screen.getByText("Kenya Airways")).toBeInTheDocument();
  // a row with a url renders as a clickable deep link to the real work package
  const bugLink = screen.getByText("#7582 Footnote data mismatch");
  expect(bugLink.closest("a")).toHaveAttribute(
    "href", "https://op.flynava.ai/work_packages/7582"
  );
  expect(screen.getByText(explanation.answer)).toBeInTheDocument();
  expect(screen.getByText(/Demo seed data/)).toBeInTheDocument();
});

test("stays closed and fetches nothing when kpiId is null", () => {
  vi.stubGlobal("fetch", vi.fn());
  render(<KpiExplainDrawer kpiId={null} onClose={vi.fn()} />);
  expect(screen.queryByText("Why this number?")).not.toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});
