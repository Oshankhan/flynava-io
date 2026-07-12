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
  Tag,
  Typography,
} from "antd";
import {
  BugOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
  ProfileOutlined,
  RightOutlined,
  ScheduleOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import { api, ApiError, type WorkspaceData } from "../lib/api";
import { useAuth } from "../lib/auth";
import StatusDonut from "../components/StatusDonut";
import DeptPanel from "../components/DeptPanel";
import { levelOf } from "../components/Layout";
import LeadWorkspace from "./LeadWorkspace";
import DeptWorkspace from "./DeptWorkspace";
import ExecWorkspace from "./ExecWorkspace";

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

const BUCKET_TAG: Record<string, string> = {
  completed: "success",
  in_progress: "processing",
  pending: "default",
  overdue: "error",
};

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

function dayLabel(iso: string): string {
  const d = iso.slice(0, 10);
  const today = new Date().toISOString().slice(0, 10);
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  if (d === today) return "Today";
  if (d === tomorrow) return "Tomorrow";
  return d;
}

export default function Workspace() {
  const { user } = useAuth();
  const level = levelOf(user);
  if (level >= 4) return <ExecWorkspace />;
  if (level === 3) return <DeptWorkspace />;
  if (level >= 2) return <LeadWorkspace />;
  return <ExecutiveWorkspace />;
}

function ExecutiveWorkspace() {
  const [data, setData] = useState<WorkspaceData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [leaveBalance, setLeaveBalance] = useState<Record<string, number> | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .workspaceMe()
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load workspace"));
    api.hrMe().then((e) => setLeaveBalance(e.leave_balance)).catch(() => setLeaveBalance(null));
  }, []);

  const donut = useMemo(() => {
    if (!data) return [];
    const b = data.buckets;
    return [
      { status: "Completed", count: b.completed },
      { status: "In Progress", count: b.in_progress },
      { status: "Pending", count: b.pending },
      { status: "Overdue", count: b.overdue },
    ].filter((s) => s.count > 0);
  }, [data]);

  if (error) return <Alert type="error" message={error} showIcon />;
  if (!data)
    return (
      <Flex justify="center" className="pt-20">
        <Spin />
      </Flex>
    );

  const b = data.buckets;
  const meetingDays: Record<string, typeof data.meetings> = {};
  data.meetings.forEach((m) => {
    const k = dayLabel(m.start);
    (meetingDays[k] = meetingDays[k] ?? []).push(m);
  });

  return (
    <div>
      {/* Greeting */}
      <Flex justify="space-between" align="center" wrap gap={12} className="mb-4">
        <div>
          <Title level={3} className="m-0">
            {greeting()}, {data.user.name.split(" ")[0]}!
          </Title>
          <Text type="secondary">
            {data.user.designation ?? ""}
            {data.team ? ` · ${data.team.name}` : ""}
            {data.lead ? ` · Reports to ${data.lead.name}` : ""}
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

      {/* KPI tiles */}
      <Row gutter={[16, 16]}>
        <Col flex="1 1 160px">
          <StatTile icon={<ProfileOutlined />} label="My Tasks" value={b.total}
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
        <DeptPanel department={data.user.department} teamId={data.user.team_id} variant="l1" />
      </div>

      <Row gutter={[16, 16]} className="mt-4">
        {/* Main column */}
        <Col xs={24} xl={16}>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={14}>
              <Card
                size="small"
                bordered={false}
                title="My Tasks"
                extra={<Button type="link" size="small" onClick={() => navigate("/tasks")}>View All <RightOutlined /></Button>}
                className="h-full"
              >
                {data.tasks.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No tasks assigned" />
                ) : (
                  <List
                    size="small"
                    dataSource={data.tasks}
                    renderItem={(t) => (
                      <List.Item
                        actions={[<Tag key="s" color={BUCKET_TAG[t.bucket]}>{t.status ?? "—"}</Tag>]}
                      >
                        <List.Item.Meta
                          title={<Text className="text-[13px]">{t.title}</Text>}
                          description={
                            <Text type="secondary" className="text-[11px]">
                              {[t.project, t.priority, t.due_date ? `due ${t.due_date}` : null]
                                .filter(Boolean)
                                .join(" · ")}
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
              {donut.length > 0 ? (
                <StatusDonut title="Tasks by Status" data={donut} centerLabel="Total Tasks" />
              ) : (
                <Card size="small" bordered={false} title="Tasks by Status" className="h-full">
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No tasks yet" />
                </Card>
              )}
            </Col>
            <Col xs={24} lg={14}>
              <Card
                size="small"
                bordered={false}
                title="Recent Activities"
                extra={<Button type="link" size="small" onClick={() => navigate("/notifications")}>View All</Button>}
              >
                {data.activity.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Nothing yet" />
                ) : (
                  <List
                    size="small"
                    dataSource={data.activity}
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
                {data.meetings.length === 0 ? (
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
              title={
                <Flex align="center" gap={6}>
                  <ScheduleOutlined className="text-io-600" /> Leave Balance
                </Flex>
              }
              extra={<Button type="link" size="small" onClick={() => navigate("/approvals")}>Request Leave</Button>}
            >
              {leaveBalance ? (
                <Flex gap={20} justify="space-around">
                  {Object.entries(leaveBalance).map(([type, days]) => (
                    <div key={type} className="text-center">
                      <div className="text-xl font-bold text-io-900">
                        {days}
                      </div>
                      <Text type="secondary" className="text-[11px]">{type}</Text>
                    </div>
                  ))}
                </Flex>
              ) : (
                <Text type="secondary" className="text-xs">No leave record linked.</Text>
              )}
            </Card>

            <Card
              size="small"
              bordered={false}
              title={
                <Flex align="center" gap={6}>
                  <BugOutlined className="text-[#ef7c3c]" /> Reopened Bugs
                </Flex>
              }
            >
              {data.reopened.length === 0 ? (
                <Text type="secondary" className="text-xs">
                  No reopened bugs on your name. 🎉
                </Text>
              ) : (
                <List
                  size="small"
                  dataSource={data.reopened}
                  renderItem={(t) => (
                    <List.Item actions={[<Tag key="p" color="orange">{t.priority ?? "—"}</Tag>]}>
                      <Text className="text-[13px]">{t.title}</Text>
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
                  <FileTextOutlined className="text-io-600" /> My Pending Requests
                </Flex>
              }
              extra={<Button type="link" size="small" onClick={() => navigate("/approvals")}>View All</Button>}
            >
              {data.my_requests.length === 0 ? (
                <Text type="secondary" className="text-xs">
                  Nothing submitted yet — raise a request from Approvals.
                </Text>
              ) : (
                <List
                  size="small"
                  dataSource={data.my_requests}
                  renderItem={(r) => (
                    <List.Item
                      actions={[
                        <Tag
                          key="s"
                          color={
                            r.status === "approved"
                              ? "success"
                              : r.status === "rejected"
                                ? "error"
                                : "processing"
                          }
                        >
                          {r.status}
                        </Tag>,
                      ]}
                    >
                      <List.Item.Meta
                        title={<Text className="text-[13px]">{r.title}</Text>}
                        description={
                          <Text type="secondary" className="text-[11px]">
                            {r.type.replace("_", " ")}
                          </Text>
                        }
                      />
                    </List.Item>
                  )}
                />
              )}
            </Card>

            {b.total > 0 && (
              <Card size="small" bordered={false} title="My Workload">
                <Progress
                  percent={Math.round(((b.total - b.completed) / b.total) * 100)}
                  strokeColor="#157f52"
                  format={(p) => `${p}% open`}
                />
                <Text type="secondary" className="text-[11px]">
                  {b.total - b.completed} of {b.total} tasks still open
                </Text>
              </Card>
            )}
          </Flex>
        </Col>
      </Row>
    </div>
  );
}
