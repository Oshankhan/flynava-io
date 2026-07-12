import { useEffect, useMemo, useState } from "react";
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
} from "@ant-design/icons";
import {
  api,
  ApiError,
  type IoRequest,
  type MemberLoad,
  type TeamTasks,
  type WorkspaceData,
} from "../lib/api";
import { BRAND } from "../lib/brand";
import StatusDonut from "../components/StatusDonut";
import DeptPanel from "../components/DeptPanel";

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

function scoreOf(m: MemberLoad): number | null {
  if (m.total === 0) return null;
  const completion = m.completed / m.total;
  const onTime = 1 - m.overdue / m.total;
  return Math.round((completion * 0.6 + onTime * 0.4) * 100);
}

function scoreColor(s: number): string {
  if (s >= 85) return "success";
  if (s >= 70) return "warning";
  return "error";
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

export default function LeadWorkspace() {
  const [ws, setWs] = useState<WorkspaceData | null>(null);
  const [team, setTeam] = useState<TeamTasks | null>(null);
  const [inbox, setInbox] = useState<IoRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .workspaceMe()
      .then(setWs)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load workspace"));
    api.teamTasks().then(setTeam).catch(() => setTeam(null));
    api.requestInbox().then(setInbox).catch(() => setInbox([]));
  }, []);

  const donut = useMemo(() => {
    if (!team) return [];
    const b = team.buckets;
    return [
      { status: "Completed", count: b.completed },
      { status: "In Progress", count: b.in_progress },
      { status: "Pending", count: b.pending },
      { status: "Overdue", count: b.overdue },
    ].filter((s) => s.count > 0);
  }, [team]);

  if (error) return <Alert type="error" message={error} showIcon />;
  if (!ws)
    return (
      <Flex justify="center" style={{ paddingTop: 80 }}>
        <Spin />
      </Flex>
    );

  const b = team?.buckets ?? ws.buckets;
  const members = (team?.members ?? []).filter((m) => m.user_id !== ws.user.user_id);

  const meetingDays: Record<string, typeof ws.meetings> = {};
  ws.meetings.forEach((m) => {
    const k = dayLabel(m.start);
    meetingDays[k] = meetingDays[k] ?? [];
    meetingDays[k].push(m);
  });

  const perfCols = [
    {
      title: "Team Member",
      key: "name",
      render: (_: unknown, m: MemberLoad) => (
        <Flex gap={8} align="center">
          <Avatar size="small" style={{ background: BRAND.primary }}>{m.name[0]}</Avatar>
          <Text style={{ fontSize: 13 }}>{m.name}</Text>
        </Flex>
      ),
    },
    {
      title: "Tasks Completed",
      key: "done",
      width: 150,
      render: (_: unknown, m: MemberLoad) => (
        <Flex gap={8} align="center">
          <Progress
            percent={m.total ? Math.round((m.completed / m.total) * 100) : 0}
            size="small"
            showInfo={false}
            strokeColor={BRAND.primary}
            style={{ width: 70 }}
          />
          <Text style={{ fontSize: 12 }}>{m.completed} / {m.total}</Text>
        </Flex>
      ),
    },
    {
      title: "On-Time %",
      key: "ontime",
      width: 90,
      render: (_: unknown, m: MemberLoad) =>
        m.total ? `${Math.round((1 - m.overdue / m.total) * 100)}%` : "—",
    },
    {
      title: "Performance",
      key: "score",
      width: 110,
      render: (_: unknown, m: MemberLoad) => {
        const s = scoreOf(m);
        return s == null ? (
          <Tag>—</Tag>
        ) : (
          <Tag color={scoreColor(s)}>{s}%</Tag>
        );
      },
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
          <Text type="secondary">Here's your team overview for today.</Text>
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

      {/* Team KPI tiles */}
      <Row gutter={[16, 16]}>
        <Col flex="1 1 160px">
          <StatTile icon={<ProfileOutlined />} label="Team Tasks" value={b.total}
            sub="Total Assigned" color={BRAND.primary} />
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

      <div style={{ marginTop: 16 }}>
        <DeptPanel department={ws.user.department} teamId={ws.user.team_id} variant="l2" />
      </div>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        {/* Main column */}
        <Col xs={24} xl={16}>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={14}>
              <Card
                size="small"
                bordered={false}
                title="Team Performance"
                extra={<Button type="link" size="small" onClick={() => navigate("/my-team")}>View Details</Button>}
                style={{ height: "100%" }}
              >
                {members.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No team members yet" />
                ) : (
                  <>
                    <Table
                      size="small"
                      rowKey="user_id"
                      dataSource={members}
                      columns={perfCols}
                      pagination={false}
                    />
                    <Button type="link" size="small" onClick={() => navigate("/my-team")}
                      style={{ paddingInline: 0, marginTop: 6 }}>
                      View full team performance
                    </Button>
                  </>
                )}
              </Card>
            </Col>
            <Col xs={24} lg={10}>
              {donut.length > 0 ? (
                <StatusDonut title="Tasks by Status" data={donut} centerLabel="Total Tasks" />
              ) : (
                <Card size="small" bordered={false} title="Tasks by Status" style={{ height: "100%" }}>
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No team tasks yet" />
                </Card>
              )}
            </Col>
            <Col xs={24} lg={14}>
              <Card
                size="small"
                bordered={false}
                title="Recent Team Activities"
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
                title="My Team Calendar"
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
              title={`Pending Approvals${inbox.length ? ` (${inbox.length})` : ""}`}
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

            <Card size="small" bordered={false} title="Team Workload">
              {members.length === 0 ? (
                <Text type="secondary" style={{ fontSize: 12 }}>No members</Text>
              ) : (
                <>
                  {members.map((m) => {
                    const openPct = m.total
                      ? Math.round(((m.total - m.completed) / m.total) * 100)
                      : 0;
                    return (
                      <Flex key={m.user_id} align="center" gap={10} style={{ marginBottom: 8 }}>
                        <Text style={{ fontSize: 12, width: 96 }} ellipsis>{m.name}</Text>
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
