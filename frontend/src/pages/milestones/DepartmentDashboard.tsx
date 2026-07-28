import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Col, Flex, Progress, Row, Select, Spin, Statistic, Table, Typography } from "antd";
import { DownloadOutlined, ReloadOutlined } from "@ant-design/icons";
import { useNavigate, useParams } from "react-router-dom";
import {
  api,
  ApiError,
  type MilestoneDepartmentPayload,
  type MilestoneFilters,
} from "../../lib/api";
import { useAsyncAction } from "../../lib/useAsyncAction";
import LabeledDonut from "../../components/success/LabeledDonut";
import ProgressTrendChart from "../../components/milestones/ProgressTrendChart";
import MilestoneFilterBar from "../../components/milestones/MilestoneFilterBar";
import {
  NeedsAttentionCard,
  TopPerformersCard,
  UpcomingDeadlinesCard,
} from "../../components/milestones/DashboardPanels";
import { HealthBadge } from "../../components/milestones/MilestoneBadges";

const { Text } = Typography;

/** Screen 5. Renders a picker when no department is in the URL — a department
 * head only ever gets their own, so the picker collapses to a label for them. */
export default function DepartmentDashboard() {
  const params = useParams();
  const navigate = useNavigate();
  const [departments, setDepartments] = useState<{ dept_id: string; name: string }[]>([]);
  const [deptId, setDeptId] = useState<string | undefined>(params.deptId);
  const [filters, setFilters] = useState<MilestoneFilters>({});
  const [data, setData] = useState<MilestoneDepartmentPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .milestoneDepartments()
      .then((list) => {
        setDepartments(list);
        setDeptId((current) => current ?? list?.[0]?.dept_id);
      })
      .catch(() => setDepartments([]));
  }, []);

  useEffect(() => setDeptId(params.deptId ?? undefined), [params.deptId]);

  const load = useCallback(async () => {
    if (!deptId) return;
    setLoading(true);
    try {
      setData(await api.departmentMilestones(deptId, filters));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }, [deptId, filters]);

  useEffect(() => {
    load();
  }, [load]);

  const [refresh, refreshing] = useAsyncAction(load);
  const [exportCsv, exporting] = useAsyncAction(() =>
    api.exportMilestones({ ...filters, department: deptId }, `milestones-${deptId}.csv`)
  );

  if (error)
    return (
      <Alert type="error" showIcon message="Cannot load department dashboard" description={error} />
    );

  return (
    <Flex vertical gap={16}>
      <Flex justify="space-between" align="center" wrap gap={8}>
        <Select
          className="min-w-[220px]"
          value={deptId}
          placeholder="Select a department"
          options={departments.map((d) => ({ value: d.dept_id, label: d.name }))}
          onChange={(v) => navigate(`/milestones/department/${v}`)}
        />
        <Flex gap={8}>
          <Button icon={<DownloadOutlined />} loading={exporting} onClick={exportCsv}>
            Export
          </Button>
          <Button icon={<ReloadOutlined />} loading={refreshing} onClick={refresh}>
            Refresh
          </Button>
        </Flex>
      </Flex>

      <MilestoneFilterBar
        value={filters}
        onChange={setFilters}
        loading={loading}
        fields={["team", "project", "category", "status", "priority", "dates"]}
      />

      {!data ? (
        <Flex align="center" justify="center" className="min-h-[240px]">
          <Spin size="large" />
        </Flex>
      ) : (
        <Spin spinning={loading}>
          <Flex vertical gap={16}>
            <Row gutter={[16, 16]}>
              <Col xs={12} md={8} xl={4}>
                <Card size="small" bordered={false} className="shadow-sm">
                  <Statistic title="Total Milestones" value={data.stats?.total ?? 0} />
                </Card>
              </Col>
              <Col xs={12} md={8} xl={4}>
                <Card size="small" bordered={false} className="shadow-sm">
                  <Statistic title="Completed" value={data.stats?.completed ?? 0} />
                </Card>
              </Col>
              <Col xs={12} md={8} xl={4}>
                <Card size="small" bordered={false} className="shadow-sm">
                  <Statistic title="In Progress" value={data.stats?.in_progress ?? 0} />
                </Card>
              </Col>
              <Col xs={12} md={8} xl={4}>
                <Card size="small" bordered={false} className="shadow-sm">
                  <Statistic
                    title="Overdue"
                    value={data.stats?.overdue ?? 0}
                    valueStyle={{ color: (data.stats?.overdue ?? 0) > 0 ? "#cf1322" : undefined }}
                  />
                </Card>
              </Col>
              <Col xs={12} md={8} xl={4}>
                <Card size="small" bordered={false} className="shadow-sm">
                  <Statistic
                    title="Completion"
                    value={data.stats?.completion_pct ?? 0}
                    suffix="%"
                    valueStyle={{ color: "#157f52" }}
                  />
                </Card>
              </Col>
              <Col xs={12} md={8} xl={4}>
                <Card size="small" bordered={false} className="shadow-sm">
                  <Statistic
                    title="Avg Progress"
                    value={data.stats?.avg_progress_pct ?? 0}
                    suffix="%"
                  />
                </Card>
              </Col>
            </Row>

            <Row gutter={[16, 16]} align="stretch">
              <Col xs={24} xl={14}>
                <ProgressTrendChart
                  title="Progress Trend"
                  points={data.trend?.points ?? []}
                  showGranularity
                />
              </Col>
              <Col xs={24} xl={10}>
                <LabeledDonut
                  title="Milestones by Priority"
                  slices={data.priority_donut?.slices ?? []}
                  centerLabel="Total"
                />
              </Col>
            </Row>

            <Row gutter={[16, 16]} align="stretch">
              <Col xs={24} xl={12}>
                <LabeledDonut
                  title="Milestones by Status"
                  slices={data.status_donut?.slices ?? []}
                  centerLabel="Total"
                />
              </Col>
              <Col xs={24} xl={12}>
                <Card title="Team Breakdown" size="small" bordered={false} className="h-full">
                  <Table
                    size="small"
                    rowKey="team_id"
                    dataSource={data.teams ?? []}
                    pagination={false}
                    scroll={{ x: "max-content" }}
                    columns={[
                      { title: "Team", dataIndex: "name" },
                      { title: "Milestones", dataIndex: "total", width: 110 },
                      { title: "Overdue", dataIndex: "overdue", width: 100 },
                      {
                        title: "Progress",
                        dataIndex: "progress_pct",
                        width: 150,
                        render: (v: number) => (
                          <Progress percent={Math.round(v)} size="small" className="!mb-0" />
                        ),
                      },
                      {
                        title: "Health",
                        dataIndex: "health",
                        width: 150,
                        render: (h: "good" | "needs_attention" | "at_risk") => (
                          <HealthBadge health={h} />
                        ),
                      },
                    ]}
                  />
                </Card>
              </Col>
            </Row>

            <Row gutter={[16, 16]} align="stretch">
              <Col xs={24} xl={8}>
                <TopPerformersCard rows={data.top_performers ?? []} />
              </Col>
              <Col xs={24} xl={8}>
                <NeedsAttentionCard rows={data.needs_attention ?? []} />
              </Col>
              <Col xs={24} xl={8}>
                <UpcomingDeadlinesCard rows={data.upcoming_deadlines ?? []} />
              </Col>
            </Row>

            <Text type="secondary" className="text-xs">
              {data.department?.name} · last updated {new Date(data.generated_at).toLocaleString()}
            </Text>
          </Flex>
        </Spin>
      )}
    </Flex>
  );
}
