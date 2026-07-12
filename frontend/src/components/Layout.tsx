import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Avatar,
  Badge,
  Button,
  Card,
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
  ApartmentOutlined,
  AuditOutlined,
  BarChartOutlined,
  BookOutlined,
  BulbOutlined,
  CalendarOutlined,
  CheckSquareOutlined,
  CommentOutlined,
  DashboardOutlined,
  FileProtectOutlined,
  HomeOutlined,
  IdcardOutlined,
  LogoutOutlined,
  MailOutlined,
  MenuOutlined,
  PlusOutlined,
  SettingOutlined,
  TeamOutlined,
  TrophyOutlined,
  UploadOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { api, type DashboardLink, type User } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useTheme } from "../lib/theme";
import AskIO from "./AskIO";
import NotificationBell from "./NotificationBell";
import InayaChat, { INAYA_OPEN_EVENT } from "./InayaChat";

const { Sider, Header, Content } = AntLayout;
const { Text, Title } = Typography;
const { useBreakpoint } = Grid;

const ROLE_LEVEL: Record<string, number> = {
  super_admin: 4,
  leadership: 4,
  manager: 3,
  hr: 3,
  marketing: 3,
  team_lead: 2,
  employee: 1,
  investor: 0,
  partner: 0,
};

export function levelOf(user: User | null): number {
  if (!user) return 1;
  return typeof user.level === "number" ? user.level : ROLE_LEVEL[user.role] ?? 1;
}

export function rolesOf(user: User | null): string[] {
  if (!user) return [];
  return user.roles && user.roles.length > 0 ? user.roles : [user.role];
}

export default function Layout() {
  const { user, logout } = useAuth();
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
    ];
    if (level >= 2)
      list.push({ key: "/my-team", icon: <TeamOutlined />, label: "My Team" });
    list.push(
      {
        key: "/tasks",
        icon: <CheckSquareOutlined />,
        label: level >= 2 ? "Team Tasks" : "My Tasks",
      },
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
      list.push({ key: "/reports", icon: <MailOutlined />, label: "Reports" });
    list.push(
      { key: "/calendar", icon: <CalendarOutlined />, label: "Calendar" },
      { key: "/documents", icon: <FileProtectOutlined />, label: "Documents" },
      { key: "/knowledge", icon: <BookOutlined />, label: "Knowledge Base" },
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
  }, [user, level, dashboards, inbox]);

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
    "/knowledge": "Knowledge Base",
  };
  const title = titles[active?.key ?? ""] ?? active?.label ?? "IO";

  const quick = [
    { icon: <PlusOutlined />, label: "Create Task", to: "/tasks?new=1" },
    { icon: <UploadOutlined />, label: "Upload Document", to: "/documents" },
    { icon: <CommentOutlined />, label: "Ask Inaya", to: null },
    { icon: <DashboardOutlined />, label: "View Reports", to: dashboards[0] ? `/dashboard/${dashboards[0].key}` : "/documents" },
  ];

  const showQuickLinks = isMobile || !collapsed;

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
      {showQuickLinks && (
        <Card
          size="small"
          title={<Text type="secondary" className="text-xs font-semibold">Quick Links</Text>}
          className="m-2.5 bg-[#f7f8fa] dark:bg-white/[0.04] border-none"
          classNames={{ body: "px-2 pb-2 pt-1" }}
        >
          {quick.map((q) => (
            <Button
              key={q.label}
              type="text"
              size="small"
              icon={q.icon}
              onClick={() => {
                setMobileNavOpen(false);
                if (q.to) navigate(q.to);
                else window.dispatchEvent(new Event(INAYA_OPEN_EVENT));
              }}
              className="flex w-full justify-start"
            >
              {q.label}
            </Button>
          ))}
        </Card>
      )}
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
        <Header className="flex items-center justify-between h-16 [line-height:normal] px-3 sm:px-6 border-b border-black/[0.06] dark:border-white/10 gap-3">
          <Flex align="center" gap={12} className="min-w-0">
            {isMobile && (
              <Button
                type="text"
                icon={<MenuOutlined />}
                onClick={() => setMobileNavOpen(true)}
                aria-label="Open navigation"
              />
            )}
            <Title level={4} className="m-0 shrink-0 text-io-600">
              {title}
            </Title>
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
