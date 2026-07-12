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
import { BRAND } from "../lib/brand";
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
      <Flex justify="center" style={{ paddingTop: 80 }}>
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
      <Flex justify="space-between" align="center" wrap gap={12} style={{ marginBottom: 16 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>
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
            <Text type="secondary" style={{ fontSize: 12 }}>
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
        <DeptPanel department={data.user.department} teamId={data.user.team_id} variant="l1" />
      </div>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        {/* Main column */}
        <Col xs={24} xl={16}>
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={14}>
              <Card
                size="small"
                bordered={false}
                title="My Tasks"
                extra={<Button type="link" size="small" onClick={() => navigate("/tasks")}>View All <RightOutlined /></Button>}
                style={{ height: "100%" }}
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
                          title={<Text style={{ fontSize: 13 }}>{t.title}</Text>}
                          description={
                            <Text type="secondary" style={{ fontSize: 11 }}>
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
                <Card size="small" bordered={false} title="Tasks by Status" style={{ height: "100%" }}>
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
                {data.meetings.length === 0 ? (
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
              title={
                <Flex align="center" gap={6}>
                  <ScheduleOutlined style={{ color: BRAND.primary }} /> Leave Balance
                </Flex>
              }
              extra={<Button type="link" size="small" onClick={() => navigate("/approvals")}>Request Leave</Button>}
            >
              {leaveBalance ? (
                <Flex gap={20} justify="space-around">
                  {Object.entries(leaveBalance).map(([type, days]) => (
                    <div key={type} style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 20, fontWeight: 700, color: BRAND.primaryStrong }}>
                        {days}
                      </div>
                      <Text type="secondary" style={{ fontSize: 11 }}>{type}</Text>
                    </div>
                  ))}
                </Flex>
              ) : (
                <Text type="secondary" style={{ fontSize: 12 }}>No leave record linked.</Text>
              )}
            </Card>

            <Card
              size="small"
              bordered={false}
              title={
                <Flex align="center" gap={6}>
                  <BugOutlined style={{ color: "#ef7c3c" }} /> Reopened Bugs
                </Flex>
              }
            >
              {data.reopened.length === 0 ? (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  No reopened bugs on your name. 🎉
                </Text>
              ) : (
                <List
                  size="small"
                  dataSource={data.reopened}
                  renderItem={(t) => (
                    <List.Item actions={[<Tag key="p" color="orange">{t.priority ?? "—"}</Tag>]}>
                      <Text style={{ fontSize: 13 }}>{t.title}</Text>
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
                  <FileTextOutlined style={{ color: BRAND.primary }} /> My Pending Requests
                </Flex>
              }
              extra={<Button type="link" size="small" onClick={() => navigate("/approvals")}>View All</Button>}
            >
              {data.my_requests.length === 0 ? (
                <Text type="secondary" style={{ fontSize: 12 }}>
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
                        title={<Text style={{ fontSize: 13 }}>{r.title}</Text>}
                        description={
                          <Text type="secondary" style={{ fontSize: 11 }}>
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
                  strokeColor={BRAND.primary}
                  format={(p) => `${p}% open`}
                />
                <Text type="secondary" style={{ fontSize: 11 }}>
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
