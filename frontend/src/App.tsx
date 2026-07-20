import { App as AntApp, ConfigProvider, theme as antdTheme } from "antd";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./lib/auth";
import { ThemeProvider, useTheme } from "./lib/theme";
import { BRAND } from "./lib/brand";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Awards from "./pages/Awards";
import Documents from "./pages/Documents";
import Reports from "./pages/Reports";
import People from "./pages/People";
import MyPayslip from "./pages/MyPayslip";
import Admin from "./pages/Admin";
import Workspace from "./pages/Workspace";
import Tasks from "./pages/Tasks";
import ProjectDetail from "./pages/ProjectDetail";
import Approvals from "./pages/Approvals";
import CalendarPage from "./pages/CalendarPage";
import NotificationsPage from "./pages/NotificationsPage";
import MyTeam from "./pages/MyTeam";
import Analytics from "./pages/Analytics";
import OrgChart from "./pages/OrgChart";
import MemberDetail from "./pages/MemberDetail";
import SuccessPage from "./pages/success/SuccessPage";
import ForecasterPage from "./pages/forecaster/ForecasterPage";
import ManagementPage from "./pages/management/ManagementPage";

function Shell() {
  const { dark } = useTheme();
  return (
    <ConfigProvider
      theme={{
        algorithm: dark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: {
          colorPrimary: BRAND.primary,
          colorInfo: BRAND.primary,
          borderRadius: 10,
          fontFamily: "Inter, system-ui, -apple-system, sans-serif",
        },
        components: {
          Layout: {
            headerBg: dark ? "#0b1512" : "#ffffff",
            siderBg: dark ? "#0b1512" : "#ffffff",
            bodyBg: dark ? "#0a1310" : "#f5f6fa",
          },
          Menu: {
            darkItemBg: "transparent",
            darkSubMenuItemBg: "transparent",
            itemSelectedBg: dark ? "rgba(21,127,82,0.28)" : "#e7f4ee",
            itemSelectedColor: dark ? "#7be3ae" : BRAND.primaryStrong,
            itemBorderRadius: 10,
          },
        },
      }}
    >
      <AntApp>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route element={<Layout />}>
              <Route path="/workspace" element={<Workspace />} />
              <Route path="/my-team" element={<MyTeam />} />
              <Route path="/tasks" element={<Tasks />} />
              <Route path="/projects/:projectId" element={<ProjectDetail />} />
              <Route path="/approvals" element={<Approvals />} />
              <Route path="/calendar" element={<CalendarPage />} />
              <Route path="/notifications" element={<NotificationsPage />} />
              <Route path="/dashboard/:key" element={<Dashboard />} />
              <Route path="/awards" element={<Awards />} />
              <Route path="/documents" element={<Documents />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/people" element={<People />} />
              <Route path="/member/:userId" element={<MemberDetail />} />
              <Route path="/my-payslip" element={<MyPayslip />} />
              <Route path="/admin" element={<Admin />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/org-chart" element={<OrgChart />} />
              <Route path="/success/:tab" element={<SuccessPage />} />
              <Route path="/forecaster/:tab" element={<ForecasterPage />} />
              <Route path="/management/:tab" element={<ManagementPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/workspace" replace />} />
          </Routes>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <Shell />
      </AuthProvider>
    </ThemeProvider>
  );
}
