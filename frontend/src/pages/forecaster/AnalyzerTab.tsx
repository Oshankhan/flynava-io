import { useEffect, useState } from "react";
import { Alert, Card, Col, Flex, Row, Spin, Table, Tag } from "antd";
import { ClockCircleOutlined, DollarOutlined, PercentageOutlined, WarningOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { api, ApiError, type ForecasterAnalyzerPayload } from "../../lib/api";
import PeriodFilter, {
  periodToParams,
  type SuccessPeriodValue,
} from "../../components/success/PeriodFilter";
import HeroKpiCard from "../../components/success/HeroKpiCard";
import LabeledDonut from "../../components/success/LabeledDonut";
import TrendMini from "../../components/success/TrendMini";
import { formatINR } from "../../lib/format";

const STATUS_COLOR: Record<string, string> = { pending: "warning", overdue: "error" };

export default function AnalyzerTab() {
  const [period, setPeriod] = useState<SuccessPeriodValue>({ mode: "current" });
  const [data, setData] = useState<ForecasterAnalyzerPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .forecasterAnalyzer(periodToParams(period).month)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, [period.mode, period.month, period.from, period.to]);

  async function refresh() {
    try {
      setData(await api.forecasterAnalyzer(periodToParams(period).month));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }

  if (error)
    return <Alert type="error" showIcon message="Cannot load Finance Analyzer" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const [pending, overdue, upcoming, successRate] = data.cards;

  return (
    <Flex vertical gap={20}>
      <PeriodFilter period={period} onChange={setPeriod} lastUpdated={data.last_updated} onRefresh={refresh} />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <HeroKpiCard card={pending} icon={<ClockCircleOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <HeroKpiCard card={overdue} icon={<WarningOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <HeroKpiCard card={upcoming} icon={<DollarOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <HeroKpiCard card={successRate} icon={<PercentageOutlined />} />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <LabeledDonut
            title="Payment Status"
            slices={data.charts.status_breakdown.slices}
            centerLabel="Payment Status"
            formatValue={(v) => `${v}%`}
          />
        </Col>
        <Col xs={24} xl={16}>
          <Card title="Payment Success Rate Trend" size="small" bordered={false} className="h-full">
            <div className="w-full h-[220px]">
              <TrendMini points={data.charts.success_rate_trend.points} color="#157f52" />
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="Pending & Overdue Invoices" size="small" bordered={false}>
        <Table
          size="small"
          pagination={false}
          rowKey="invoice_id"
          scroll={{ x: true }}
          dataSource={data.tables.invoices}
          columns={[
            { title: "Invoice #", dataIndex: "number", key: "number" },
            { title: "Project", dataIndex: "project", key: "project" },
            {
              title: "Date", dataIndex: "date", key: "date",
              render: (v: string) => dayjs(v).format("DD MMM YYYY"),
            },
            {
              title: "Due Date", dataIndex: "due_date", key: "due_date",
              render: (v: string) => dayjs(v).format("DD MMM YYYY"),
            },
            {
              title: "Amount", dataIndex: "amount", key: "amount",
              render: (v: number) => formatINR(v),
            },
            {
              title: "Status", dataIndex: "status", key: "status",
              render: (v: string) => <Tag color={STATUS_COLOR[v] ?? "default"}>{v}</Tag>,
            },
          ]}
        />
        {data.tables.invoices.length === 0 && (
          <div className="text-center text-xs text-gray-400 py-4">
            No pending or overdue invoices.
          </div>
        )}
      </Card>
    </Flex>
  );
}
