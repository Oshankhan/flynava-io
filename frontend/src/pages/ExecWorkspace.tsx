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
      <Flex justify="center" className="pt-20">
        <Spin />
      </Flex>
    );

  const meetingDays: Record<string, typeof data.meetings> = {};
  data.meetings.forEach((m) => {
    const k = dayLabel(m.start);
    meetingDays[k] = meetingDays[k] ?? [];
    meetingDays[k].push(m);
  });

  const seriesById = Object.fromEntries((data.series ?? []).map((s) => [s.kpi_id, s]));

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
      <Flex justify="space-between" align="center" wrap gap={12} className="mb-4">
        <div>
          <Title level={3} className="m-0">
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
            <Text type="secondary" className="text-xs">
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
              <KpiCard kpi={k} series={seriesById[k.kpi_id]} />
            </Col>
          ))}
        </Row>
      )}

      {/* Departments — the drill-down entry point */}
      <Card
        size="small"
        bordered={false}
        className="mt-4"
        title={
          <Flex align="center" gap={6}>
            <BankOutlined className="text-io-600" /> Departments
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
                className={`h-full ${d.head ? "cursor-pointer" : "cursor-default"}`}
              >
                <Flex align="center" gap={10} className="mb-2">
                  <Avatar className="bg-io-600">
                    {d.head?.name?.[0] ?? "?"}
                  </Avatar>
                  <div>
                    <Text strong className="text-[13px]">{d.head?.name ?? "Unassigned"}</Text>
                    <div>
                      <Text type="secondary" className="text-[11px]">
                        {d.head?.designation ?? d.name}
                      </Text>
                    </div>
                  </div>
                </Flex>
                <Text type="secondary" className="text-[11px]">
                  {d.teams_count} team{d.teams_count === 1 ? "" : "s"} · {d.member_count} people
                </Text>
                <Progress
                  percent={deptOpenPct(d)}
                  size="small"
                  strokeColor={loadColor(deptOpenPct(d))}
                  className="mt-1.5"
                  format={(p) => `${p}% open`}
                />
                <Flex gap={6} wrap className="mt-1.5">
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

      <Row gutter={[16, 16]} className="mt-4">
        <Col xs={24} lg={14}>
          {data.projects.length > 0 ? (
            <ProjectHealth projects={data.projects} />
          ) : (
            <Card size="small" bordered={false} title="Project Health" className="h-full">
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No active projects" />
            </Card>
          )}
        </Col>
        <Col xs={24} lg={10}>
          {data.bug_breakdown && data.bug_breakdown.length > 0 ? (
            <StatusDonut title="Bugs by Status" data={data.bug_breakdown} centerLabel="Total Bugs" />
          ) : (
            <Card size="small" bordered={false} title="Bugs by Status" className="h-full">
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
                <ExperimentOutlined className="text-[#7cc8e0]" />
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
                scroll={{ x: true }}
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
                <FileTextOutlined className="text-io-600" /> Pending Product Documents
              </Flex>
            }
          >
            {data.pending_docs.length === 0 ? (
              <Text type="secondary" className="text-xs">Nothing pending review.</Text>
            ) : (
              <List
                size="small"
                dataSource={data.pending_docs}
                renderItem={(p) => (
                  <List.Item actions={[<Tag key="m">{p.module}</Tag>]}>
                    <List.Item.Meta
                      title={<Text className="text-[13px]">{p.title}</Text>}
                      description={
                        <Text type="secondary" className="text-[11px]">
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
                <Text type="secondary" className="text-xs">Present</Text>
                <div className="text-2xl font-bold text-io-600">
                  {data.attendance_today.present}
                </div>
              </Col>
              <Col span={8}>
                <Text type="secondary" className="text-xs">Late</Text>
                <div className="text-2xl font-bold text-amber-500">
                  {data.attendance_today.late}
                </div>
              </Col>
              <Col span={8}>
                <Text type="secondary" className="text-xs">Absent</Text>
                <div className="text-2xl font-bold text-red-500">
                  {data.attendance_today.absent}
                </div>
              </Col>
            </Row>
            {data.attendance_today.late_names.length > 0 && (
              <Text type="secondary" className="text-xs">
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

        <Col xs={24}>
          <Card
            size="small"
            bordered={false}
            title={
              <Flex align="center" gap={6}>
                <BugOutlined className="text-[#ef7c3c]" />
                Escalations{data.inbox_count > 0 ? ` (${data.inbox_count})` : ""}
              </Flex>
            }
          >
            {data.inbox_count === 0 ? (
              <Text type="secondary" className="text-xs">Nothing waiting on you. 🎉</Text>
            ) : (
              <Text className="text-[13px]">
                {data.inbox_count} request{data.inbox_count === 1 ? "" : "s"} pending your approval —
                <a onClick={() => navigate("/approvals")} className="ml-1">view Approvals</a>
              </Text>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
