import { useState } from "react";

/** Wraps an async action with a loading flag and blocks double-submits while
 * it's in flight. Pair the returned `loading` with a button's `loading` /
 * `confirmLoading` prop — every control that fires an API call must show one
 * (see CLAUDE.md). */
export function useAsyncAction<Args extends unknown[]>(
  fn: (...args: Args) => Promise<void>
): readonly [(...args: Args) => Promise<void>, boolean] {
  const [loading, setLoading] = useState(false);

  const run = async (...args: Args) => {
    if (loading) return;
    setLoading(true);
    try {
      await fn(...args);
    } finally {
      setLoading(false);
    }
  };

  return [run, loading] as const;
}
