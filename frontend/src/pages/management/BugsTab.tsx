import { useEffect, useState } from "react";
import { Alert, Card, Col, Flex, Row, Select, Spin, Table, Tag } from "antd";
import {
  BugOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  PercentageOutlined,
  PlusCircleOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import { api, ApiError, type ManagementBugsPayload } from "../../lib/api";
import WeekPeriodFilter, {
  periodToQuery,
  type BugsPeriodValue,
} from "../../components/management/WeekPeriodFilter";
import MiniStatCard from "../../components/success/MiniStatCard";
import LabeledDonut from "../../components/success/LabeledDonut";
import TrendMini from "../../components/success/TrendMini";
import GroupedBarChart from "../../components/forecaster/GroupedBarChart";
import CountBars from "../../components/management/CountBars";
import TwoSeriesLine from "../../components/management/TwoSeriesLine";

const SEVERITY_COLOR: Record<string, string> = {
  Critical: "error",
  High: "error",
  Medium: "warning",
  Low: "default",
};

const ALL_PROJECTS = "__all__";

export default function BugsTab() {
  const [period, setPeriod] = useState<BugsPeriodValue>({ mode: "month" });
  const [project, setProject] = useState<string | undefined>(undefined);
  const [data, setData] = useState<ManagementBugsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .managementBugs({ ...periodToQuery(period), project })
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, [period.mode, period.from, period.to, project]);

  async function refresh() {
    try {
      setData(await api.managementBugs({ ...periodToQuery(period), project }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }

  if (error)
    return <Alert type="error" showIcon message="Cannot load Project Bugs Tracker" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const [unresolved, avgResolution, created, resolved, resolutionRate] = data.cards;

  return (
    <Flex vertical gap={20}>
      <Flex wrap align="center" justify="space-between" gap={12}>
        <Select
          className="w-full sm:w-[240px]"
          value={project ?? ALL_PROJECTS}
          onChange={(v) => setProject(v === ALL_PROJECTS ? undefined : v)}
          options={[
            { value: ALL_PROJECTS, label: "All Projects" },
            ...data.projects.map((p) => ({ value: p.project, label: p.name })),
          ]}
        />
        <WeekPeriodFilter period={period} onChange={setPeriod} lastUpdated={data.last_updated} onRefresh={refresh} />
      </Flex>

      <Row gutter={[16, 16]}>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={unresolved} icon={<BugOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={avgResolution} icon={<ClockCircleOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={created} icon={<PlusCircleOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={5}>
          <MiniStatCard card={resolved} icon={<CheckCircleOutlined />} />
        </Col>
        <Col xs={12} md={8} xl={4}>
          <MiniStatCard card={resolutionRate} icon={<PercentageOutlined />} />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="Bugs Creation Trend" size="small" bordered={false} className="h-full">
            <TwoSeriesLine
              points={data.charts.creation_trend.points}
              aKey="created" aName="Created" aColor="#7c3aed"
              bKey="resolved" bName="Resolved" bColor="#157f52"
            />
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title="Bugs by Status" size="small" bordered={false} className="h-full">
            <Row gutter={[12, 12]}>
              <Col xs={24} sm={12}>
                <LabeledDonut title="" slices={data.charts.by_status.slices} centerLabel="Total" />
              </Col>
              <Col xs={24} sm={12}>
                <Table
                  size="small"
                  pagination={false}
                  rowKey="status"
                  dataSource={data.tables.by_status}
                  columns={[
                    { title: "Status", dataIndex: "status", key: "status" },
                    { title: "Count", dataIndex: "count", key: "count" },
                    { title: "%", dataIndex: "pct", key: "pct", render: (v: number) => `${v}%` },
                  ]}
                />
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="Top Bug Modules" size="small" bordered={false} className="h-full">
            <CountBars
              rows={data.tables.by_module.map((m) => ({ label: m.module, count: m.count, pct: m.pct }))}
            />
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <LabeledDonut title="Bugs Severity Distribution" slices={data.charts.by_severity.slices} centerLabel="Total" />
        </Col>
      </Row>

      <Card title="Recent Unresolved Bugs" size="small" bordered={false}>
        <Table
          size="small"
          pagination={false}
          rowKey="bug_id"
          scroll={{ x: true }}
          dataSource={data.tables.recent_unresolved}
          columns={[
            { title: "Bug ID", dataIndex: "bug_id", key: "bug_id" },
            { title: "Project", dataIndex: "project", key: "project" },
            { title: "Title", dataIndex: "title", key: "title" },
            {
              title: "Severity", dataIndex: "severity", key: "severity",
              render: (v: string) => <Tag color={SEVERITY_COLOR[v] ?? "default"}>{v}</Tag>,
            },
            { title: "Status", dataIndex: "status", key: "status" },
            { title: "Assignee", dataIndex: "assignee", key: "assignee" },
            {
              title: "Reported On", dataIndex: "reported_on", key: "reported_on",
              render: (v: string | null) => (v ? dayjs(v).format("DD MMM YYYY") : "—"),
            },
            { title: "Age (Days)", dataIndex: "age_days", key: "age_days" },
          ]}
        />
        {data.tables.recent_unresolved.length === 0 && (
          <div className="text-center text-xs text-gray-400 py-4">No unresolved bugs.</div>
        )}
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <Card title="Bugs Status Overview" size="small" bordered={false} className="h-full">
            <GroupedBarChart
              series={[{
                key: "count", name: "Bugs", color: "#157f52",
                points: data.tables.by_status.map((s) => ({ t: s.status, v: s.count })),
              }]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={12}>
          <Card title="Bugs Resolution Time (Days)" size="small" bordered={false} className="h-full">
            <div className="w-full h-[220px]">
              <TrendMini points={data.charts.resolution_time_trend.points} color="#7c3aed" />
            </div>
          </Card>
        </Col>
      </Row>

      <Card title="Recent Activity" size="small" bordered={false}>
        <Table
          size="small"
          pagination={false}
          rowKey={(r) => `${r.bug_id}-${r.at}`}
          scroll={{ x: true }}
          dataSource={data.tables.recent_activity}
          columns={[
            { title: "Bug ID", dataIndex: "bug_id", key: "bug_id" },
            { title: "Project", dataIndex: "project", key: "project" },
            { title: "Detail", dataIndex: "detail", key: "detail" },
            {
              title: "At", dataIndex: "at", key: "at",
              render: (v: string) => dayjs(v).format("DD MMM YYYY HH:mm"),
            },
          ]}
        />
        {data.tables.recent_activity.length === 0 && (
          <div className="text-center text-xs text-gray-400 py-4">No recent activity.</div>
        )}
      </Card>
    </Flex>
  );
}
