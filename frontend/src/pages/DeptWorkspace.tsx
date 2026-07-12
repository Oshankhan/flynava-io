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

const TILE_TINT = {
  primary: "bg-io-600/15 text-io-600",
  amber: "bg-amber-500/15 text-amber-500",
  sky: "bg-sky-400/15 text-sky-400",
  red: "bg-red-500/15 text-red-500",
} as const;

function StatTile({
  icon,
  label,
  value,
  sub,
  tint,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  sub: string;
  tint: keyof typeof TILE_TINT;
}) {
  return (
    <Card size="small" bordered={false} className="h-full">
      <Flex gap={12} align="center">
        <Avatar shape="square" size={42} className={TILE_TINT[tint]} icon={icon} />
        <div>
          <Text type="secondary" className="text-xs">{label}</Text>
          <div className="text-2xl font-bold leading-tight">{value}</div>
          <Text type="secondary" className="text-[11px]">{sub}</Text>
        </div>
      </Flex>
    </Card>
  );
}

function loadColor(openPct: number): string {
  if (openPct > 80) return "#ef4444";
  if (openPct > 50) return "#f59e0b";
  return "#157f52";
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
      <Flex justify="center" className="pt-20">
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
          <Text strong className="text-[13px]">{t.name}</Text>
          <div>
            <Text type="secondary" className="text-[11px]">
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
            strokeColor="#157f52"
            className="w-20"
          />
          <Text className="text-xs">{t.buckets.completed} / {t.buckets.total}</Text>
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
      <Flex justify="space-between" align="center" wrap gap={12} className="mb-4">
        <div>
          <Title level={3} className="m-0">
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
            <Text type="secondary" className="text-xs">
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
            sub="Across all teams" tint="primary" />
        </Col>
        <Col flex="1 1 160px">
          <StatTile icon={<CheckCircleOutlined />} label="Completed" value={b.completed}
            sub={pct(b.completed, b.total)} tint="primary" />
        </Col>
        <Col flex="1 1 160px">
          <StatTile icon={<SyncOutlined />} label="In Progress" value={b.in_progress}
            sub={pct(b.in_progress, b.total)} tint="amber" />
        </Col>
        <Col flex="1 1 160px">
          <StatTile icon={<ClockCircleOutlined />} label="Pending" value={b.pending}
            sub={pct(b.pending, b.total)} tint="sky" />
        </Col>
        <Col flex="1 1 160px">
          <StatTile icon={<ExclamationCircleOutlined />} label="Overdue" value={b.overdue}
            sub={pct(b.overdue, b.total)} tint="red" />
        </Col>
      </Row>

      {/* Dept KPI strip */}
      {dept && dept.dept_kpis.length > 0 && (
        <Row gutter={[16, 16]} className="mt-4">
          {dept.dept_kpis.slice(0, 4).map((k) => (
            <Col key={k.kpi_id} xs={12} md={6}>
              <KpiCard kpi={k} />
            </Col>
          ))}
        </Row>
      )}

      <Row gutter={[16, 16]} className="mt-4">
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
                    scroll={{ x: true }}
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
                            <Avatar size="small" className="bg-io-600">
                              {a.actor_name?.[0] ?? "?"}
                            </Avatar>
                          }
                          title={
                            <Text className="text-[13px]">
                              {a.actor_name} {a.text}
                            </Text>
                          }
                          description={
                            <Text type="secondary" className="text-[11px]">
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
                className="h-full"
              >
                {ws.meetings.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No upcoming meetings" />
                ) : (
                  Object.entries(meetingDays).map(([day, ms]) => (
                    <div key={day} className="mb-2.5">
                      <Text strong className="text-xs">{day}</Text>
                      {ms.map((m) => (
                        <Flex key={m.meeting_id} gap={8} align="center" className="py-1.5">
                          <Text type="secondary" className="text-xs w-[62px]">
                            {m.start.slice(11, 16)}
                          </Text>
                          <span className="w-2 h-2 rounded-full bg-io-600 shrink-0" />
                          <Text className="text-[13px]">{m.title}</Text>
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
                <Text type="secondary" className="text-xs">
                  Nothing waiting on you. 🎉
                </Text>
              ) : (
                <List
                  size="small"
                  dataSource={inbox.slice(0, 5)}
                  renderItem={(r) => (
                    <List.Item
                      className="cursor-pointer"
                      onClick={() => navigate("/approvals")}
                      actions={[<Tag key="t" color="processing">pending</Tag>]}
                    >
                      <List.Item.Meta
                        title={<Text className="text-[13px]">{r.title}</Text>}
                        description={
                          <Text type="secondary" className="text-[11px]">
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
                  <UserAddOutlined className="text-io-600" /> Open Positions
                </Flex>
              }
            >
              {!dept || dept.positions.length === 0 ? (
                <Text type="secondary" className="text-xs">No open roles in this department.</Text>
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
                        title={<Text className="text-[13px]">{p.title}</Text>}
                        description={
                          <Text type="secondary" className="text-[11px]">
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
                <Text type="secondary" className="text-xs">No teams</Text>
              ) : (
                <>
                  {teams.map((t) => {
                    const openPct = t.buckets.total
                      ? Math.round(((t.buckets.total - t.buckets.completed) / t.buckets.total) * 100)
                      : 0;
                    return (
                      <Flex key={t.team_id} align="center" gap={10} className="mb-2">
                        <Text className="text-xs w-24" ellipsis>{t.name}</Text>
                        <Progress
                          percent={openPct}
                          size="small"
                          strokeColor={loadColor(openPct)}
                          className="flex-1"
                        />
                      </Flex>
                    );
                  })}
                  <Flex gap={12} wrap className="mt-1.5">
                    <Text type="secondary" className="text-[11px]">● 0–50% Low</Text>
                    <Text type="secondary" className="text-[11px] text-amber-500">● 51–80% Medium</Text>
                    <Text type="secondary" className="text-[11px] text-red-500">● 81–100% High</Text>
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
