import { useEffect, useState } from "react";
import { Alert, Card, Col, Flex, Progress, Row, Spin, Table, Tag, Typography } from "antd";
import {
  CheckSquareOutlined,
  ClockCircleOutlined,
  FieldTimeOutlined,
  UnorderedListOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { api, ApiError, type OpsPayload } from "../../lib/api";
import PeriodFilter, {
  periodToParams,
  type SuccessPeriodValue,
} from "../../components/success/PeriodFilter";
import MiniStatCard from "../../components/success/MiniStatCard";
import LabeledDonut from "../../components/success/LabeledDonut";
import TrendMini from "../../components/success/TrendMini";

const { Text } = Typography;

const PROCESS_STATUS_COLOR: Record<string, string> = {
  Good: "success",
  Attention: "warning",
};

export default function OperationsTab() {
  const [period, setPeriod] = useState<SuccessPeriodValue>({ mode: "current" });
  const [data, setData] = useState<OpsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .successOperations(periodToParams(period).month)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, [period.mode, period.month, period.from, period.to]);

  async function refresh() {
    try {
      setData(await api.successOperations(periodToParams(period).month));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }

  if (error)
    return <Alert type="error" showIcon message="Cannot load Operational Insights" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const [tasksTotal, tasksCompleted, onTimePct, pending, overdue] = data.cards;

  return (
    <Flex vertical gap={20}>
      <PeriodFilter period={period} onChange={setPeriod} lastUpdated={data.last_updated} onRefresh={refresh} />

      <Row gutter={[16, 16]}>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={tasksTotal} icon={<UnorderedListOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={tasksCompleted} icon={<CheckSquareOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={onTimePct} icon={<ClockCircleOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={pending} icon={<FieldTimeOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={4}>
          <MiniStatCard card={overdue} icon={<WarningOutlined />} />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <LabeledDonut title="Tasks by Status" slices={data.charts.by_status.slices} centerLabel="Total Tasks" />
        </Col>
        <Col xs={24} xl={12}>
          <Card title="Tasks Trend" size="small" bordered={false} className="h-full">
            <div className="w-full h-[260px]">
              <TrendMini points={data.charts.tasks_trend.points} color="#157f52" />
            </div>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <LabeledDonut title="Tasks by Priority" slices={data.charts.by_priority.slices} centerLabel="Total Tasks" />
        </Col>
        <Col xs={24} xl={12}>
          <Card title="Top Operational Processes" size="small" bordered={false} className="h-full">
            <Table
              size="small"
              pagination={false}
              rowKey="process"
              scroll={{ x: true }}
              dataSource={data.tables.top_processes}
              columns={[
                { title: "Process", dataIndex: "process", key: "process" },
                { title: "Total Tasks", dataIndex: "total_tasks", key: "total_tasks" },
                { title: "Completed", dataIndex: "completed", key: "completed" },
                {
                  title: "On-time %",
                  dataIndex: "on_time_pct",
                  key: "on_time_pct",
                  render: (v: number) => `${v}%`,
                },
                { title: "Overdue", dataIndex: "overdue", key: "overdue" },
                {
                  title: "Avg. Completion",
                  dataIndex: "avg_completion_hours",
                  key: "avg_completion_hours",
                  render: (v: number) => `${v} hrs`,
                },
                {
                  title: "Status",
                  dataIndex: "status",
                  key: "status",
                  render: (v: string) => <Tag color={PROCESS_STATUS_COLOR[v] ?? "default"}>{v}</Tag>,
                },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Card title="Operational Efficiency Overview" size="small" bordered={false}>
        <Row gutter={[16, 16]}>
          {data.tables.efficiency.map((row) => (
            <Col key={row.metric} xs={24} sm={12} xl={6}>
              <Flex justify="space-between" className="mb-1">
                <Text className="text-sm font-medium">{row.metric}</Text>
                <Text className="text-sm font-semibold">{row.value != null ? `${row.value}%` : "—"}</Text>
              </Flex>
              <Progress percent={row.value ?? 0} showInfo={false} strokeColor="#157f52" />
              {row.delta_pct != null && (
                <Text type="secondary" className="text-[11px]">
                  {row.delta_pct >= 0 ? "+" : ""}
                  {row.delta_pct}% vs last month
                </Text>
              )}
            </Col>
          ))}
        </Row>
      </Card>
    </Flex>
  );
}
