import { useEffect, useState } from "react";
import { Alert, Card, Col, Flex, Row, Spin, Typography } from "antd";
import {
  ClockCircleOutlined,
  DashboardOutlined,
  DollarOutlined,
  RiseOutlined,
  RocketOutlined,
  TeamOutlined,
  ThunderboltOutlined,
  UserSwitchOutlined,
  VideoCameraOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, ApiError, type CentralPayload } from "../../lib/api";
import PeriodFilter, {
  periodToParams,
  type SuccessPeriodValue,
} from "../../components/success/PeriodFilter";
import HeroKpiCard from "../../components/success/HeroKpiCard";
import MiniStatCard from "../../components/success/MiniStatCard";
import LabeledDonut from "../../components/success/LabeledDonut";
import TimelineTracker from "../../components/success/TimelineTracker";

const { Text } = Typography;

const MINI_ICONS = [
  <RocketOutlined key="arr" />,
  <UserSwitchOutlined key="cust" />,
  <VideoCameraOutlined key="demo" />,
  <TeamOutlined key="hc" />,
  <WarningOutlined key="abs" />,
  <ClockCircleOutlined key="tard" />,
];

export default function CentralTab() {
  const [period, setPeriod] = useState<SuccessPeriodValue>({ mode: "current" });
  const [data, setData] = useState<CentralPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .successCentral(periodToParams(period))
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, [period.mode, period.month, period.from, period.to]);

  async function refresh() {
    try {
      setData(await api.successCentral(periodToParams(period)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }

  if (error)
    return (
      <Alert type="error" showIcon message="Cannot load Central Dashboard" description={error} />
    );
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const [productivity, efficiency, netCashFlow, revenueGrowth] = data.cards;

  return (
    <Flex vertical gap={20}>
      <PeriodFilter
        period={period}
        onChange={setPeriod}
        lastUpdated={data.last_updated}
        onRefresh={refresh}
        dailyCustomRange
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <HeroKpiCard card={productivity} icon={<ClockCircleOutlined />} linkLabel="Project Wise" />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <HeroKpiCard card={efficiency} icon={<DashboardOutlined />} linkLabel="Project Wise" />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <HeroKpiCard card={netCashFlow} icon={<DollarOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <HeroKpiCard card={revenueGrowth} icon={<RiseOutlined />} />
        </Col>
      </Row>

      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} xl={12}>
          <Card title="Website Visitors & Interactions" size="small" bordered={false} className="h-full">
            <div className="w-full h-[220px]">
              <ResponsiveContainer>
                <AreaChart data={data.charts.visitors.points} margin={{ left: 4, right: 8, top: 8 }}>
                  <defs>
                    <linearGradient id="visitors-grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#4f46e5" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#4f46e5" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="interactions-grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0d9488" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#0d9488" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#dfeee6" />
                  <XAxis dataKey="t" tick={{ fontSize: 10 }} minTickGap={24} />
                  <YAxis tick={{ fontSize: 10 }} width={44} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Area
                    type="monotone"
                    dataKey="visitors"
                    name="Visitors"
                    stroke="#4f46e5"
                    strokeWidth={2}
                    fill="url(#visitors-grad)"
                  />
                  <Area
                    type="monotone"
                    dataKey="interactions"
                    name="Interactions"
                    stroke="#0d9488"
                    strokeWidth={2}
                    fill="url(#interactions-grad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <Row gutter={12} className="mt-2">
              <Col span={8}>
                <Text type="secondary" className="text-xs block">Total Visitors</Text>
                <div className="font-semibold">
                  {data.charts.visitors.footer.total_visitors.toLocaleString()}
                </div>
              </Col>
              <Col span={8}>
                <Text type="secondary" className="text-xs block">Total Interactions</Text>
                <div className="font-semibold">
                  {data.charts.visitors.footer.total_interactions.toLocaleString()}
                </div>
              </Col>
              <Col span={8}>
                <Text type="secondary" className="text-xs block">Engagement Rate</Text>
                <div className="font-semibold">{data.charts.visitors.footer.engagement_rate}%</div>
              </Col>
            </Row>
          </Card>
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <LabeledDonut
            title="Progress Tracker"
            slices={data.charts.progress.slices}
            centerLabel="Overall Progress"
            centerValue={
              data.charts.progress.overall_pct != null
                ? `${data.charts.progress.overall_pct}%`
                : undefined
            }
          />
        </Col>
        <Col xs={24} sm={12} xl={6}>
          <TimelineTracker items={data.tables.timeline} />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        {data.tables.mini_cards.map((card, i) => (
          <Col key={card.id} xs={12} md={8} xl={4}>
            <MiniStatCard card={card} icon={MINI_ICONS[i] ?? <ThunderboltOutlined />} />
          </Col>
        ))}
      </Row>
    </Flex>
  );
}
