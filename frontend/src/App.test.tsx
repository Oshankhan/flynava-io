import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test } from "vitest";
import App from "./App";

beforeEach(() => {
  localStorage.clear();
  window.history.pushState({}, "", "/");
});

test("redirects unauthenticated user to login", () => {
  render(<App />);
  expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
});
