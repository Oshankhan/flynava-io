import { useEffect, useState } from "react";
import { Alert, Card, Col, Flex, Row, Spin, Table } from "antd";
import { TeamOutlined, UserAddOutlined, UserDeleteOutlined, PercentageOutlined } from "@ant-design/icons";
import { api, ApiError, type ForecasterWorkforcePayload } from "../../lib/api";
import PeriodFilter, {
  periodToParams,
  type SuccessPeriodValue,
} from "../../components/success/PeriodFilter";
import MiniStatCard from "../../components/success/MiniStatCard";
import SparkCell from "../../components/success/SparkCell";
import ActualForecastChart from "../../components/forecaster/ActualForecastChart";
import GroupedBarChart from "../../components/forecaster/GroupedBarChart";

export default function WorkforceTab() {
  const [period, setPeriod] = useState<SuccessPeriodValue>({ mode: "current" });
  const [data, setData] = useState<ForecasterWorkforcePayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .forecasterWorkforce(periodToParams(period).month)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, [period.mode, period.month, period.from, period.to]);

  async function refresh() {
    try {
      setData(await api.forecasterWorkforce(periodToParams(period).month));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }

  if (error)
    return <Alert type="error" showIcon message="Cannot load Workforce" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const [headcount, joiners, resigned, conversion] = data.cards;

  return (
    <Flex vertical gap={20}>
      <PeriodFilter period={period} onChange={setPeriod} lastUpdated={data.last_updated} onRefresh={refresh} />

      <Row gutter={[16, 16]}>
        <Col xs={12} md={6}>
          <MiniStatCard card={headcount} icon={<TeamOutlined />} />
        </Col>
        <Col xs={12} md={6}>
          <MiniStatCard card={joiners} icon={<UserAddOutlined />} />
        </Col>
        <Col xs={12} md={6}>
          <MiniStatCard card={resigned} icon={<UserDeleteOutlined />} />
        </Col>
        <Col xs={12} md={6}>
          <MiniStatCard card={conversion} icon={<PercentageOutlined />} />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <ActualForecastChart
            title="Headcount Forecast"
            actual={data.charts.headcount_forecast.actual}
            forecast={data.charts.headcount_forecast.forecast}
          />
        </Col>
        <Col xs={24} xl={12}>
          <Card title="Joiners vs Resigned" size="small" bordered={false} className="h-full">
            <GroupedBarChart
              series={[
                { key: "joiners", name: "Joiners", color: "#157f52",
                 points: data.charts.joiners_vs_resigned.joiners },
                { key: "resigned", name: "Resigned", color: "#cf1322",
                 points: data.charts.joiners_vs_resigned.resigned },
              ]}
            />
          </Card>
        </Col>
      </Row>

      <Card title="Department Headcount" size="small" bordered={false}>
        <Table
          size="small"
          pagination={false}
          rowKey="dept"
          scroll={{ x: true }}
          dataSource={data.tables.departments}
          columns={[
            { title: "Department", dataIndex: "dept", key: "dept" },
            { title: "Headcount", dataIndex: "headcount", key: "headcount" },
            { title: "Performance Score", dataIndex: "performance", key: "performance" },
            {
              title: "Attrition Rate", dataIndex: "attrition", key: "attrition",
              render: (v: number) => `${v}%`,
            },
            {
              title: "Trend", dataIndex: "trend", key: "trend",
              render: (trend: number[]) => <SparkCell points={trend} />,
            },
          ]}
        />
      </Card>
    </Flex>
  );
}
