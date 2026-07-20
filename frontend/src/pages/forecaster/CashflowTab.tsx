import { useEffect, useState } from "react";
import { Alert, Card, Col, Flex, Row, Spin } from "antd";
import { ArrowDownOutlined, ArrowUpOutlined, BankOutlined, WalletOutlined } from "@ant-design/icons";
import { api, ApiError, type ForecasterCashflowPayload } from "../../lib/api";
import PeriodFilter, {
  periodToParams,
  type SuccessPeriodValue,
} from "../../components/success/PeriodFilter";
import HeroKpiCard from "../../components/success/HeroKpiCard";
import ActualForecastChart from "../../components/forecaster/ActualForecastChart";
import GroupedBarChart from "../../components/forecaster/GroupedBarChart";

export default function CashflowTab() {
  const [period, setPeriod] = useState<SuccessPeriodValue>({ mode: "current" });
  const [data, setData] = useState<ForecasterCashflowPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .forecasterCashflow(periodToParams(period).month)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, [period.mode, period.month, period.from, period.to]);

  async function refresh() {
    try {
      setData(await api.forecasterCashflow(periodToParams(period).month));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }

  if (error)
    return <Alert type="error" showIcon message="Cannot load Cashflow" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const [cashBalance, cashIn, cashOut, netCashFlow] = data.cards;
  const bars = data.charts.cash_in_vs_out.bars;

  return (
    <Flex vertical gap={20}>
      <PeriodFilter period={period} onChange={setPeriod} lastUpdated={data.last_updated} onRefresh={refresh} />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <HeroKpiCard card={cashBalance} icon={<BankOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <HeroKpiCard card={cashIn} icon={<ArrowUpOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <HeroKpiCard card={cashOut} icon={<ArrowDownOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <HeroKpiCard card={netCashFlow} icon={<WalletOutlined />} />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="Cash In vs Cash Out" size="small" bordered={false} className="h-full">
            <GroupedBarChart
              series={[
                { key: "cash_in", name: "Cash In", color: "#157f52",
                 points: bars.map((b) => ({ t: b.t, v: b.cash_in ?? 0 })) },
                { key: "cash_out", name: "Cash Out", color: "#cf1322",
                 points: bars.map((b) => ({ t: b.t, v: b.cash_out ?? 0 })) },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <ActualForecastChart
            title="Cash Balance Forecast"
            actual={data.charts.cash_balance_forecast.actual}
            forecast={data.charts.cash_balance_forecast.forecast}
          />
        </Col>
      </Row>
    </Flex>
  );
}
