import { useEffect, useState } from "react";
import { Alert, Card, Flex, Progress, Spin, Tag, Typography } from "antd";
import {
  BankOutlined,
  CreditCardOutlined,
  DollarOutlined,
  PercentageOutlined,
  RiseOutlined,
  TeamOutlined,
  WalletOutlined,
} from "@ant-design/icons";
import { api, ApiError, type ForecasterCard, type ForecasterOverviewPayload } from "../../lib/api";
import PeriodFilter, {
  periodToParams,
  type SuccessPeriodValue,
} from "../../components/success/PeriodFilter";
import HeroKpiCard from "../../components/success/HeroKpiCard";
import SummaryPanel from "../../components/forecaster/SummaryPanel";
import CategoryBars from "../../components/forecaster/CategoryBars";
import InsightList from "../../components/forecaster/InsightList";
import AlertList from "../../components/forecaster/AlertList";

const { Text } = Typography;

const BAND_COLOR: Record<string, string> = {
  Healthy: "#157f52",
  Watch: "#d97706",
  "At Risk": "#cf1322",
};

function HealthScoreCard({ card }: { card: ForecasterCard }) {
  const color = BAND_COLOR[card.band ?? ""] ?? "#8c8c8c";
  return (
    <Card size="small" bordered={false} className="h-full shadow-sm">
      <Flex vertical align="center" gap={6}>
        <Text type="secondary" className="text-xs font-medium uppercase tracking-wide self-start">
          {card.label}
        </Text>
        <Progress
          type="circle"
          percent={card.value ?? 0}
          size={64}
          strokeColor={color}
          format={(v) => <span className="text-base font-bold">{v}</span>}
        />
        {card.band && (
          <Tag color={color} className="m-0">
            {card.band}
          </Tag>
        )}
      </Flex>
    </Card>
  );
}

export default function OverviewTab() {
  const [period, setPeriod] = useState<SuccessPeriodValue>({ mode: "current" });
  const [data, setData] = useState<ForecasterOverviewPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .forecasterOverview(periodToParams(period).month)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, [period.mode, period.month, period.from, period.to]);

  async function refresh() {
    try {
      setData(await api.forecasterOverview(periodToParams(period).month));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }

  if (error)
    return <Alert type="error" showIcon message="Cannot load Financial Forecaster" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const [revenue, expenses, netProfit, cashBalance, employees, outstanding, accuracy, health] =
    data.cards;

  return (
    <Flex vertical gap={20}>
      <PeriodFilter period={period} onChange={setPeriod} lastUpdated={data.last_updated} onRefresh={refresh} />

      <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-4">
        <HeroKpiCard card={revenue} icon={<DollarOutlined />} />
        <HeroKpiCard card={expenses} icon={<WalletOutlined />} />
        <HeroKpiCard card={netProfit} icon={<RiseOutlined />} />
        <HeroKpiCard card={cashBalance} icon={<BankOutlined />} />
        <HeroKpiCard card={employees} icon={<TeamOutlined />} />
        <HeroKpiCard card={outstanding} icon={<CreditCardOutlined />} />
        <HeroKpiCard card={accuracy} icon={<PercentageOutlined />} />
        <HealthScoreCard card={health} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
        <SummaryPanel
          title="Revenue Summary"
          value={data.panels.revenue.this_month}
          momPct={data.panels.revenue.mom_pct}
          trend={data.panels.revenue.trend}
          link="/forecaster/revenue"
        >
          <Text type="secondary" className="text-[11px]">
            Forecast: {data.panels.revenue.forecast_this_month?.toLocaleString() ?? "—"}
            {data.panels.revenue.vs_forecast_pct != null &&
              ` (${data.panels.revenue.vs_forecast_pct > 0 ? "+" : ""}${data.panels.revenue.vs_forecast_pct}% vs actual)`}
          </Text>
        </SummaryPanel>

        <SummaryPanel
          title="Workforce Summary"
          value={data.panels.workforce.total_employees}
          unit="count"
          trend={data.panels.workforce.trend}
          link="/forecaster/workforce"
        >
          <Flex justify="space-between" className="text-[11px]">
            <Text type="secondary">New Joiners: {data.panels.workforce.new_joiners}</Text>
            <Text type="secondary">Resigned: {data.panels.workforce.resigned}</Text>
          </Flex>
          <Text type="secondary" className="text-[11px] block mt-1">
            Conversion Rate: {data.panels.workforce.conversion_rate}%
          </Text>
        </SummaryPanel>

        <SummaryPanel
          title="Cost Summary"
          value={data.panels.costs.total_expenses}
          momPct={data.panels.costs.mom_pct}
          link="/forecaster/costs"
        >
          <CategoryBars rows={data.panels.costs.top_categories} />
        </SummaryPanel>

        <SummaryPanel
          title="Cashflow Summary"
          value={data.panels.cashflow.cash_balance}
          trend={data.panels.cashflow.trend}
          link="/forecaster/cashflow"
        >
          <Text type="secondary" className="text-[11px]">
            Net Cash Flow: {data.panels.cashflow.net_cash_flow?.toLocaleString() ?? "—"}
          </Text>
        </SummaryPanel>

        <SummaryPanel title="Finance Analyzer Summary" link="/forecaster/analyzer">
          <Flex justify="space-between" className="text-[11px] mb-1">
            <Text type="secondary">Pending: {data.panels.analyzer.pending_count}</Text>
            <Text type="secondary">Success: {data.panels.analyzer.success_rate}%</Text>
          </Flex>
          <Text type="secondary" className="text-[11px] block">
            Overdue: {data.panels.analyzer.overdue_amount?.toLocaleString() ?? "—"}
          </Text>
          <Text type="secondary" className="text-[11px] block">
            Due in 7 days: {data.panels.analyzer.upcoming_due_7d?.toLocaleString() ?? "—"}
          </Text>
        </SummaryPanel>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 items-start">
        <InsightList items={data.insights} />

        <Card title={`Forecast Overview — ${data.forecast_label}`} size="small" bordered={false}>
          <div className="grid grid-cols-2 gap-3">
            {data.forecast_cards.map((card, i) => (
              <HeroKpiCard
                key={card.id}
                card={card}
                icon={[<DollarOutlined key="r" />, <WalletOutlined key="e" />,
                      <RiseOutlined key="p" />, <BankOutlined key="c" />][i]}
                deltaLabel="vs current run-rate"
              />
            ))}
          </div>
        </Card>

        <AlertList alerts={data.alerts} />
      </div>
    </Flex>
  );
}
