import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Avatar,
  Badge,
  Button,
  Drawer,
  Dropdown,
  Flex,
  Grid,
  Layout as AntLayout,
  Menu,
  type MenuProps,
  notification,
  Switch,
  Typography,
} from "antd";
import {
  AimOutlined,
  ApartmentOutlined,
  AuditOutlined,
  BarChartOutlined,
  BulbOutlined,
  CalendarOutlined,
  CheckSquareOutlined,
  ClusterOutlined,
  ControlOutlined,
  DashboardOutlined,
  FileProtectOutlined,
  FundProjectionScreenOutlined,
  HomeOutlined,
  IdcardOutlined,
  LogoutOutlined,
  MenuOutlined,
  SettingOutlined,
  TeamOutlined,
  TrophyOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { api, type DashboardLink } from "../lib/api";
import { useAuth } from "../lib/auth";
import { levelOf, rolesOf } from "../lib/rbac";
import { useTheme } from "../lib/theme";
import AskIO from "./AskIO";
import NotificationBell from "./NotificationBell";
import InayaChat from "./InayaChat";

const { Sider, Header, Content } = AntLayout;
const { Text } = Typography;
const { useBreakpoint } = Grid;

// A bare "own" access level (self-only visibility — an employee's own HR
// record, their own task list) doesn't qualify for these company-wide
// aggregate screens — mirrors the backend's `has_aggregate_access` gate in
// api/deps.py, so the sidebar never offers a tab that then 403s.
function hasAggregateAccess(modules: Record<string, string>, module: string): boolean {
  const level = modules[module];
  return !!level && level !== "own";
}

function buildSuccessChildren(
  modules: Record<string, string>,
  level: number
): { key: string; label: string }[] {
  const has = (m: string) => hasAggregateAccess(modules, m);
  const children: { key: string; label: string }[] = [];
  if (["operations", "hr", "finance", "marketing_sales"].some(has))
    children.push({ key: "/success/central", label: "Central Dashboard" });
  if (has("hr")) children.push({ key: "/success/organization", label: "Organization Insights" });
  if (has("marketing_sales"))
    children.push({ key: "/success/marketing", label: "Marketing Insights" });
  if (has("finance")) children.push({ key: "/success/finance", label: "Finance Performance" });
  if (has("finance") || level >= 4)
    children.push({ key: "/success/startup", label: "Startup Metrics" });
  if (has("operations"))
    children.push({ key: "/success/operations", label: "Operational Insights" });
  return children;
}

// Financial Forecaster is gated on `finance` alone (every screen there is a
// company-wide financial view) — mirrors the backend's single
// `require_any_module("finance")` gate in api/v1/forecaster.py.
function buildForecasterChildren(modules: Record<string, string>): { key: string; label: string }[] {
  if (!hasAggregateAccess(modules, "finance")) return [];
  return [
    { key: "/forecaster/overview", label: "Overview" },
    { key: "/forecaster/workforce", label: "Workforce" },
    { key: "/forecaster/revenue", label: "Revenue" },
    { key: "/forecaster/cashflow", label: "Cashflow" },
    { key: "/forecaster/costs", label: "Costs" },
    { key: "/forecaster/analyzer", label: "Finance Analyzer" },
  ];
}

// Management Overview: Insights hub is gated on any of the 4 insight depts
// (mirrors the existing per-dept /insights/{dept} gate); Bugs Tracker +
// Project Report are gated on operations/product_dev alone (mirrors the
// backend's require_any_module("operations", "product_dev") in
// api/v1/management.py) — both project/team-wide views.
function buildManagementChildren(modules: Record<string, string>): { key: string; label: string }[] {
  const has = (m: string) => hasAggregateAccess(modules, m);
  const children: { key: string; label: string }[] = [];
  if (["operations", "finance", "hr", "marketing_sales"].some(has))
    children.push({ key: "/management/insights", label: "Management Insights" });
  if (has("operations") || has("product_dev")) {
    children.push({ key: "/management/bugs", label: "Project Bugs Tracker" });
    children.push({ key: "/management/report", label: "Project Report" });
  }
  return children;
}

// Resource Management: gated on level >= 3 (dept-heads and above) — mirrors
// the backend's `user_level(user) < 3` 403 in api/v1/resources.py. Every
// sub-tab is listed once access is granted; only Resource Dashboard is built
// today, the rest are "coming soon" placeholders (see ResourcePage.tsx).
function buildResourceChildren(level: number): { key: string; label: string }[] {
  if (level < 3) return [];
  return [
    { key: "/resource/dashboard", label: "Resource Dashboard" },
    { key: "/resource/capacity", label: "Team Capacity" },
    { key: "/resource/planner", label: "Resource Planner" },
    { key: "/resource/lifecycle", label: "Work Lifecycle" },
    { key: "/resource/reports", label: "Reports" },
  ];
}

export default function Layout() {
  const { user, logout, modules } = useAuth();
  const { dark, toggle } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const [dashboards, setDashboards] = useState<DashboardLink[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [inbox, setInbox] = useState(0);
  const lastUnread = useRef<number | null>(null);
  const screens = useBreakpoint();
  const isMobile = !screens.lg;

  const level = levelOf(user);

  useEffect(() => {
    if (user) api.listDashboards().then(setDashboards).catch(() => setDashboards([]));
  }, [user]);

  // Poll unread + approval inbox; toast when something new lands.
  const poll = useCallback(async () => {
    try {
      const { count } = await api.unreadCount();
      if (lastUnread.current != null && count > lastUnread.current) {
        const items = await api.notifications();
        const fresh = items.filter((n) => n.status === "unread").slice(0, 3);
        fresh.forEach((n) =>
          notification.open({
            message: n.title,
            description: n.body,
            placement: "bottomRight",
            onClick: () => n.action_link && navigate(n.action_link),
          })
        );
      }
      lastUnread.current = count;
      if (levelOf(user) >= 2) setInbox((await api.requestInbox()).length);
    } catch {
      /* ignore */
    }
  }, [user, navigate]);

  useEffect(() => {
    if (!user) return;
    poll();
    const t = setInterval(poll, 10000);
    return () => clearInterval(t);
  }, [user, poll]);

  // Real-time push via SSE, layered on top of the poll above. If the stream
  // never connects or drops, we simply keep relying on the interval poll —
  // this effect must never surface an error or otherwise affect the UI.
  useEffect(() => {
    if (!user) return;
    let es: EventSource | null = null;
    try {
      es = new EventSource(api.notificationsStreamUrl());
      es.onmessage = () => poll();
      es.onerror = () => {
        es?.close();
      };
    } catch {
      /* SSE unsupported or failed to init — poll interval above still covers us */
    }
    return () => es?.close();
  }, [user, poll]);

  const items = useMemo(() => {
    if (!user) return [];
    const roles = rolesOf(user);
    const canReports = roles.some((r) =>
      ["super_admin", "leadership", "manager", "team_lead"].includes(r)
    );
    const canPeople = roles.some((r) => ["super_admin", "leadership", "hr"].includes(r));
    const list: MenuProps["items"] = [
      { key: "/workspace", icon: <HomeOutlined />, label: "My Workspace" },
      {
        key: "/tasks",
        icon: <CheckSquareOutlined />,
        label: level >= 2 ? "Team Tasks" : "My Tasks",
      },
    ];
    if (level >= 2)
      list.push({ key: "/my-team", icon: <TeamOutlined />, label: "My Team" });
    list.push(
      {
        key: "/approvals",
        icon: <AuditOutlined />,
        label: (
          <Flex align="center" justify="space-between">
            Approvals
            {inbox > 0 && <Badge count={inbox} size="small" />}
          </Flex>
        ),
      }
    );
    if (canReports)
      list.push({ key: "/reports", icon: <BarChartOutlined />, label: "Reports" });
    list.push(
      { key: "/calendar", icon: <CalendarOutlined />, label: "Calendar" },
      { key: "/documents", icon: <FileProtectOutlined />, label: "Documents" },
      { type: "divider" }
    );
    if (dashboards.length > 0)
      list.push({
        key: "dashboards",
        icon: <DashboardOutlined />,
        label: "Dashboards",
        children: dashboards.map((d) => ({
          key: `/dashboard/${d.key}`,
          label: d.title,
        })),
      });

    const successChildren = buildSuccessChildren(modules, level);
    if (successChildren.length > 0)
      list.push({
        key: "success",
        icon: <AimOutlined />,
        label: "Indicator Of Success",
        children: successChildren,
      });

    const forecasterChildren = buildForecasterChildren(modules);
    if (forecasterChildren.length > 0)
      list.push({
        key: "forecaster",
        icon: <FundProjectionScreenOutlined />,
        label: "Financial Forecaster",
        children: forecasterChildren,
      });

    const managementChildren = buildManagementChildren(modules);
    if (managementChildren.length > 0)
      list.push({
        key: "management",
        icon: <ControlOutlined />,
        label: "Management Overview",
        children: managementChildren,
      });

    const resourceChildren = buildResourceChildren(level);
    if (resourceChildren.length > 0)
      list.push({
        key: "resource",
        icon: <ClusterOutlined />,
        label: "Resource Management",
        children: resourceChildren,
      });

    if (canPeople)
      list.push({ key: "/people", icon: <TeamOutlined />, label: "People (HR)" });
    if (level >= 3)
      list.push({ key: "/org-chart", icon: <ApartmentOutlined />, label: "Org Chart" });
    list.push(
      { key: "/my-payslip", icon: <IdcardOutlined />, label: "My Payslip" },
      { key: "/awards", icon: <TrophyOutlined />, label: "Awards" }
    );
    if (level >= 4)
      list.push({ key: "/analytics", icon: <BarChartOutlined />, label: "Analytics" });
    if (user.role === "super_admin")
      list.push({ key: "/admin", icon: <SettingOutlined />, label: "Admin" });
    return list;
  }, [user, level, dashboards, modules, inbox]);

  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;

  const flat: { key: string; label: string }[] = [];
  items?.forEach((i) => {
    if (!i || !("key" in i) || i.key == null) return;
    const label = "label" in i && typeof i.label === "string" ? i.label : String(i.key);
    if (typeof i.key === "string" && i.key.startsWith("/"))
      flat.push({ key: i.key, label });
    if ("children" in i && Array.isArray(i.children))
      i.children.forEach((c) => {
        if (c && "key" in c && typeof c.key === "string")
          flat.push({
            key: c.key,
            label: "label" in c && typeof c.label === "string" ? c.label : c.key,
          });
      });
  });
  const active = flat.find((l) => location.pathname.startsWith(l.key));
  const selected = active?.key ?? location.pathname;
  const titles: Record<string, string> = {
    "/workspace": "My Workspace",
    "/my-team": "My Team",
    "/tasks": level >= 2 ? "Team Tasks" : "My Tasks",
    "/approvals": "Approvals",
    "/calendar": "Calendar",
  };
  const title = titles[active?.key ?? ""] ?? active?.label ?? "IO";
  const subtitles: Record<string, string> = {
    "/documents": "Central repository for marketing documents, assets and brand resources.",
    "/tasks": "Projects, tasks and workload across your teams.",
    "/reports": "Create, schedule and share reports across all domains.",
    "/success/central": "Company-wide productivity, efficiency, and growth at a glance.",
    "/success/organization": "Headcount, attrition, payroll, and workforce demographics.",
    "/success/marketing": "Campaigns, leads, conversion, and channel performance.",
    "/success/finance": "Revenue, expenses, margins, and cash flow.",
    "/success/startup": "Customer, revenue, and burn metrics for growth tracking.",
    "/success/operations": "Task throughput, on-time delivery, and process efficiency.",
    "/forecaster/overview": "Executive summary of financial performance and forecasts.",
    "/forecaster/workforce": "Headcount, hiring, attrition, and workforce forecast.",
    "/forecaster/revenue": "Revenue actuals vs forecast and segment breakdown.",
    "/forecaster/cashflow": "Cash position, inflows/outflows, and balance forecast.",
    "/forecaster/costs": "Expense categories, trends, and cost forecast.",
    "/forecaster/analyzer": "Payment status, overdue amounts, and success rate.",
    "/management/insights": "AI-detected problems across operations, finance, HR, and marketing.",
    "/management/bugs": "Bug creation, resolution, and severity trends across projects.",
    "/management/report": "Per-project status: progress, stages, tasks, and billing.",
    "/resource/dashboard": "Real-time overview of teams, resources and work lifecycle.",
    "/resource/capacity": "Team-by-team capacity and utilization.",
    "/resource/planner": "Plan and allocate resources across projects.",
    "/resource/lifecycle": "Work lifecycle stages across every department.",
    "/resource/reports": "Resource utilization and allocation reports.",
  };
  const subtitle = subtitles[active?.key ?? ""];

  const navContent = (
    <Flex vertical className="h-full">
      <Flex align="center" justify="center" gap={10} className="px-2.5 pt-4 pb-2">
        <img
          src="/flynava-logo.png"
          alt="FlyNava Technologies"
          className={!isMobile && collapsed ? "h-[26px] w-auto block" : "h-12 w-auto block"}
        />
        {(isMobile || !collapsed) && (
          <span className="text-[22px] font-extrabold tracking-wide bg-gradient-to-br from-io-600 to-io-900 bg-clip-text text-transparent border-l-2 border-[#e3e8e5] dark:border-white/15 pl-2.5 leading-tight">
            IO
          </span>
        )}
      </Flex>
      <div className="flex-1 overflow-y-auto px-1.5 pt-4">
        <Menu
          theme={dark ? "dark" : "light"}
          mode="inline"
          selectedKeys={[selected]}
          items={items}
          onClick={({ key }) => {
            if (key.startsWith("/")) navigate(key);
            setMobileNavOpen(false);
          }}
          className="bg-transparent border-e-0"
        />
      </div>
    </Flex>
  );

  return (
    <AntLayout className="h-screen">
      {isMobile ? (
        <Drawer
          placement="left"
          open={mobileNavOpen}
          onClose={() => setMobileNavOpen(false)}
          closable={false}
          width={236}
          styles={{ body: { padding: 0 } }}
        >
          {navContent}
        </Drawer>
      ) : (
        <Sider
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          theme={dark ? "dark" : "light"}
          width={236}
          className="flex flex-col border-r border-[#eef0f4] dark:border-white/10"
        >
          {navContent}
        </Sider>
      )}

      <AntLayout>
        <Header className="flex items-center justify-between min-h-16 py-2 [line-height:normal] px-3 sm:px-6 border-b border-black/[0.06] dark:border-white/10 gap-3">
          <Flex align="center" gap={12} className="min-w-0">
            {isMobile && (
              <Button
                type="text"
                icon={<MenuOutlined />}
                onClick={() => setMobileNavOpen(true)}
                aria-label="Open navigation"
              />
            )}
            <div className="min-w-0 leading-none">
              <div className="text-io-600 font-semibold text-lg leading-none truncate">{title}</div>
              {subtitle && (
                <Text type="secondary" className="text-[11px] leading-none mt-0.5 hidden sm:block" ellipsis>
                  {subtitle}
                </Text>
              )}
            </div>
          </Flex>
          <Flex align="center" gap={16} className="h-full overflow-x-auto">
            <div className="hidden sm:block">
              <AskIO />
            </div>
            <NotificationBell />
            <Flex align="center" gap={6} className="hidden sm:flex">
              <BulbOutlined />
              <Switch
                size="small"
                checked={dark}
                onChange={toggle}
                aria-label="Toggle theme"
              />
            </Flex>
            <Dropdown
              menu={{
                items: [
                  {
                    key: "role",
                    label: (
                      <Text type="secondary" className="capitalize">
                        {user.designation ?? user.role?.replace("_", " ")}
                      </Text>
                    ),
                    disabled: true,
                  },
                  { type: "divider" },
                  {
                    key: "logout",
                    icon: <LogoutOutlined />,
                    label: "Logout",
                    onClick: logout,
                  },
                ],
              }}
            >
              <Button type="text" className="h-auto p-1">
                <Flex align="center" gap={8}>
                  <Avatar size="small" className="bg-io-600" icon={<UserOutlined />} />
                  <Flex vertical align="flex-start" className="leading-tight hidden sm:flex">
                    <span>{user.name}</span>
                    {user.designation && (
                      <Text type="secondary" className="text-[11px]">
                        {user.designation}
                      </Text>
                    )}
                  </Flex>
                </Flex>
              </Button>
            </Dropdown>
          </Flex>
        </Header>
        <Content className="p-3 sm:p-5 sm:pt-5 overflow-y-auto">
          <Outlet />
        </Content>
      </AntLayout>
      <InayaChat />
    </AntLayout>
  );
}
