import type { ComponentType } from "react";
import { Navigate, useParams } from "react-router-dom";
import RequireModule from "../../components/RequireModule";
import InsightsTab from "./InsightsTab";
import BugsTab from "./BugsTab";
import ReportTab from "./ReportTab";

const TABS: Record<string, ComponentType> = {
  insights: InsightsTab,
  bugs: BugsTab,
  report: ReportTab,
};

// Mirrors backend/app/api/v1/management.py's per-tab access gates.
const TAB_MODULE: Record<string, string | string[]> = {
  insights: ["operations", "finance", "hr", "marketing_sales"],
  bugs: ["operations", "product_dev"],
  report: ["operations", "product_dev"],
};

export default function ManagementPage() {
  const { tab = "insights" } = useParams();
  const Tab = TABS[tab];
  if (!Tab) return <Navigate to="/management/insights" replace />;
  return (
    <RequireModule module={TAB_MODULE[tab]}>
      <Tab />
    </RequireModule>
  );
}
