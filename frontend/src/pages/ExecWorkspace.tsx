import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Avatar,
  Badge,
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
  BankOutlined,
  BugOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  ExperimentOutlined,
  FileTextOutlined,
} from "@ant-design/icons";
import { api, ApiError, type DeptRollup, type ExecWorkspaceData } from "../lib/api";
import { useAuth } from "../lib/auth";
import { BRAND } from "../lib/brand";
import KpiCard from "../components/KpiCard";
import ProjectHealth from "../components/ProjectHealth";
import StatusDonut from "../components/StatusDonut";

const { Text, Title } = Typography;

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good Morning";
  if (h < 17) return "Good Afternoon";
  return "Good Evening";
}

function deptOpenPct(d: DeptRollup): number {
  return d.buckets.total ? Math.round(((d.buckets.total - d.buckets.completed) / d.buckets.total) * 100) : 0;
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

export default function ExecWorkspace() {
  const { user } = useAuth();
  const [data, setData] = useState<ExecWorkspaceData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .execWorkspace()
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load dashboard"));
  }, []);

  if (error) return <Alert type="error" message={error} showIcon />;
  if (!data)
    return (
      <Flex justify="center" style={{ paddingTop: 80 }}>
        <Spin />
      </Flex>
    );

  const meetingDays: Record<string, typeof data.meetings> = {};
  data.meetings.forEach((m) => {
    const k = dayLabel(m.start);
    meetingDays[k] = meetingDays[k] ?? [];
    meetingDays[k].push(m);
  });

  const automationCols = [
    { title: "Script", dataIndex: "title", key: "title", ellipsis: true },
    { title: "Module", dataIndex: "module", key: "module", width: 100 },
    { title: "Owner", dataIndex: "owner", key: "owner", width: 130 },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (s: string) => (
        <Tag color={s === "pending" ? "orange" : s === "in_review" ? "blue" : "success"}>
          {s.replace("_", " ")}
        </Tag>
      ),
    },
  ];

  return (
    <div>
      <Flex justify="space-between" align="center" wrap gap={12} style={{ marginBottom: 16 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>
            {greeting()}, {user?.name?.split(" ")[0] ?? "there"}!
          </Title>
          <Text type="secondary">Here's what's happening across the company today.</Text>
        </div>
        <Card size="small" bordered={false}>
          <Flex vertical align="flex-end" gap={2}>
            <Text strong>
              <CalendarOutlined />{" "}
              {new Date().toLocaleDateString(undefined, {
                weekday: "long", day: "numeric", month: "long", year: "numeric",
              })}
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              <ClockCircleOutlined />{" "}
              {new Date().toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
            </Text>
          </Flex>
        </Card>
      </Flex>

      {/* Org-wide KPI headline */}
      {data.kpis.length > 0 && (
        <Row gutter={[16, 16]}>
          {data.kpis.slice(0, 8).map((k) => (
            <Col key={k.kpi_id} xs={12} md={6} xl={3}>
              <KpiCard kpi={k} />
            </Col>
          ))}
        </Row>
      )}

      {/* Departments — the drill-down entry point */}
      <Card
        size="small"
        bordered={false}
        style={{ marginTop: 16 }}
        title={
          <Flex align="center" gap={6}>
            <BankOutlined style={{ color: BRAND.primary }} /> Departments
          </Flex>
        }
      >
        <Row gutter={[16, 16]}>
          {data.departments.map((d) => (
            <Col key={d.dept_id} xs={24} sm={12} lg={8} xl={6}>
              <Card
                size="small"
                hoverable
                onClick={() => d.head && navigate(`/my-team?root=${d.head.user_id}`)}
                style={{ height: "100%", cursor: d.head ? "pointer" : "default" }}
              >
                <Flex align="center" gap={10} style={{ marginBottom: 8 }}>
                  <Avatar style={{ background: BRAND.primary }}>
                    {d.head?.name?.[0] ?? "?"}
                  </Avatar>
                  <div>
                    <Text strong style={{ fontSize: 13 }}>{d.head?.name ?? "Unassigned"}</Text>
                    <div>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        {d.head?.designation ?? d.name}
                      </Text>
                    </div>
                  </div>
                </Flex>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  {d.teams_count} team{d.teams_count === 1 ? "" : "s"} · {d.member_count} people
                </Text>
                <Progress
                  percent={deptOpenPct(d)}
                  size="small"
                  strokeColor={loadColor(deptOpenPct(d))}
                  style={{ marginTop: 6 }}
                  format={(p) => `${p}% open`}
                />
                <Flex gap={6} wrap style={{ marginTop: 6 }}>
                  {d.buckets.overdue > 0 && <Tag color="error">{d.buckets.overdue} overdue</Tag>}
                  {d.reopened_count > 0 && <Tag color="orange">{d.reopened_count} reopened</Tag>}
                  {d.late_today > 0 && <Tag color="gold">{d.late_today} late today</Tag>}
                  {d.buckets.overdue === 0 && d.reopened_count === 0 && d.late_today === 0 && (
                    <Tag color="success">All clear</Tag>
                  )}
                </Flex>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={14}>
          {data.projects.length > 0 ? (
            <ProjectHealth projects={data.projects} />
          ) : (
            <Card size="small" bordered={false} title="Project Health" style={{ height: "100%" }}>
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No active projects" />
            </Card>
          )}
        </Col>
        <Col xs={24} lg={10}>
          {data.bug_breakdown && data.bug_breakdown.length > 0 ? (
            <StatusDonut title="Bugs by Status" data={data.bug_breakdown} centerLabel="Total Bugs" />
          ) : (
            <Card size="small" bordered={false} title="Bugs by Status" style={{ height: "100%" }}>
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No bug data yet" />
            </Card>
          )}
        </Col>

        <Col xs={24} lg={12}>
          <Card
            size="small"
            bordered={false}
            title={
              <Flex align="center" gap={6}>
                <ExperimentOutlined style={{ color: "#7cc8e0" }} />
                QA Automation
                {data.automation.pending > 0 && <Badge count={data.automation.pending} />}
              </Flex>
            }
          >
            {data.automation.rows.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No scripts tracked" />
            ) : (
              <Table
                size="small"
                rowKey="script_id"
                dataSource={data.automation.rows}
                columns={automationCols}
                pagination={{ pageSize: 5, showSizeChanger: false }}
              />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            size="small"
            bordered={false}
            title={
              <Flex align="center" gap={6}>
                <FileTextOutlined style={{ color: BRAND.primary }} /> Pending Product Documents
              </Flex>
            }
          >
            {data.pending_docs.length === 0 ? (
              <Text type="secondary" style={{ fontSize: 12 }}>Nothing pending review.</Text>
            ) : (
              <List
                size="small"
                dataSource={data.pending_docs}
                renderItem={(p) => (
                  <List.Item actions={[<Tag key="m">{p.module}</Tag>]}>
                    <List.Item.Meta
                      title={<Text style={{ fontSize: 13 }}>{p.title}</Text>}
                      description={
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          Since {new Date(p.created_at).toLocaleDateString()}
                        </Text>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card size="small" bordered={false} title="Attendance Today">
            <Row gutter={16}>
              <Col span={8}>
                <Text type="secondary" style={{ fontSize: 12 }}>Present</Text>
                <div style={{ fontSize: 24, fontWeight: 700, color: BRAND.primary }}>
                  {data.attendance_today.present}
                </div>
              </Col>
              <Col span={8}>
                <Text type="secondary" style={{ fontSize: 12 }}>Late</Text>
                <div style={{ fontSize: 24, fontWeight: 700, color: "#f59e0b" }}>
                  {data.attendance_today.late}
                </div>
              </Col>
              <Col span={8}>
                <Text type="secondary" style={{ fontSize: 12 }}>Absent</Text>
                <div style={{ fontSize: 24, fontWeight: 700, color: "#ef4444" }}>
                  {data.attendance_today.absent}
                </div>
              </Col>
            </Row>
            {data.attendance_today.late_names.length > 0 && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                Late: {data.attendance_today.late_names.join(", ")}
              </Text>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" bordered={false} title="My Calendar">
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
                      <span style={{ width: 8, height: 8, borderRadius: 4, background: BRAND.primary, flexShrink: 0 }} />
                      <Text style={{ fontSize: 13 }}>{m.title}</Text>
                    </Flex>
                  ))}
                </div>
              ))
            )}
          </Card>
        </Col>

        <Col xs={24}>
          <Card
            size="small"
            bordered={false}
            title={
              <Flex align="center" gap={6}>
                <BugOutlined style={{ color: "#ef7c3c" }} />
                Escalations{data.inbox_count > 0 ? ` (${data.inbox_count})` : ""}
              </Flex>
            }
          >
            {data.inbox_count === 0 ? (
              <Text type="secondary" style={{ fontSize: 12 }}>Nothing waiting on you. 🎉</Text>
            ) : (
              <Text style={{ fontSize: 13 }}>
                {data.inbox_count} request{data.inbox_count === 1 ? "" : "s"} pending your approval —
                <a onClick={() => navigate("/approvals")} style={{ marginLeft: 4 }}>view Approvals</a>
              </Text>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
