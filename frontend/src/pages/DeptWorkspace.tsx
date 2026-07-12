import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Avatar,
  Button,
  Card,
  Col,
  Empty,
  Flex,
  List,
  Progress,
  Row,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import {
  CalendarOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  ProfileOutlined,
  SyncOutlined,
  UserAddOutlined,
} from "@ant-design/icons";
import {
  api,
  ApiError,
  type DeptTeamSummary,
  type DeptWorkspaceData,
  type IoRequest,
  type WorkspaceData,
} from "../lib/api";
import { BRAND } from "../lib/brand";
import KpiCard from "../components/KpiCard";

const { Text, Title } = Typography;

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good Morning";
  if (h < 17) return "Good Afternoon";
  return "Good Evening";
}

function pct(part: number, total: number): string {
  return total > 0 ? `${Math.round((part / total) * 100)}%` : "0%";
}

function StatTile({
  icon,
  label,
  value,
  sub,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  sub: string;
  color: string;
}) {
  return (
    <Card size="small" bordered={false} style={{ height: "100%" }}>
      <Flex gap={12} align="center">
        <Avatar shape="square" size={42} style={{ background: `${color}22`, color }} icon={icon} />
        <div>
          <Text type="secondary" style={{ fontSize: 12 }}>{label}</Text>
          <div style={{ fontSize: 24, fontWeight: 700, lineHeight: 1.1 }}>{value}</div>
          <Text type="secondary" style={{ fontSize: 11 }}>{sub}</Text>
        </div>
      </Flex>
    </Card>
  );
}

function loadColor(openPct: number): string {
  if (openPct > 80) return "#ef4444";
  if (openPct > 50) return "#f59e0b";
  return BRAND.primary;
}

function dayLabel(iso: string): string {
  const d = iso.slice(0, 10);
  const today = new Date().toISOString().slice(0, 10);
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  if (d === today) return "Today";
  if (d === tomorrow) return "Tomorrow";
  return d;
}

const TYPE_LABEL: Record<string, string> = {
  hr_grievance: "HR Grievance",
  leave: "Leave Request",
  reimbursement: "Reimbursement",
  document: "Document Approval",
  general: "General Request",
};

const DEPT_LABEL: Record<string, string> = {
  eng: "Engineering",
  fin: "Finance",
  hr: "Human Resources",
  mkt: "Marketing",
};

export default function DeptWorkspace() {
  const [ws, setWs] = useState<WorkspaceData | null>(null);
  const [dept, setDept] = useState<DeptWorkspaceData | null>(null);
  const [inbox, setInbox] = useState<IoRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .workspaceMe()
      .then(setWs)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load workspace"));
    api.workspaceDepartment().then(setDept).catch(() => setDept(null));
    api.requestInbox().then(setInbox).catch(() => setInbox([]));
  }, []);

  if (error) return <Alert type="error" message={error} showIcon />;
  if (!ws)
    return (
      <Flex justify="center" style={{ paddingTop: 80 }}>
        <Spin />
      </Flex>
    );

  const teams = dept?.teams ?? [];
  const b = teams.reduce(
    (acc, t) => ({
      total: acc.total + t.buckets.total,
      completed: acc.completed + t.buckets.completed,
      in_progress: acc.in_progress + t.buckets.in_progress,
      pending: acc.pending + t.buckets.pending,
      overdue: acc.overdue + t.buckets.overdue,
    }),
    { total: 0, completed: 0, in_progress: 0, pending: 0, overdue: 0 }
  );

  const meetingDays: Record<string, typeof ws.meetings> = {};
  ws.meetings.forEach((m) => {
    const k = dayLabel(m.start);
    meetingDays[k] = meetingDays[k] ?? [];
    meetingDays[k].push(m);
  });

  const teamCols = [
    {
      title: "Team",
      key: "name",
      render: (_: unknown, t: DeptTeamSummary) => (
        <div>
          <Text strong style={{ fontSize: 13 }}>{t.name}</Text>
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>
              {t.lead_name ?? "No lead"} · {t.member_count} member{t.member_count === 1 ? "" : "s"}
            </Text>
          </div>
        </div>
      ),
    },
    {
      title: "Tasks Completed",
      key: "done",
      width: 160,
      render: (_: unknown, t: DeptTeamSummary) => (
        <Flex gap={8} align="center">
          <Progress
            percent={t.buckets.total ? Math.round((t.buckets.completed / t.buckets.total) * 100) : 0}
            size="small"
            showInfo={false}
            strokeColor={BRAND.primary}
            style={{ width: 80 }}
          />
          <Text style={{ fontSize: 12 }}>{t.buckets.completed} / {t.buckets.total}</Text>
        </Flex>
      ),
    },
    {
      title: "Overdue",
      key: "overdue",
      width: 90,
      render: (_: unknown, t: DeptTeamSummary) =>
        t.buckets.overdue > 0 ? <Tag color="error">{t.buckets.overdue}</Tag> : <Tag>0</Tag>,
    },
    {
      title: "Reopened Bugs",
      key: "reopened",
      width: 120,
      render: (_: unknown, t: DeptTeamSummary) =>
        t.reopened_count > 0 ? <Tag color="orange">{t.reopened_count}</Tag> : <Tag>0</Tag>,
    },
  ];

  return (
    <div>
      {/* Greeting */}
      <Flex justify="space-between" align="center" wrap gap={12} style={{ marginBottom: 16 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>
            {greeting()}, {ws.user.name.split(" ")[0]}!
          </Title>
          <Text type="secondary">
            {DEPT_LABEL[dept?.department ?? ""] ?? "Department"} overview — {teams.length} team
            {teams.length === 1 ? "" : "s"}
          </Text>
        </div>
        <Card size="small" bordered={false}>
          <Flex vertical align="flex-end" gap={2}>
            <Text strong>
              <CalendarOutlined />{" "}
              {new Date().toLocaleDateString(undefined, {
                weekday: "long",
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              <ClockCircleOutlined />{" "}
              {new Date().toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
            </Text>
          </Flex>
        </Card>
      </Flex>

      {/* Department-wide KPI tiles */}
      <Row gutter={[16, 16]}>
        <Col flex="1 1 160px">
          <StatTile icon={<ProfileOutlined />} label="Dept Tasks" value={b.total}
            sub="Across all teams" color={BRAND.primary} />
        </Col>
        <Col flex="1 1 160px">
          <StatTile icon={<CheckCircleOutlined />} label="Completed" value={b.completed}
            sub={pct(b.completed, b.total)} color="#157f52" />
        </Col>
        <Col flex="1 1 160px">
          <StatTile icon={<SyncOutlined />} label="In Progress" value={b.in_progress}
            sub={pct(b.in_progress, b.total)} color="#f59e0b" />
        </Col>
        <Col flex="1 1 160px">
          <StatTile icon={<ClockCircleOutlined />} label="Pending" value={b.pending}
            sub={pct(b.pending, b.total)} color="#7cc8e0" />
        </Col>
        <Col flex="1 1 160px">
          <StatTile icon={<ExclamationCircleOutlined />} label="Overdue" value={b.overdue}
            sub={pct(b.overdue, b.total)} color="#ef4444" />
        </Col>
      </Row>

      {/* Dept KPI strip */}
      {dept && dept.dept_kpis.length > 0 && (
        <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
          {dept.dept_kpis.slice(0, 4).map((k) => (
            <Col key={k.kpi_id} xs={12} md={6}>
              <KpiCard kpi={k} />
            </Col>
          ))}
        </Row>
      )}

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        {/* Main column */}
        <Col xs={24} xl={16}>
          <Row gutter={[16, 16]}>
            <Col xs={24}>
              <Card size="small" bordered={false} title="Team Performance">
                {teams.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No teams in this department yet" />
                ) : (
                  <Table
                    size="small"
                    rowKey="team_id"
                    dataSource={teams}
                    columns={teamCols}
                    pagination={false}
                  />
                )}
              </Card>
            </Col>
            <Col xs={24} lg={14}>
              <Card
                size="small"
                bordered={false}
                title="Recent Department Activities"
                extra={<Button type="link" size="small" onClick={() => navigate("/notifications")}>View All</Button>}
              >
                {ws.activity.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Nothing yet" />
                ) : (
                  <List
                    size="small"
                    dataSource={ws.activity}
                    renderItem={(a) => (
                      <List.Item>
                        <List.Item.Meta
                          avatar={
                            <Avatar size="small" style={{ background: BRAND.primary }}>
                              {a.actor_name?.[0] ?? "?"}
                            </Avatar>
                          }
                          title={
                            <Text style={{ fontSize: 13 }}>
                              {a.actor_name} {a.text}
                            </Text>
                          }
                          description={
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              {a.at ? new Date(a.at).toLocaleString() : ""}
                            </Text>
                          }
                        />
                      </List.Item>
                    )}
                  />
                )}
              </Card>
            </Col>
            <Col xs={24} lg={10}>
              <Card
                size="small"
                bordered={false}
                title="My Calendar"
                extra={<Button type="link" size="small" onClick={() => navigate("/calendar")}>View Calendar</Button>}
                style={{ height: "100%" }}
              >
                {ws.meetings.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No upcoming meetings" />
                ) : (
                  Object.entries(meetingDays).map(([day, ms]) => (
                    <div key={day} style={{ marginBottom: 10 }}>
                      <Text strong style={{ fontSize: 12 }}>{day}</Text>
                      {ms.map((m) => (
                        <Flex key={m.meeting_id} gap={8} align="center" style={{ padding: "6px 0" }}>
                          <Text type="secondary" style={{ fontSize: 12, width: 62 }}>
                            {m.start.slice(11, 16)}
                          </Text>
                          <span
                            style={{
                              width: 8,
                              height: 8,
                              borderRadius: 4,
                              background: BRAND.primary,
                              flexShrink: 0,
                            }}
                          />
                          <Text style={{ fontSize: 13 }}>{m.title}</Text>
                        </Flex>
                      ))}
                    </div>
                  ))
                )}
              </Card>
            </Col>
          </Row>
        </Col>

        {/* Right rail */}
        <Col xs={24} xl={8}>
          <Flex vertical gap={16}>
            <Card
              size="small"
              bordered={false}
              title={`Escalations${inbox.length ? ` (${inbox.length})` : ""}`}
              extra={<Button type="link" size="small" onClick={() => navigate("/approvals")}>View All</Button>}
            >
              {inbox.length === 0 ? (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  Nothing waiting on you. 🎉
                </Text>
              ) : (
                <List
                  size="small"
                  dataSource={inbox.slice(0, 5)}
                  renderItem={(r) => (
                    <List.Item
                      style={{ cursor: "pointer" }}
                      onClick={() => navigate("/approvals")}
                      actions={[<Tag key="t" color="processing">pending</Tag>]}
                    >
                      <List.Item.Meta
                        title={<Text style={{ fontSize: 13 }}>{r.title}</Text>}
                        description={
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            {TYPE_LABEL[r.type] ?? r.type} · {r.requester_name}
                          </Text>
                        }
                      />
                    </List.Item>
                  )}
                />
              )}
            </Card>

            <Card
              size="small"
              bordered={false}
              title={
                <Flex align="center" gap={6}>
                  <UserAddOutlined style={{ color: BRAND.primary }} /> Open Positions
                </Flex>
              }
            >
              {!dept || dept.positions.length === 0 ? (
                <Text type="secondary" style={{ fontSize: 12 }}>No open roles in this department.</Text>
              ) : (
                <List
                  size="small"
                  dataSource={dept.positions}
                  renderItem={(p) => (
                    <List.Item
                      actions={[
                        <Tag key="d" color={p.days_open > 40 ? "red" : p.days_open > 20 ? "orange" : undefined}>
                          {p.days_open}d
                        </Tag>,
                      ]}
                    >
                      <List.Item.Meta
                        title={<Text style={{ fontSize: 13 }}>{p.title}</Text>}
                        description={
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            {p.candidates} candidate{p.candidates === 1 ? "" : "s"}
                          </Text>
                        }
                      />
                    </List.Item>
                  )}
                />
              )}
            </Card>

            <Card size="small" bordered={false} title="Team Workload">
              {teams.length === 0 ? (
                <Text type="secondary" style={{ fontSize: 12 }}>No teams</Text>
              ) : (
                <>
                  {teams.map((t) => {
                    const openPct = t.buckets.total
                      ? Math.round(((t.buckets.total - t.buckets.completed) / t.buckets.total) * 100)
                      : 0;
                    return (
                      <Flex key={t.team_id} align="center" gap={10} style={{ marginBottom: 8 }}>
                        <Text style={{ fontSize: 12, width: 96 }} ellipsis>{t.name}</Text>
                        <Progress
                          percent={openPct}
                          size="small"
                          strokeColor={loadColor(openPct)}
                          style={{ flex: 1 }}
                        />
                      </Flex>
                    );
                  })}
                  <Flex gap={12} style={{ marginTop: 6 }}>
                    <Text type="secondary" style={{ fontSize: 11 }}>● 0–50% Low</Text>
                    <Text type="secondary" style={{ fontSize: 11, color: "#f59e0b" }}>● 51–80% Medium</Text>
                    <Text type="secondary" style={{ fontSize: 11, color: "#ef4444" }}>● 81–100% High</Text>
                  </Flex>
                </>
              )}
            </Card>
          </Flex>
        </Col>
      </Row>
    </div>
  );
}
