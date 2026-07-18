import type { ReactNode } from "react";

const URL_RE = /(https?:\/\/[^\s)]+)/g;

/** Turns raw "https://..." substrings in plain text into clickable links —
 * used for Ask IO / Inaya answers, whose evidence text has OpenProject work
 * package URLs folded straight in (see services/rag_index.py's task chunks),
 * so "give me the bug link" answers actually open the real item. */
export function linkify(text: string): ReactNode {
  // split() with a capturing group interleaves matched/unmatched fragments;
  // checking each fragment's own prefix (rather than re-testing the global
  // regex, which carries stateful lastIndex across calls) is what tells them
  // apart.
  const parts = text.split(URL_RE);
  if (parts.length === 1) return text;
  return parts.map((part, i) =>
    part.startsWith("http://") || part.startsWith("https://") ? (
      <a
        key={i}
        href={part}
        target="_blank"
        rel="noopener noreferrer"
        className="text-io-600 hover:underline"
      >
        {part}
      </a>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}
