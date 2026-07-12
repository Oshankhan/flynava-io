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
      <Flex justify="center" className="pt-20">
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
          <Avatar size="small" className="bg-io-600">{m.name[0]}</Avatar>
          <Text className="text-[13px]">{m.name}</Text>
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
            strokeColor="#157f52"
            className="w-[70px]"
          />
          <Text className="text-xs">{m.completed} / {m.total}</Text>
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
      <Flex justify="space-between" align="center" wrap gap={12} className="mb-4">
        <div>
          <Title level={3} className="m-0">
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
            <Text type="secondary" className="text-xs">
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
            sub="Total Assigned" tint="primary" />
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

      <div className="mt-4">
        <DeptPanel department={ws.user.department} teamId={ws.user.team_id} variant="l2" />
      </div>

      <Row gutter={[16, 16]} className="mt-4">
        {/* Main column */}
        <Col xs={24} xl={16}>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={14}>
              <Card
                size="small"
                bordered={false}
                title="Team Performance"
                extra={<Button type="link" size="small" onClick={() => navigate("/my-team")}>View Details</Button>}
                className="h-full"
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
                      scroll={{ x: true }}
                    />
                    <Button type="link" size="small" onClick={() => navigate("/my-team")}
                      className="px-0 mt-1.5">
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
                <Card size="small" bordered={false} title="Tasks by Status" className="h-full">
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
                title="My Team Calendar"
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
              title={`Pending Approvals${inbox.length ? ` (${inbox.length})` : ""}`}
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

            <Card size="small" bordered={false} title="Team Workload">
              {members.length === 0 ? (
                <Text type="secondary" className="text-xs">No members</Text>
              ) : (
                <>
                  {members.map((m) => {
                    const openPct = m.total
                      ? Math.round(((m.total - m.completed) / m.total) * 100)
                      : 0;
                    return (
                      <Flex key={m.user_id} align="center" gap={10} className="mb-2">
                        <Text className="text-xs w-24" ellipsis>{m.name}</Text>
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
