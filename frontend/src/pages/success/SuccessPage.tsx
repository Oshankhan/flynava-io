import type { ComponentType } from "react";
import { Navigate, useParams } from "react-router-dom";
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

export default function SuccessPage() {
  const { tab = "central" } = useParams();
  const Tab = TABS[tab];
  if (!Tab) return <Navigate to="/success/central" replace />;
  return <Tab />;
}
