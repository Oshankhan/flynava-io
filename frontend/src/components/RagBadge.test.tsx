import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import RagBadge from "./RagBadge";

test("shows label for each RAG status", () => {
  const { rerender } = render(<RagBadge rag="green" />);
  expect(screen.getByText("On track")).toBeInTheDocument();
  rerender(<RagBadge rag="red" />);
  expect(screen.getByText("Critical")).toBeInTheDocument();
});
