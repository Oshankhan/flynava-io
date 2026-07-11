import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Avatar,
  Badge,
  Button,
  Card,
  Dropdown,
  Flex,
  Layout as AntLayout,
  Menu,
  type MenuProps,
  notification,
  Switch,
  Typography,
} from "antd";
import {
  AuditOutlined,
  BellOutlined,
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
import { BRAND } from "../lib/brand";
import AskIO from "./AskIO";
import NotificationBell from "./NotificationBell";

const { Sider, Header, Content } = AntLayout;
const { Text, Title } = Typography;

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

export default function Layout() {
  const { user, logout } = useAuth();
  const { dark, toggle } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const [dashboards, setDashboards] = useState<DashboardLink[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [unread, setUnread] = useState(0);
  const [inbox, setInbox] = useState(0);
  const lastUnread = useRef<number | null>(null);

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
      setUnread(count);
      if (levelOf(user) >= 2) setInbox((await api.requestInbox()).length);
    } catch {
      /* ignore */
    }
  }, [user, navigate]);

  useEffect(() => {
    if (!user) return;
    poll();
    const t = setInterval(poll, 30000);
    return () => clearInterval(t);
  }, [user, poll]);

  const items = useMemo(() => {
    if (!user) return [];
    const canReports = ["super_admin", "leadership", "manager", "team_lead"].includes(user.role);
    const canPeople = ["super_admin", "leadership", "hr"].includes(user.role);
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
      { key: "/ai", icon: <CommentOutlined />, label: "AI Workspace" },
      { key: "/knowledge", icon: <BookOutlined />, label: "Knowledge Base" },
      {
        key: "/notifications",
        icon: <BellOutlined />,
        label: (
          <Flex align="center" justify="space-between">
            Notifications
            {unread > 0 && <Badge count={unread} size="small" />}
          </Flex>
        ),
      },
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
    list.push(
      { key: "/my-payslip", icon: <IdcardOutlined />, label: "My Payslip" },
      { key: "/awards", icon: <TrophyOutlined />, label: "Awards" }
    );
    if (user.role === "super_admin")
      list.push({ key: "/admin", icon: <SettingOutlined />, label: "Admin" });
    return list;
  }, [user, level, dashboards, unread, inbox]);

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
    "/ai": "AI Workspace",
    "/knowledge": "Knowledge Base",
    "/notifications": "Notifications",
  };
  const title = titles[active?.key ?? ""] ?? active?.label ?? "IO";

  const quick = [
    { icon: <PlusOutlined />, label: "Create Task", to: "/tasks?new=1" },
    { icon: <UploadOutlined />, label: "Upload Document", to: "/documents" },
    { icon: <CommentOutlined />, label: "Ask IO", to: "/ai" },
    { icon: <DashboardOutlined />, label: "View Reports", to: dashboards[0] ? `/dashboard/${dashboards[0].key}` : "/documents" },
  ];

  return (
    <AntLayout style={{ height: "100vh" }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme={dark ? "dark" : "light"}
        width={236}
        style={{
          display: "flex",
          flexDirection: "column",
          borderRight: dark ? "1px solid rgba(255,255,255,0.08)" : "1px solid #eef0f4",
        }}
      >
        <Flex vertical style={{ height: "100%" }}>
          <Flex align="center" justify="center" gap={10} style={{ padding: "16px 10px 8px" }}>
            <img
              src="/flynava-logo.png"
              alt="FlyNava Technologies"
              style={{ height: collapsed ? 26 : 48, width: "auto", display: "block" }}
            />
            {!collapsed && (
              <span
                style={{
                  fontSize: 22,
                  fontWeight: 800,
                  letterSpacing: 1,
                  background: `linear-gradient(135deg, ${BRAND.primary} 0%, ${BRAND.primaryStrong} 100%)`,
                  WebkitBackgroundClip: "text",
                  backgroundClip: "text",
                  color: "transparent",
                  borderLeft: dark ? "2px solid rgba(255,255,255,0.15)" : "2px solid #e3e8e5",
                  paddingLeft: 10,
                  lineHeight: 1.1,
                }}
              >
                IO
              </span>
            )}
          </Flex>
          <div style={{ flex: 1, overflowY: "auto", paddingInline: 6, paddingTop: 16 }}>
            <Menu
              theme={dark ? "dark" : "light"}
              mode="inline"
              selectedKeys={[selected]}
              items={items}
              onClick={({ key }) => {
                if (key.startsWith("/")) navigate(key);
              }}
              style={{ background: "transparent", borderInlineEnd: 0 }}
            />
          </div>
          {!collapsed && (
            <Card
              size="small"
              title={<Text type="secondary" style={{ fontSize: 12, fontWeight: 600 }}>Quick Links</Text>}
              style={{
                margin: 10,
                background: dark ? "rgba(255,255,255,0.04)" : "#f7f8fa",
                border: "none",
              }}
              styles={{ body: { padding: "4px 8px 8px" } }}
            >
              {quick.map((q) => (
                <Button
                  key={q.label}
                  type="text"
                  size="small"
                  icon={q.icon}
                  onClick={() => navigate(q.to)}
                  style={{
                    display: "flex",
                    width: "100%",
                    justifyContent: "flex-start",
                  }}
                >
                  {q.label}
                </Button>
              ))}
            </Card>
          )}
        </Flex>
      </Sider>

      <AntLayout>
        <Header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            height: 64,
            lineHeight: "normal",
            paddingInline: 24,
            borderBottom: "1px solid rgba(0,0,0,0.06)",
          }}
        >
          <Title level={4} style={{ margin: 0, color: BRAND.primary }}>
            {title}
          </Title>
          <Flex align="center" gap={16} style={{ height: "100%" }}>
            <AskIO />
            <NotificationBell />
            <Flex align="center" gap={6}>
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
                      <Text type="secondary" style={{ textTransform: "capitalize" }}>
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
              <Button type="text" style={{ height: "auto", padding: 4 }}>
                <Flex align="center" gap={8}>
                  <Avatar size="small" style={{ background: BRAND.primary }} icon={<UserOutlined />} />
                  <Flex vertical align="flex-start" style={{ lineHeight: 1.2 }}>
                    <span>{user.name}</span>
                    {user.designation && (
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {user.designation}
                      </Text>
                    )}
                  </Flex>
                </Flex>
              </Button>
            </Dropdown>
          </Flex>
        </Header>
        <Content style={{ padding: "20px 24px 24px", overflowY: "auto" }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
}
