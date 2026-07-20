import type { ComponentType } from "react";
import { Navigate, useParams } from "react-router-dom";
import InsightsTab from "./InsightsTab";
import BugsTab from "./BugsTab";
import ReportTab from "./ReportTab";

const TABS: Record<string, ComponentType> = {
  insights: InsightsTab,
  bugs: BugsTab,
  report: ReportTab,
};

export default function ManagementPage() {
  const { tab = "insights" } = useParams();
  const Tab = TABS[tab];
  if (!Tab) return <Navigate to="/management/insights" replace />;
  return <Tab />;
}
