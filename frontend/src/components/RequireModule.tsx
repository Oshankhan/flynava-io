import type { ReactNode } from "react";
import { Result } from "antd";
import { useAuth } from "../lib/auth";

// Mirrors backend's has_aggregate_access: a bare "own" level (self-only
// visibility) doesn't qualify for a company-wide screen.
function hasAccess(modules: Record<string, string>, module: string): boolean {
  const level = modules[module];
  return !!level && level !== "own";
}

interface Props {
  /** Single module, or a list meaning "any of" — mirrors the backend's
   * require_any_module (e.g. Indicator Of Success's central tab needs
   * operations OR hr OR finance OR marketing_sales). */
  module: string | string[];
  children: ReactNode;
}

export default function RequireModule({ module, children }: Props) {
  const { modules } = useAuth();
  const mods = Array.isArray(module) ? module : [module];
  if (!mods.some((m) => hasAccess(modules, m))) {
    return (
      <Result
        status="403"
        title="403"
        subTitle="You don't have access to this section."
      />
    );
  }
  return <>{children}</>;
}
