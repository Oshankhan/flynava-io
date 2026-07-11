import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import Workspace from "./Workspace";
import { AuthProvider } from "../lib/auth";

beforeEach(() => {
  localStorage.setItem(
    "io_user",
    JSON.stringify({
      user_id: "u_emp",
      name: "Evan Employee",
      email: "employee@flynava.ai",
      role: "employee",
      level: 1,
      status: "active",
    })
  );
});

const payload = {
  user: {
    user_id: "u_emp",
    name: "Evan Employee",
    designation: "Python Developer",
    department: "eng",
    level: 1,
    role: "employee",
  },
  team: { team_id: "team_python", name: "Python Team", department: "eng" },
  lead: { name: "Priya Nair", designation: "Python Team Lead" },
  buckets: { total: 4, completed: 2, in_progress: 1, pending: 0, overdue: 1 },
  tasks: [
    {
      task_id: "t1",
      title: "Fix login bug",
      status: "In progress",
      bucket: "in_progress",
      wp_type: "Bug",
      priority: "High",
      due_date: "2030-01-01",
      progress: 30,
      project: "KQ Project",
    },
  ],
  reopened: [
    {
      task_id: "t9",
      title: "Payment retry loops forever",
      status: "Reopen",
      bucket: "pending",
      wp_type: "Bug",
      priority: "High",
      due_date: null,
      progress: 0,
      project: "KQ Project",
    },
  ],
  meetings: [
    {
      meeting_id: "m1",
      title: "Python Stand-up",
      start: `${new Date().toISOString().slice(0, 10)}T10:30`,
      end: `${new Date().toISOString().slice(0, 10)}T10:45`,
      organizer_id: "u_tl_python",
      attendee_ids: ["u_emp"],
      status: "scheduled",
    },
  ],
  my_requests: [
    {
      req_id: "r1",
      type: "hr_grievance",
      title: "Broken chair",
      requester_id: "u_emp",
      status: "pending",
      history: [],
      created_at: "2026-07-10T09:00:00Z",
    },
  ],
  inbox_count: 0,
  unread_notifications: 2,
  activity: [
    {
      actor_id: "u_emp",
      actor_name: "Evan Employee",
      action: "request_submitted",
      text: "submitted request “Broken chair”",
      at: "2026-07-10T09:00:00Z",
    },
  ],
};

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

test("renders greeting, task buckets, reopened bugs, meetings and requests", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => payload }))
  );
  render(
    <MemoryRouter>
      <AuthProvider>
        <Workspace />
      </AuthProvider>
    </MemoryRouter>
  );
  await waitFor(() => expect(screen.getByText(/Evan!/)).toBeInTheDocument());
  expect(screen.getAllByText("My Tasks").length).toBeGreaterThan(0);
  expect(screen.getByText("Fix login bug")).toBeInTheDocument();
  expect(screen.getByText("Payment retry loops forever")).toBeInTheDocument();
  expect(screen.getByText("Python Stand-up")).toBeInTheDocument();
  expect(screen.getByText("Broken chair")).toBeInTheDocument();
  expect(screen.getByText(/Reports to Priya Nair/)).toBeInTheDocument();
});

test("shows error on failed load", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      json: async () => ({ detail: "missing bearer token" }),
    }))
  );
  render(
    <MemoryRouter>
      <AuthProvider>
        <Workspace />
      </AuthProvider>
    </MemoryRouter>
  );
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent("missing bearer token")
  );
});
