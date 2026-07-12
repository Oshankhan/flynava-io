import { useEffect, useMemo, useState } from "react";
import { Alert, Card, Col, Empty, Flex, Row, Spin, Table, Tag, Typography } from "antd";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ClockCircleOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { api, ApiError, type ActorCount, type AnalyticsSummary, type DeptCount } from "../lib/api";
import TrendChart from "../components/TrendChart";
import StatusDonut from "../components/StatusDonut";

const { Text, Title } = Typography;

export default function Analytics() {
  const [data, setData] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .analyticsSummary(30)
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load analytics"));
  }, []);

  const trend = useMemo(() => {
    if (!data) return null;
    return {
      kpi_id: "actions_per_day",
      name: "Actions",
      unit: "",
      points: data.actions_per_day.map((d) => ({ t: d.date, v: d.count })),
    };
  }, [data]);

  const actionSlices = useMemo(
    () => data?.by_action.map((a) => ({ status: a.action, count: a.count })) ?? [],
    [data]
  );

  if (error) return <Alert type="error" message={error} showIcon />;
  if (!data)
    return (
      <Flex justify="center" className="pt-20">
        <Spin />
      </Flex>
    );

  const deptCols = [
    { title: "Department", dataIndex: "department", key: "department" },
    { title: "Actions", dataIndex: "count", key: "count", width: 100 },
  ];

  return (
    <div>
      <Flex justify="space-between" align="center" wrap gap={12} className="mb-4">
        <div>
          <Title level={3} className="m-0">Analytics</Title>
          <Text type="secondary">
            {data.total_actions} action{data.total_actions === 1 ? "" : "s"} in the last {data.window_days} days
          </Text>
        </div>
      </Flex>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          {trend && trend.points.length > 0 ? (
            <TrendChart series={trend} />
          ) : (
            <Card size="small" bordered={false} title="Actions" className="h-full">
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No activity yet" />
            </Card>
          )}
        </Col>
        <Col xs={24} lg={10}>
          {actionSlices.length > 0 ? (
            <StatusDonut title="Actions by Type" data={actionSlices} centerLabel="Total Actions" />
          ) : (
            <Card size="small" bordered={false} title="Actions by Type" className="h-full">
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No activity yet" />
            </Card>
          )}
        </Col>

        <Col xs={24} lg={14}>
          <Card size="small" bordered={false} title="Most Active Users">
            {data.top_actors.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No activity yet" />
            ) : (
              <div className="w-full" style={{ height: Math.max(180, data.top_actors.length * 34) }}>
                <ResponsiveContainer>
                  <BarChart
                    data={data.top_actors as ActorCount[]}
                    layout="vertical"
                    margin={{ left: 12, right: 24, top: 4, bottom: 4 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#dfeee6" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 10 }} allowDecimals={false} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={110} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#157f52" radius={[0, 4, 4, 0]} barSize={16} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card size="small" bordered={false} title="Activity by Department">
            {data.by_department.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No activity yet" />
            ) : (
              <Table
                size="small"
                rowKey="department"
                dataSource={data.by_department as DeptCount[]}
                columns={deptCols}
                pagination={false}
              />
            )}
          </Card>
        </Col>

        <Col xs={24}>
          <Card
            size="small"
            bordered={false}
            title={
              <Flex align="center" gap={6}>
                <ThunderboltOutlined className="text-io-600" /> Integration Health
              </Flex>
            }
          >
            {data.integrations.length === 0 ? (
              <Text type="secondary" className="text-xs">
                No integrations synced yet.
              </Text>
            ) : (
              <Row gutter={[16, 16]}>
                {data.integrations.map((i) => (
                  <Col key={i.source} xs={24} md={8}>
                    <Card size="small" bordered className="h-full">
                      <Flex justify="space-between" align="center">
                        <Flex vertical>
                          <Text strong className="capitalize">{i.source}</Text>
                          <Text type="secondary" className="text-[11px]">
                            <ClockCircleOutlined />{" "}
                            {i.run_at ? new Date(i.run_at).toLocaleString() : "never synced"}
                          </Text>
                          {i.records_processed != null && (
                            <Text type="secondary" className="text-[11px]">
                              {i.records_processed} records processed
                            </Text>
                          )}
                        </Flex>
                        <Tag color={i.status === "ok" ? "success" : i.status === "error" ? "error" : "default"}>
                          {i.status ?? "unknown"}
                        </Tag>
                      </Flex>
                    </Card>
                  </Col>
                ))}
              </Row>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
