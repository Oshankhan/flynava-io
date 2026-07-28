import type { ComponentType } from "react";
import { Result } from "antd";
import { Navigate, useParams } from "react-router-dom";
import RequireModule from "../../components/RequireModule";
import { useAuth } from "../../lib/auth";
import DashboardTab from "./DashboardTab";
import ListTab from "./ListTab";
import EmployeesTab from "./EmployeesTab";
import DepartmentDashboard from "./DepartmentDashboard";
import ReportsTab from "./ReportsTab";

/** Tabs whose backend endpoint is gated on `has_aggregate_access("milestones")`
 * — a bare "own" level 403s there, so the UI must not offer them either.
 * `list` and `employees` are scoped per row instead and stay open to everyone. */
const AGGREGATE_TABS = new Set(["dashboard", "departments", "reports"]);

const TABS: Record<string, ComponentType> = {
  dashboard: DashboardTab,
  list: ListTab,
  employees: EmployeesTab,
  departments: DepartmentDashboard,
  reports: ReportsTab,
};

export default function MilestonePage() {
  const { tab = "dashboard" } = useParams();
  const { modules } = useAuth();
  const Tab = TABS[tab];
  if (!Tab) return <Navigate to="/milestones/dashboard" replace />;
  if (AGGREGATE_TABS.has(tab))
    return (
      <RequireModule module="milestones">
        <Tab />
      </RequireModule>
    );
  // Row-scoped tabs still need *some* access to the module — roles that are
  // NONE in the RBAC matrix (partner) would otherwise land on an empty screen
  // instead of a straight refusal.
  if (!modules.milestones)
    return <Result status="403" title="403" subTitle="You don't have access to this section." />;
  return <Tab />;
}
