import { useEffect, useState } from "react";
import { Alert, Flex, Spin } from "antd";
import { api, ApiError } from "../../lib/api";
import InsightsSection from "../../components/insights/InsightsSection";

// Mirrors insights/engine.py's DEPT_MODULE — which RBAC module gates each dept.
const DEPT_MODULE: Record<string, string> = {
  operations: "operations",
  finance: "finance",
  hr: "hr",
  marketing: "marketing_sales",
};

function hasAccess(modules: Record<string, string>, module: string): boolean {
  const level = modules[module];
  return !!level && level !== "own";
}

/** Aggregates the existing per-department AI insight detectors (already
 * built for Dashboard.tsx) into one "Management Insights" hub — no new
 * backend, just reuses GET /insights/{dept} across every dept the caller
 * can access. */
export default function InsightsTab() {
  const [modules, setModules] = useState<Record<string, string> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .me()
      .then((r) => alive && setModules(r.modules))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, []);

  if (error)
    return <Alert type="error" showIcon message="Cannot load Management Insights" description={error} />;
  if (!modules)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const depts = Object.entries(DEPT_MODULE)
    .filter(([, module]) => hasAccess(modules, module))
    .map(([dept]) => dept);

  if (depts.length === 0)
    return <Alert type="info" showIcon message="No insight departments available for your role." />;

  return <InsightsSection depts={depts} />;
}
