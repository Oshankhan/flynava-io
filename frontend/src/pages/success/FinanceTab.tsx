import { useEffect, useState } from "react";
import { Alert, Card, Col, Flex, Row, Segmented, Spin, Table } from "antd";
import { DollarOutlined, PieChartOutlined, RiseOutlined } from "@ant-design/icons";
import { api, ApiError, type FinancePayload } from "../../lib/api";
import PeriodFilter, {
  periodToParams,
  type SuccessPeriodValue,
} from "../../components/success/PeriodFilter";
import HeroKpiCard from "../../components/success/HeroKpiCard";
import LabeledDonut from "../../components/success/LabeledDonut";
import TrendMini from "../../components/success/TrendMini";
import { formatINR } from "../../lib/format";

// Every summary row is a rupee amount except Operating Margin, which is a
// percentage — the backend doesn't tag a unit per row (it's the only ratio
// mixed into an otherwise all-currency table), so this is matched by name.
const PCT_METRICS = new Set(["Operating Margin"]);

function formatSummaryValue(metric: string, value: number | null): string {
  if (value == null) return "—";
  return PCT_METRICS.has(metric) ? `${value}%` : formatINR(value);
}

function ChangeCell({
  metric,
  current,
  previous,
}: {
  metric: string;
  current: number | null;
  previous: number | null;
}) {
  if (current == null || previous == null) return <span>—</span>;
  const diff = current - previous;
  const pct = previous ? Math.round((diff / Math.abs(previous)) * 1000) / 10 : null;
  const isPct = PCT_METRICS.has(metric);
  return (
    <span className={diff >= 0 ? "text-io-600" : "text-red-600"}>
      {diff >= 0 ? "+" : ""}
      {isPct ? `${diff.toFixed(1)}%` : formatINR(diff)}{" "}
      {!isPct && pct != null && `(${diff >= 0 ? "+" : ""}${pct}%)`}
    </span>
  );
}

export default function FinanceTab() {
  const [period, setPeriod] = useState<SuccessPeriodValue>({ mode: "current" });
  const [granularity, setGranularity] = useState<"monthly" | "yearly">("monthly");
  const [data, setData] = useState<FinancePayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    setLoading(true);
    api
      .successFinance(periodToParams(period).month, granularity)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [period.mode, period.month, period.from, period.to, granularity]);

  async function refresh() {
    try {
      setData(await api.successFinance(periodToParams(period).month, granularity));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }

  if (error)
    return <Alert type="error" showIcon message="Cannot load Finance Performance" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const [netCashFlow, revenueGrowth, currentRatio] = data.cards;

  return (
    <Flex vertical gap={20}>
      <Flex justify="flex-end">
        <Segmented
          disabled={loading}
          value={granularity}
          onChange={(v) => setGranularity(v as "monthly" | "yearly")}
          options={[
            { label: "Finance (Yearly)", value: "yearly" },
            { label: "Finance (Monthly)", value: "monthly" },
          ]}
        />
      </Flex>

      <PeriodFilter period={period} onChange={setPeriod} lastUpdated={data.last_updated} onRefresh={refresh} />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={8}>
          <HeroKpiCard card={netCashFlow} icon={<DollarOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={8}>
          <HeroKpiCard card={revenueGrowth} icon={<RiseOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={8}>
          <HeroKpiCard card={currentRatio} icon={<PieChartOutlined />} />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="Net Cash Flow Trend" size="small" bordered={false} className="h-full">
            <div className="w-full h-[220px]">
              <TrendMini points={data.charts.net_cash_flow_trend.points} color="#157f52" />
            </div>
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="Revenue Growth Rate Trend" size="small" bordered={false} className="h-full">
            <div className="w-full h-[220px]">
              <TrendMini points={data.charts.revenue_growth_trend.points} color="#4f46e5" />
            </div>
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="Current Ratio Trend" size="small" bordered={false} className="h-full">
            <div className="w-full h-[220px]">
              <TrendMini points={data.charts.current_ratio_trend.points} color="#0d9488" />
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="Financial Summary" size="small" bordered={false}>
        <Table
          size="small"
          pagination={false}
          rowKey="metric"
          scroll={{ x: true }}
          dataSource={data.tables.financial_summary}
          columns={[
            { title: "Metric", dataIndex: "metric", key: "metric" },
            {
              title: "Current",
              key: "current",
              render: (_: unknown, row: FinancePayload["tables"]["financial_summary"][number]) =>
                formatSummaryValue(row.metric, row.current),
            },
            {
              title: "Previous",
              key: "previous",
              render: (_: unknown, row: FinancePayload["tables"]["financial_summary"][number]) =>
                formatSummaryValue(row.metric, row.previous),
            },
            {
              title: "Change",
              key: "change",
              render: (_: unknown, row: FinancePayload["tables"]["financial_summary"][number]) => (
                <ChangeCell metric={row.metric} current={row.current} previous={row.previous} />
              ),
            },
          ]}
        />
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <LabeledDonut
            title="Revenue by Segment"
            slices={data.tables.revenue_segments.map((s) => ({ label: s.segment, value: s.amount }))}
            centerLabel="Total Revenue"
            formatValue={formatINR}
          />
        </Col>
        <Col xs={24} xl={12}>
          <LabeledDonut
            title="Expense Breakdown"
            slices={data.tables.expense_breakdown.map((e) => ({ label: e.category, value: e.amount }))}
            centerLabel="Total Expenses"
            formatValue={formatINR}
          />
        </Col>
      </Row>
    </Flex>
  );
}
