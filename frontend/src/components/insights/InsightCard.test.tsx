import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import InsightCard from "./InsightCard";
import InayaChat, { INAYA_OPEN_EVENT } from "../InayaChat";
import type { InsightCard as InsightCardData } from "../../lib/api";

const card: InsightCardData = {
  insight_id: "operations:ops_reopened_bugs",
  dept: "operations",
  title: "Bugs that keep reopening",
  severity: "high",
  problem: "3 bug(s) are currently in a Reopen state.",
  metrics: [{ label: "Reopened bugs", value: 3, unit: "" }],
  entities: [],
  evidence: ["Bug A — Reopen, priority High, assignee Alice, project Kenya Airways"],
  chart: null,
  answer: "3 bugs are reopening repeatedly, mostly assigned to Alice.",
  reason: "Detected by rule 'Bugs that keep reopening'.",
  recommended_action: "Start a root-cause review with Alice.",
  confidence: "High",
  ai_provider: "echo",
  generated_at: new Date().toISOString(),
  feedback: { useful: 1, not_useful: 0, mine: null },
};

test("renders answer, severity, metrics, and evidence", () => {
  render(<InsightCard card={card} onVote={vi.fn()} />);
  expect(screen.getByText(card.answer)).toBeInTheDocument();
  expect(screen.getByText("high")).toBeInTheDocument();
  expect(screen.getByText(/Reopened bugs/)).toBeInTheDocument();
  expect(screen.getByText(/Bug A/)).toBeInTheDocument();
  expect(screen.getByText("Confidence: High")).toBeInTheDocument();
});

test("calls onVote with the insight id and useful flag", async () => {
  const onVote = vi.fn().mockResolvedValue(undefined);
  render(<InsightCard card={card} onVote={onVote} />);
  fireEvent.click(screen.getByLabelText("Mark useful"));
  await waitFor(() =>
    expect(onVote).toHaveBeenCalledWith("operations:ops_reopened_bugs", true)
  );
});

test("highlights the not-useful button when the current user already voted", () => {
  render(
    <InsightCard
      card={{ ...card, feedback: { useful: 0, not_useful: 1, mine: false } }}
      onVote={vi.fn()}
    />
  );
  const notUseful = screen.getByLabelText("Mark not useful");
  expect(notUseful).toHaveTextContent("1");
});

test("clicking the card opens Inaya pre-loaded with the finding, not a static panel", () => {
  render(
    <>
      <InsightCard card={card} onVote={vi.fn()} />
      <InayaChat />
    </>
  );
  fireEvent.click(screen.getByRole("button", { name: `Ask Inaya about: ${card.title}` }));
  // Inaya's own panel opens (title "Inaya") with the card's answer already
  // shown as a turn — no separate drawer/panel component involved. Both the
  // card and the newly-opened Inaya turn render the same title/answer text,
  // so each now appears twice on screen.
  expect(screen.getByText("Inaya")).toBeInTheDocument();
  expect(screen.getAllByText(card.title)).toHaveLength(2);
  expect(screen.getAllByText(card.answer)).toHaveLength(2);
});

test("clicking a vote button does not also open Inaya", () => {
  const onOpen = vi.fn();
  window.addEventListener(INAYA_OPEN_EVENT, onOpen);
  render(<InsightCard card={card} onVote={vi.fn().mockResolvedValue(undefined)} />);
  fireEvent.click(screen.getByLabelText("Mark useful"));
  expect(onOpen).not.toHaveBeenCalled();
  window.removeEventListener(INAYA_OPEN_EVENT, onOpen);
});

test("renders bug entities with their id and a link to the real OpenProject item", () => {
  render(
    <InsightCard
      card={{
        ...card,
        entities: [
          { kind: "bug", id: "7582", label: "Footnote data mismatch",
            url: "https://op.flynava.ai/work_packages/7582",
            extra: { assignee: "Alice" } },
        ],
      }}
      onVote={vi.fn()}
    />
  );
  const link = screen.getByText(/#7582 Footnote data mismatch/);
  expect(link.closest("a")).toHaveAttribute(
    "href", "https://op.flynava.ai/work_packages/7582"
  );
});
