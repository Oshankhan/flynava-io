import { useEffect, useState } from "react";
import {
  Alert,
  Card,
  Col,
  Descriptions,
  Flex,
  Progress,
  Row,
  Select,
  Spin,
  Statistic,
  Steps,
  Table,
  Tag,
} from "antd";
import dayjs from "dayjs";
import {
  api,
  ApiError,
  type ManagementProjectOption,
  type ManagementReportPayload,
} from "../../lib/api";

const RAG_COLOR: Record<string, string> = {
  green: "success",
  amber: "warning",
  red: "error",
  grey: "default",
};
const STAGE_STATUS: Record<string, "finish" | "process" | "wait"> = {
  done: "finish",
  active: "process",
  pending: "wait",
};
const INVOICE_STATUS_COLOR: Record<string, string> = {
  paid: "success",
  pending: "warning",
  overdue: "error",
};

export default function ReportTab() {
  const [projects, setProjects] = useState<ManagementProjectOption[]>([]);
  const [projectId, setProjectId] = useState<string | undefined>(undefined);
  const [data, setData] = useState<ManagementReportPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    api
      .managementProjects()
      .then((rows) => {
        if (!alive) return;
        setProjects(rows);
        setProjectId((prev) => prev ?? rows[0]?.project_id);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (!projectId) return;
    let alive = true;
    setError(null);
    api
      .managementReport(projectId)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, [projectId]);

  if (!projectId || projects.length === 0)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  // project_invoices are always USD-denominated (see seed.py) — format the
  // billing summary with the currency the rows actually carry, not INR.
  const currency = data?.invoices.rows[0]?.currency ?? "USD";

  return (
    <Flex vertical gap={20}>
      <Select
        className="w-full sm:w-[280px]"
        value={projectId}
        onChange={setProjectId}
        options={projects.map((p) => ({ value: p.project_id, label: p.name }))}
      />

      {error && <Alert type="error" showIcon message="Cannot load Project Report" description={error} />}
      {!error && !data && (
        <Flex align="center" justify="center" className="min-h-[240px]">
          <Spin size="large" />
        </Flex>
      )}

      {data && (
        <>
          <Card size="small" bordered={false}>
            <Flex justify="space-between" align="start" wrap gap={16}>
              <div>
                <Flex align="center" gap={10}>
                  <span className="text-lg font-bold text-io-900">{data.project.name}</span>
                  <Tag color={RAG_COLOR[data.project.rag]} className="m-0 capitalize">
                    {data.project.status}
                  </Tag>
                </Flex>
                <Descriptions size="small" column={2} className="mt-2">
                  <Descriptions.Item label="Client">{data.project.client ?? "—"}</Descriptions.Item>
                  <Descriptions.Item label="Engagement">{data.project.engagement ?? "—"}</Descriptions.Item>
                  <Descriptions.Item label="Priority">{data.project.priority ?? "—"}</Descriptions.Item>
                  <Descriptions.Item label="Project Manager">
                    {data.project.project_manager?.name ?? "—"}
                  </Descriptions.Item>
                  <Descriptions.Item label="Start Date">
                    {data.project.start_date ? dayjs(data.project.start_date).format("DD MMM YYYY") : "—"}
                  </Descriptions.Item>
                  <Descriptions.Item label="Due Date">
                    {data.project.due_date ? dayjs(data.project.due_date).format("DD MMM YYYY") : "—"}
                  </Descriptions.Item>
                  <Descriptions.Item label="Members">{data.project.member_count}</Descriptions.Item>
                </Descriptions>
              </div>
              <div className="w-full sm:w-[260px]">
                <Flex justify="space-between" className="mb-1">
                  <span className="text-xs text-gray-500">Progress</span>
                  <span className="text-xs text-gray-500">
                    {data.project.progress}%{data.project.expected_progress != null &&
                      ` / expected ${data.project.expected_progress}%`}
                  </span>
                </Flex>
                <Progress percent={data.project.progress} strokeColor="#157f52" />
              </div>
            </Flex>
          </Card>

          <Card title="Stage Pipeline" size="small" bordered={false}>
            <Steps
              size="small"
              items={data.stages?.map((s) => ({
                title: s.name,
                description: `${s.progress}%`,
                status: STAGE_STATUS[s.status],
              }))}
            />
          </Card>

          <Row gutter={[16, 16]}>
            <Col xs={12} sm={8} xl={4}>
              <Card size="small" bordered={false} className="h-full">
                <Statistic title="Total Tasks" value={data.stats.tasks_total} />
              </Card>
            </Col>
            <Col xs={12} sm={8} xl={4}>
              <Card size="small" bordered={false} className="h-full">
                <Statistic title="Tasks Done" value={data.stats.tasks_done} />
              </Card>
            </Col>
            <Col xs={12} sm={8} xl={4}>
              <Card size="small" bordered={false} className="h-full">
                <Statistic title="Task Completion" value={data.stats.task_completion_pct ?? 0} suffix="%" />
              </Card>
            </Col>
            <Col xs={12} sm={8} xl={4}>
              <Card size="small" bordered={false} className="h-full">
                <Statistic title="Total Bugs" value={data.stats.bugs_total} />
              </Card>
            </Col>
            <Col xs={12} sm={8} xl={4}>
              <Card size="small" bordered={false} className="h-full">
                <Statistic title="Open Bugs" value={data.stats.bugs_open} valueStyle={{ color: data.stats.bugs_open > 0 ? "#cf1322" : undefined }} />
              </Card>
            </Col>
            <Col xs={12} sm={8} xl={4}>
              <Card size="small" bordered={false} className="h-full">
                <Statistic title="Bug Resolution" value={data.stats.bug_resolution_pct ?? 0} suffix="%" />
              </Card>
            </Col>
          </Row>

          <Card
            title="Billing"
            size="small"
            bordered={false}
            extra={
              <Flex gap={16}>
                <span className="text-xs">
                  Paid: <strong className="text-io-600">{currency} {data.invoices.paid.toLocaleString()}</strong>
                </span>
                <span className="text-xs">
                  Pending: <strong className="text-amber-600">{currency} {data.invoices.pending.toLocaleString()}</strong>
                </span>
                <span className="text-xs">
                  Overdue: <strong className="text-red-600">{currency} {data.invoices.overdue.toLocaleString()}</strong>
                </span>
              </Flex>
            }
          >
            <Table
              size="small"
              pagination={false}
              rowKey="invoice_id"
              scroll={{ x: true }}
              dataSource={data.invoices.rows}
              columns={[
                { title: "Invoice #", dataIndex: "number", key: "number" },
                { title: "Date", dataIndex: "date", key: "date", render: (v: string) => dayjs(v).format("DD MMM YYYY") },
                {
                  title: "Due Date", dataIndex: "due_date", key: "due_date",
                  render: (v: string | null) => (v ? dayjs(v).format("DD MMM YYYY") : "—"),
                },
                {
                  title: "Amount", dataIndex: "amount", key: "amount",
                  render: (v: number, row) => `${row.currency} ${v.toLocaleString()}`,
                },
                {
                  title: "Status", dataIndex: "status", key: "status",
                  render: (v: string) => <Tag color={INVOICE_STATUS_COLOR[v] ?? "default"}>{v}</Tag>,
                },
              ]}
            />
            {data.invoices.rows.length === 0 && (
              <div className="text-center text-xs text-gray-400 py-4">No invoices for this project.</div>
            )}
          </Card>
        </>
      )}
    </Flex>
  );
}
