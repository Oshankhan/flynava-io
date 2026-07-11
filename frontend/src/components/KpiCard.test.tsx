import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import KpiCard from "./KpiCard";
import type { Kpi } from "../lib/api";

const kpi: Kpi = {
  kpi_id: "ops_project_completion",
  name: "Project Completion Rate",
  module: "operations",
  value: 65,
  unit: "%",
  target: 90,
  direction: "higher",
  rag: "amber",
};

test("renders name, formatted value, and target", () => {
  render(<KpiCard kpi={kpi} />);
  expect(screen.getByText("Project Completion Rate")).toBeInTheDocument();
  expect(screen.getByText("65%")).toBeInTheDocument();
  expect(screen.getByText(/Target 90%/)).toBeInTheDocument();
  expect(screen.getByText("At risk")).toBeInTheDocument();
});

test("renders em dash when value is null", () => {
  render(<KpiCard kpi={{ ...kpi, value: null, target: null }} />);
  expect(screen.getByText("—")).toBeInTheDocument();
});

test("shows up-arrow + value when rising and higher is better", () => {
  render(<KpiCard kpi={{ ...kpi, change_pct: 1.9 }} />);
  const badge = screen.getByTestId("kpi-change");
  expect(badge).toHaveTextContent("1.9%");
  expect(badge.querySelector('[aria-label="arrow-up"]')).toBeTruthy();
});

test("shows down-arrow + value when falling", () => {
  render(<KpiCard kpi={{ ...kpi, change_pct: -3.2 }} />);
  const badge = screen.getByTestId("kpi-change");
  expect(badge).toHaveTextContent("3.2%");
  expect(badge.querySelector('[aria-label="arrow-down"]')).toBeTruthy();
});
