import { useEffect, useState } from "react";
import { Alert, Card, Col, Flex, Row, Spin, Table, Typography } from "antd";
import { AimOutlined, TagsOutlined, WalletOutlined } from "@ant-design/icons";
import { api, ApiError, type ForecasterCard, type ForecasterCostsPayload } from "../../lib/api";
import PeriodFilter, {
  periodToParams,
  type SuccessPeriodValue,
} from "../../components/success/PeriodFilter";
import HeroKpiCard from "../../components/success/HeroKpiCard";
import LabeledDonut from "../../components/success/LabeledDonut";
import ActualForecastChart from "../../components/forecaster/ActualForecastChart";
import { formatINR } from "../../lib/format";

const { Text } = Typography;

function LargestCategoryCard({ card }: { card: ForecasterCard }) {
  return (
    <Card size="small" bordered={false} className="h-full shadow-sm">
      <Flex vertical gap={6}>
        <span className="flex items-center justify-center w-9 h-9 rounded-full text-base shrink-0 bg-purple-500/15 text-purple-600">
          <TagsOutlined />
        </span>
        <Text type="secondary" className="text-xs font-medium uppercase tracking-wide">
          {card.label}
        </Text>
        <span className="text-2xl font-bold text-io-900 leading-none">
          {formatINR(card.value)}
        </span>
        {card.category && <Text type="secondary" className="text-xs">{card.category}</Text>}
      </Flex>
    </Card>
  );
}

export default function CostsTab() {
  const [period, setPeriod] = useState<SuccessPeriodValue>({ mode: "current" });
  const [data, setData] = useState<ForecasterCostsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .forecasterCosts(periodToParams(period).month)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, [period.mode, period.month, period.from, period.to]);

  async function refresh() {
    try {
      setData(await api.forecasterCosts(periodToParams(period).month));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }

  if (error)
    return <Alert type="error" showIcon message="Cannot load Costs" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const [totalExpenses, largestCategory, forecastExpenses] = data.cards;

  return (
    <Flex vertical gap={20}>
      <PeriodFilter period={period} onChange={setPeriod} lastUpdated={data.last_updated} onRefresh={refresh} />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={8}>
          <HeroKpiCard card={totalExpenses} icon={<WalletOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={8}>
          <LargestCategoryCard card={largestCategory} />
        </Col>
        <Col xs={24} sm={12} xl={8}>
          <HeroKpiCard card={forecastExpenses} icon={<AimOutlined />} />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={16}>
          <ActualForecastChart
            title="Expenses: Actual vs Forecast"
            actual={data.charts.expense_trend.actual}
            forecast={data.charts.expense_trend.forecast}
          />
        </Col>
        <Col xs={24} xl={8}>
          <LabeledDonut
            title="Expense Breakdown"
            slices={data.tables.categories.map((c) => ({ label: c.category, value: c.amount }))}
            centerLabel="Total Expenses"
            formatValue={formatINR}
          />
        </Col>
      </Row>

      <Card title="Expense Categories" size="small" bordered={false}>
        <Table
          size="small"
          pagination={false}
          rowKey="category"
          scroll={{ x: true }}
          dataSource={data.tables.categories}
          columns={[
            { title: "Category", dataIndex: "category", key: "category" },
            {
              title: "Amount", dataIndex: "amount", key: "amount",
              render: (v: number) => formatINR(v),
            },
            {
              title: "Previous", dataIndex: "previous", key: "previous",
              render: (v: number | null) => (v == null ? "—" : formatINR(v)),
            },
            {
              title: "Change", dataIndex: "change_pct", key: "change_pct",
              render: (v: number | null) =>
                v == null ? "—" : (
                  <span className={v <= 0 ? "text-io-600" : "text-red-600"}>
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
