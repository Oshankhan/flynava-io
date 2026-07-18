import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import InayaChat from "./InayaChat";

function answerFor(question: string) {
  return {
    answer: `reply to ${question}`,
    reason: "r",
    evidence: [],
    recommended_action: "a",
    confidence: "High" as const,
    last_updated: new Date().toISOString(),
  };
}

afterEach(() => vi.restoreAllMocks());

test("sends prior completed turns as history on the next question", async () => {
  const requestBodies: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: string, opts: RequestInit) => {
      const body = JSON.parse(String(opts.body));
      requestBodies.push(body);
      return { ok: true, status: 200, json: async () => answerFor(body.question) };
    })
  );

  render(<InayaChat />);
  fireEvent.click(screen.getByRole("button", { name: "Inaya" }));

  const input = screen.getByPlaceholderText("Ask Inaya…");
  fireEvent.change(input, { target: { value: "first question" } });
  fireEvent.keyDown(input, { key: "Enter" });
  await waitFor(() =>
    expect(screen.getByText("reply to first question")).toBeInTheDocument()
  );

  fireEvent.change(input, { target: { value: "second question" } });
  fireEvent.keyDown(input, { key: "Enter" });
  await waitFor(() =>
    expect(screen.getByText("reply to second question")).toBeInTheDocument()
  );

  expect(requestBodies).toHaveLength(2);
  expect(requestBodies[0]).toMatchObject({ question: "first question", history: [] });
  expect(requestBodies[1]).toMatchObject({
    question: "second question",
    history: [{ q: "first question", a: "reply to first question" }],
  });
});
