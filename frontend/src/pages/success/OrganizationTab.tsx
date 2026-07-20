import { useEffect, useState } from "react";
import { Alert, Card, Col, Flex, Progress, Row, Spin, Table, Typography } from "antd";
import {
  ApartmentOutlined,
  CalendarOutlined,
  DollarOutlined,
  TeamOutlined,
  UserSwitchOutlined,
} from "@ant-design/icons";
import { api, ApiError, type OrgPayload } from "../../lib/api";
import PeriodFilter, {
  periodToParams,
  type SuccessPeriodValue,
} from "../../components/success/PeriodFilter";
import MiniStatCard from "../../components/success/MiniStatCard";
import LabeledDonut from "../../components/success/LabeledDonut";
import SparkCell from "../../components/success/SparkCell";
import TrendMini from "../../components/success/TrendMini";

const { Text } = Typography;

function DemographicBars({ rows }: { rows: { label: string; count: number }[] }) {
  const total = rows.reduce((s, r) => s + r.count, 0);
  return (
    <Flex vertical gap={10}>
      {rows.map((r) => {
        const pct = total ? Math.round((r.count / total) * 100) : 0;
        return (
          <div key={r.label}>
            <Flex justify="space-between" className="mb-1">
              <Text className="text-xs">{r.label}</Text>
              <Text type="secondary" className="text-xs">{pct}%</Text>
            </Flex>
            <Progress percent={pct} showInfo={false} strokeColor="#157f52" size="small" />
          </div>
        );
      })}
    </Flex>
  );
}

export default function OrganizationTab() {
  const [period, setPeriod] = useState<SuccessPeriodValue>({ mode: "current" });
  const [data, setData] = useState<OrgPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .successOrganization(periodToParams(period).month)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, [period.mode, period.month, period.from, period.to]);

  async function refresh() {
    try {
      setData(await api.successOrganization(periodToParams(period).month));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }

  if (error)
    return (
      <Alert type="error" showIcon message="Cannot load Organization Insights" description={error} />
    );
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const [headcount, activeDepts, attrition, avgTenure, payroll] = data.cards;

  const columns = [
    { title: "Department", dataIndex: "dept", key: "dept" },
    { title: "Headcount", dataIndex: "headcount", key: "headcount" },
    { title: "Performance Score", dataIndex: "performance", key: "performance" },
    {
      title: "Attrition Rate",
      dataIndex: "attrition",
      key: "attrition",
      render: (v: number) => `${v}%`,
    },
    {
      title: "Trend",
      dataIndex: "trend",
      key: "trend",
      render: (trend: number[]) => <SparkCell points={trend} />,
    },
  ];

  return (
    <Flex vertical gap={20}>
      <PeriodFilter period={period} onChange={setPeriod} lastUpdated={data.last_updated} onRefresh={refresh} />

      <Row gutter={[16, 16]}>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={headcount} icon={<TeamOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={activeDepts} icon={<ApartmentOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={attrition} icon={<UserSwitchOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={avgTenure} icon={<CalendarOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={4}>
          <MiniStatCard card={payroll} icon={<DollarOutlined />} />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="Headcount Trend" size="small" bordered={false} className="h-full">
            <div className="w-full h-[220px]">
              <TrendMini points={data.charts.headcount_trend.points} color="#157f52" />
            </div>
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <LabeledDonut title="Department Wise Headcount" slices={data.charts.dept_headcount.slices} centerLabel="Total" />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="Attrition Rate Trend" size="small" bordered={false} className="h-full">
            <div className="w-full h-[220px]">
              <TrendMini points={data.charts.attrition_trend.points} color="#d97706" />
            </div>
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title="Top Performing Departments" size="small" bordered={false} className="h-full">
            <Table
              size="small"
              pagination={false}
              rowKey="dept"
              dataSource={data.tables.top_departments}
              columns={columns}
              scroll={{ x: true }}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <LabeledDonut title="Gender Distribution" slices={data.charts.demographics.gender.map((g) => ({ label: g.label, value: g.count }))} />
        </Col>
        <Col xs={24} sm={12} xl={8}>
          <Card title="Age Distribution" size="small" bordered={false} className="h-full">
            <DemographicBars rows={data.charts.demographics.age.map((a) => ({ label: a.band, count: a.count }))} />
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={8}>
          <Card title="Education Level" size="small" bordered={false} className="h-full">
            <DemographicBars rows={data.charts.demographics.education.map((e) => ({ label: e.level, count: e.count }))} />
          </Card>
        </Col>
      </Row>
    </Flex>
  );
}
