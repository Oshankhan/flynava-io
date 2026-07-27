import type { ComponentType } from "react";
import { Navigate, useParams } from "react-router-dom";
import RequireModule from "../../components/RequireModule";
import OverviewTab from "./OverviewTab";
import WorkforceTab from "./WorkforceTab";
import RevenueTab from "./RevenueTab";
import CashflowTab from "./CashflowTab";
import CostsTab from "./CostsTab";
import AnalyzerTab from "./AnalyzerTab";

const TABS: Record<string, ComponentType> = {
  overview: OverviewTab,
  workforce: WorkforceTab,
  revenue: RevenueTab,
  cashflow: CashflowTab,
  costs: CostsTab,
  analyzer: AnalyzerTab,
};

export default function ForecasterPage() {
  const { tab = "overview" } = useParams();
  const Tab = TABS[tab];
  if (!Tab) return <Navigate to="/forecaster/overview" replace />;
  // Every forecaster tab mirrors the backend's single require_any_module("finance").
  return (
    <RequireModule module="finance">
      <Tab />
    </RequireModule>
  );
}
