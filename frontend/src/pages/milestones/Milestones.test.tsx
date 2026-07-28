import { App as AntApp } from "antd";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import DashboardTab from "./DashboardTab";
import ListTab from "./ListTab";
import MilestoneDetail from "./MilestoneDetail";
import { AuthProvider } from "../../lib/auth";

const FILTER_OPTIONS = {
  departments: [{ value: "eng", label: "Engineering" }],
  teams: [],
  projects: [],
  categories: [],
  managers: [],
  owners: [{ value: "u_a", label: "Ann Lee" }],
  statuses: ["in_progress"],
  priorities: ["High", "Medium", "Low"],
};

const DASHBOARD = {
  generated_at: "2026-07-28T09:00:00Z",
  period: { month: "2026-07", from: null, to: null },
  cards: [
    { id: "total_employees", label: "Total Employees", value: 142, unit: "count", delta_pct: 5.2, delta_direction: "up", good: true },
    { id: "active_milestones", label: "Active Milestones", value: 358, unit: "count", delta_pct: 8.7, delta_direction: "up", good: true },
    { id: "completed_month", label: "Completed This Month", value: 214, unit: "count", delta_pct: 7.3, delta_direction: "up", good: true },
    { id: "overdue", label: "Overdue Milestones", value: 32, unit: "count", delta_pct: -12.5, delta_direction: "down", good: true },
    { id: "company_completion", label: "Company Completion", value: 79.4, unit: "pct", delta_pct: 6.1, delta_direction: "up", good: true },
    { id: "org_health", label: "Organization Health", value: 78, unit: "score", delta_pct: null, delta_direction: "flat", good: true },
  ],
  org_health: { score: 78, band: "Good" },
  status_donut: { total: 358, slices: [{ label: "Completed", value: 214 }, { label: "In Progress", value: 144 }] },
  trend: { granularity: "monthly", points: [{ t: "Jun", month: "2026-06", planned: 80, actual: 74, delayed: 6 }] },
  departments: [
    { dept_id: "eng", name: "Development", progress_pct: 88, planned_pct: 85, total: 40, completed: 20, overdue: 2, health: "good" },
  ],
  top_performers: [
    { rank: 1, user_id: "u_a", name: "Sarah Johnson", department: "Development", designation: "Dev", completed: 14, total: 14, completion_pct: 100, score: 98 },
  ],
  needs_attention: [
    { user_id: "u_b", name: "James Martinez", department: "Finance", designation: "Analyst", overdue_milestones: 3, overdue_days: 7, risk: "High" },
  ],
  upcoming_deadlines: [
    { milestone_id: "MS-1258", name: "User Dashboard Enhancement", due_date: "2026-07-29", priority: "High", days_left: 1, owner_name: "Sarah Johnson", project_name: "Jupiter" },
  ],
  totals: { all: 358, active: 144, completed: 214, overdue: 32 },
};

const LIST_PAGE = {
  items: [
    {
      milestone_id: "MS-1258", name: "User Dashboard Enhancement", description: "",
      project_id: "p1", project_name: "Jupiter", department: "eng", department_name: "Development",
      team_id: "t1", team_name: "Frontend", owner_id: "u_a", owner_name: "Sarah Johnson",
      manager_id: "u_m", manager_name: "William Anderson", category: "Delivery",
      priority: "High", status: "in_progress", start_date: "2026-06-01",
      due_date: "2026-07-29", completed_at: null, progress_pct: 75, actual_pct: 75,
      planned_pct: 70, delayed_pct: 0, health: "good", overdue: false,
      overdue_days: 0, days_left: 1,
    },
  ],
  total: 358,
  page: 1,
  page_size: 20,
  generated_at: "2026-07-28T09:00:00Z",
};

const DETAIL = {
  milestone: LIST_PAGE.items[0],
  tasks: [],
  daily_entries: [],
  dependencies: [],
  documents: [],
  comments: [],
  timeline: [],
  trend: DASHBOARD.trend,
  permissions: { can_manage: true, can_approve: false },
  counts: { tasks: 8, daily_entries: 12, dependencies: 2, documents: 4, comments: 3 },
  generated_at: "2026-07-28T09:00:00Z",
};

/** Routes the stub by URL: every milestone screen loads its filter options
 * alongside its own payload, so a single-response stub would starve one of
 * the two calls. */
function stubFetch(routes: Record<string, unknown>) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      const match = Object.keys(routes).find((key) => url.includes(key));
      if (!match)
        return { ok: false, status: 404, statusText: "Not Found", json: async () => ({}) };
      return { ok: true, status: 200, json: async () => routes[match] };
    })
  );
  return calls;
}

function renderWithProviders(ui: React.ReactNode, path = "/") {
  return render(
    <AntApp>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </AntApp>
  );
}

afterEach(() => vi.restoreAllMocks());

test("dashboard renders every KPI card, the donut and the drill-down tables", async () => {
  stubFetch({
    "/milestones/filters": FILTER_OPTIONS,
    "/milestones/dashboard": DASHBOARD,
    "/auth/me": { user: null, modules: {} },
  });
  renderWithProviders(<DashboardTab />);

  await waitFor(() => expect(screen.getByText("Total Employees")).toBeInTheDocument());
  ["Active Milestones", "Completed This Month", "Overdue Milestones", "Company Completion",
    "Organization Health"].forEach((label) =>
      expect(screen.getByText(label)).toBeInTheDocument()
    );
  expect(screen.getByText("Milestones by Status")).toBeInTheDocument();
  expect(screen.getByText("Company Progress Trend")).toBeInTheDocument();
  expect(screen.getByText("Development")).toBeInTheDocument();
  // Sarah Johnson is both a top performer and the owner of an upcoming
  // deadline, so she legitimately appears twice.
  expect(screen.getAllByText("Sarah Johnson").length).toBeGreaterThan(0);
  expect(screen.getByText("James Martinez")).toBeInTheDocument();
  expect(screen.getByText("User Dashboard Enhancement")).toBeInTheDocument();
});

test("dashboard surfaces a load failure instead of rendering empty cards", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      json: async () => ({ detail: "no aggregate access to milestones" }),
    }))
  );
  renderWithProviders(<DashboardTab />);
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("no aggregate access")
  );
});

test("list shows the server total and refetches when a filter is applied", async () => {
  const calls = stubFetch({
    "/milestones/filters": FILTER_OPTIONS,
    "/milestones?": LIST_PAGE,
    "/auth/me": { user: null, modules: {} },
  });
  renderWithProviders(<ListTab />);

  await waitFor(() => expect(screen.getByText("MS-1258")).toBeInTheDocument());
  expect(screen.getByText(/of 358 milestones/)).toBeInTheDocument();

  const before = calls.filter((c) => c.includes("/milestones?")).length;
  fireEvent.click(screen.getByRole("button", { name: /Apply Filters/ }));
  await waitFor(() =>
    expect(calls.filter((c) => c.includes("/milestones?")).length).toBeGreaterThan(before)
  );
});

test("detail renders the seven tabs with their counts", async () => {
  stubFetch({
    "/milestones/MS-1258": DETAIL,
    "/auth/me": { user: null, modules: {} },
  });
  render(
    <AntApp>
      <MemoryRouter initialEntries={["/milestones/detail/MS-1258"]}>
        <AuthProvider>
          <Routes>
            <Route path="/milestones/detail/:milestoneId" element={<MilestoneDetail />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </AntApp>
  );

  await waitFor(() => expect(screen.getByText("Overview")).toBeInTheDocument());
  const tabs = screen.getByRole("tablist");
  ["Tasks (8)", "Daily Success (12)", "Dependencies (2)", "Documents (4)", "Timeline",
    "Comments (3)"].forEach((label) =>
      expect(within(tabs).getByText(label)).toBeInTheDocument()
    );
  // Progress Overview reads the derived planned/actual/delayed split.
  expect(screen.getByText("Planned Progress")).toBeInTheDocument();
  expect(screen.getByText("Actual Progress")).toBeInTheDocument();
  expect(screen.getByText("Delayed Progress")).toBeInTheDocument();
});
