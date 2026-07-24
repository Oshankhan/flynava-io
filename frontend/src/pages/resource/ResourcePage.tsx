import type { ComponentType } from "react";
import { Navigate, useParams } from "react-router-dom";
import ResourceDashboard from "./ResourceDashboard";
import ComingSoonTab from "./ComingSoonTab";

const TABS: Record<string, ComponentType> = {
  dashboard: ResourceDashboard,
  capacity: () => <ComingSoonTab title="Team Capacity" />,
  planner: () => <ComingSoonTab title="Resource Planner" />,
  lifecycle: () => <ComingSoonTab title="Work Lifecycle" />,
  reports: () => <ComingSoonTab title="Reports" />,
};

export default function ResourcePage() {
  const { tab = "dashboard" } = useParams();
  const Tab = TABS[tab];
  if (!Tab) return <Navigate to="/resource/dashboard" replace />;
  return <Tab />;
}
