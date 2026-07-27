import type { ComponentType } from "react";
import { Navigate, useParams } from "react-router-dom";
import RequireModule from "../../components/RequireModule";
import CentralTab from "./CentralTab";
import OrganizationTab from "./OrganizationTab";
import MarketingTab from "./MarketingTab";
import FinanceTab from "./FinanceTab";
import StartupTab from "./StartupTab";
import OperationsTab from "./OperationsTab";

const TABS: Record<string, ComponentType> = {
  central: CentralTab,
  organization: OrganizationTab,
  marketing: MarketingTab,
  finance: FinanceTab,
  startup: StartupTab,
  operations: OperationsTab,
};

// Mirrors backend/app/api/v1/success.py's per-tab require_any_module gates.
const TAB_MODULE: Record<string, string | string[]> = {
  central: ["operations", "hr", "finance", "marketing_sales"],
  organization: "hr",
  marketing: "marketing_sales",
  finance: "finance",
  startup: "finance",
  operations: "operations",
};

export default function SuccessPage() {
  const { tab = "central" } = useParams();
  const Tab = TABS[tab];
  if (!Tab) return <Navigate to="/success/central" replace />;
  return (
    <RequireModule module={TAB_MODULE[tab]}>
      <Tab />
    </RequireModule>
  );
}
