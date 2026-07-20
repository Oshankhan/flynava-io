import { useEffect, useState } from "react";
import { Alert, Card, Col, Flex, Row, Spin, Table } from "antd";
import { AimOutlined, DollarOutlined, PercentageOutlined } from "@ant-design/icons";
import { api, ApiError, type ForecasterRevenuePayload } from "../../lib/api";
import PeriodFilter, {
  periodToParams,
  type SuccessPeriodValue,
} from "../../components/success/PeriodFilter";
import HeroKpiCard from "../../components/success/HeroKpiCard";
import LabeledDonut from "../../components/success/LabeledDonut";
import ActualForecastChart from "../../components/forecaster/ActualForecastChart";
import { formatINR } from "../../lib/format";

export default function RevenueTab() {
  const [period, setPeriod] = useState<SuccessPeriodValue>({ mode: "current" });
  const [data, setData] = useState<ForecasterRevenuePayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .forecasterRevenue(periodToParams(period).month)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, [period.mode, period.month, period.from, period.to]);

  async function refresh() {
    try {
      setData(await api.forecasterRevenue(periodToParams(period).month));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }

  if (error)
    return <Alert type="error" showIcon message="Cannot load Revenue" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const [revenue, forecastRevenue, accuracy] = data.cards;

  return (
    <Flex vertical gap={20}>
      <PeriodFilter period={period} onChange={setPeriod} lastUpdated={data.last_updated} onRefresh={refresh} />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={8}>
          <HeroKpiCard card={revenue} icon={<DollarOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={8}>
          <HeroKpiCard card={forecastRevenue} icon={<AimOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={8}>
          <HeroKpiCard card={accuracy} icon={<PercentageOutlined />} />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <ActualForecastChart
            title="Revenue: Actual vs Forecast"
            actual={data.charts.revenue_trend.actual}
            forecast={data.charts.revenue_trend.forecast}
          />
        </Col>
        <Col xs={24} xl={8}>
          <LabeledDonut
            title="Revenue by Segment"
            slices={data.tables.revenue_segments.map((s) => ({ label: s.segment, value: s.amount }))}
            centerLabel="Total Revenue"
            formatValue={formatINR}
          />
        </Col>
      </Row>

      <Card title="Actual vs Forecast (Monthly)" size="small" bordered={false}>
        <Table
          size="small"
          pagination={false}
          rowKey="month"
          scroll={{ x: true }}
          dataSource={data.tables.actual_vs_forecast}
          columns={[
            { title: "Month", dataIndex: "month", key: "month" },
            {
              title: "Actual", dataIndex: "actual", key: "actual",
              render: (v: number | null) => (v == null ? "—" : formatINR(v)),
            },
            {
              title: "Forecast", dataIndex: "forecast", key: "forecast",
              render: (v: number | null) => (v == null ? "—" : formatINR(v)),
            },
            {
              title: "Variance", dataIndex: "variance_pct", key: "variance_pct",
              render: (v: number | null) =>
                v == null ? "—" : (
                  <span className={v >= 0 ? "text-io-600" : "text-red-600"}>
                    {v > 0 ? "+" : ""}{v}%
                  </span>
                ),
            },
          ]}
        />
      </Card>
    </Flex>
  );
}
