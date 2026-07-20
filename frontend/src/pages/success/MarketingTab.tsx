import { useEffect, useState } from "react";
import { Alert, Card, Col, Flex, Row, Spin, Table, Tag } from "antd";
import {
  DollarOutlined,
  FunnelPlotOutlined,
  PercentageOutlined,
  SoundOutlined,
  TrophyOutlined,
} from "@ant-design/icons";
import { api, ApiError, type MarketingPayload } from "../../lib/api";
import PeriodFilter, {
  periodToParams,
  type SuccessPeriodValue,
} from "../../components/success/PeriodFilter";
import MiniStatCard from "../../components/success/MiniStatCard";
import LabeledDonut from "../../components/success/LabeledDonut";
import TrendMini from "../../components/success/TrendMini";
import { formatINR } from "../../lib/format";

const CAMPAIGN_STATUS_COLOR: Record<string, string> = {
  Active: "success",
  Completed: "default",
};

export default function MarketingTab() {
  const [period, setPeriod] = useState<SuccessPeriodValue>({ mode: "current" });
  const [data, setData] = useState<MarketingPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .successMarketing(periodToParams(period).month)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, [period.mode, period.month, period.from, period.to]);

  async function refresh() {
    try {
      setData(await api.successMarketing(periodToParams(period).month));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }

  if (error)
    return <Alert type="error" showIcon message="Cannot load Marketing Insights" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const [campaigns, leads, conversion, cpl, roi] = data.cards;

  return (
    <Flex vertical gap={20}>
      <PeriodFilter period={period} onChange={setPeriod} lastUpdated={data.last_updated} onRefresh={refresh} />

      <Row gutter={[16, 16]}>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={campaigns} icon={<SoundOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={leads} icon={<FunnelPlotOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={conversion} icon={<PercentageOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={4}>
          <MiniStatCard card={cpl} icon={<DollarOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={roi} icon={<TrophyOutlined />} />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <LabeledDonut title="Leads by Source" slices={data.charts.leads_by_source.slices} centerLabel="Total Leads" />
        </Col>
        <Col xs={24} xl={12}>
          <Card title="Leads Trend" size="small" bordered={false} className="h-full">
            <div className="w-full h-[260px]">
              <TrendMini points={data.charts.leads_trend.points} color="#4f46e5" />
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="Top Performing Campaigns" size="small" bordered={false}>
        <Table
          size="small"
          pagination={false}
          rowKey="name"
          scroll={{ x: true }}
          dataSource={data.tables.top_campaigns}
          columns={[
            { title: "Campaign", dataIndex: "name", key: "name" },
            { title: "Leads", dataIndex: "leads", key: "leads" },
            {
              title: "Conversion Rate",
              dataIndex: "conv_rate",
              key: "conv_rate",
              render: (v: number) => `${v}%`,
            },
            { title: "ROI", dataIndex: "roi", key: "roi", render: (v: number) => `${v}%` },
            {
              title: "Status",
              dataIndex: "status",
              key: "status",
              render: (v: string) => <Tag color={CAMPAIGN_STATUS_COLOR[v] ?? "default"}>{v}</Tag>,
            },
          ]}
        />
      </Card>

      <Card title="Channel Performance Overview" size="small" bordered={false}>
        <div className="overflow-x-auto">
          <Table
            size="small"
            pagination={false}
            rowKey="channel"
            scroll={{ x: 900 }}
            dataSource={data.tables.channels}
            columns={[
              { title: "Channel", dataIndex: "channel", key: "channel" },
              {
                title: "Impressions",
                dataIndex: "impressions",
                key: "impressions",
                render: (v: number) => v.toLocaleString(),
              },
              {
                title: "Clicks",
                dataIndex: "clicks",
                key: "clicks",
                render: (v: number) => v.toLocaleString(),
              },
              { title: "CTR (%)", dataIndex: "ctr", key: "ctr", render: (v: number) => `${v}%` },
              { title: "Leads", dataIndex: "leads", key: "leads" },
              {
                title: "Conversion Rate (%)",
                dataIndex: "conv_rate",
                key: "conv_rate",
                render: (v: number) => `${v}%`,
              },
              { title: "Cost", dataIndex: "cost", key: "cost", render: (v: number) => formatINR(v) },
              {
                title: "Cost per Lead",
                dataIndex: "cpl",
                key: "cpl",
                render: (v: number) => formatINR(v),
              },
              { title: "ROI (%)", dataIndex: "roi", key: "roi", render: (v: number) => `${v}%` },
            ]}
          />
        </div>
      </Card>
    </Flex>
  );
}
