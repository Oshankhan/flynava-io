import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import Login from "./Login";
import { AuthProvider } from "../lib/auth";

beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

function renderLogin() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <Login />
      </AuthProvider>
    </MemoryRouter>
  );
}

test("shows error on invalid credentials", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      status: 401,
      statusText: "Unauthorized",
      json: async () => ({ detail: "invalid credentials" }),
    }))
  );
  renderLogin();
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "x@flynava.ai" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "wrong" },
  });
  fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
  await waitFor(() =>
    expect(screen.getByText("invalid credentials")).toBeInTheDocument()
  );
});

test("stores token on successful login", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.endsWith("/auth/login"))
        return {
          ok: true,
          status: 200,
          json: async () => ({
            access_token: "tok",
            refresh_token: "ref",
            user: { user_id: "u_lead", name: "Leo", email: "l@f.ai", role: "leadership" },
          }),
        };
      return { ok: true, status: 200, json: async () => [{ key: "leadership", title: "Leadership" }] };
    })
  );
  renderLogin();
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "leadership@flynava.ai" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "Passw0rd!" },
  });
  fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
  await waitFor(() => expect(localStorage.getItem("io_token")).toBe("tok"));
});
