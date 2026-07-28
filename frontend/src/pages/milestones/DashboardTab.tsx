import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Col, Flex, Row, Spin, Typography } from "antd";
import {
  AlertOutlined,
  CheckCircleOutlined,
  DashboardOutlined,
  DownloadOutlined,
  HeartOutlined,
  ReloadOutlined,
  TeamOutlined,
  TrophyOutlined,
} from "@ant-design/icons";
import { api, ApiError, type MilestoneDashboardPayload, type MilestoneFilters } from "../../lib/api";
import { useAsyncAction } from "../../lib/useAsyncAction";
import MiniStatCard from "../../components/success/MiniStatCard";
import LabeledDonut from "../../components/success/LabeledDonut";
import MilestoneFilterBar from "../../components/milestones/MilestoneFilterBar";
import ProgressTrendChart from "../../components/milestones/ProgressTrendChart";
import {
  DepartmentProgressCard,
  NeedsAttentionCard,
  TopPerformersCard,
  UpcomingDeadlinesCard,
} from "../../components/milestones/DashboardPanels";

const { Text } = Typography;

const CARD_ICONS: Record<string, React.ReactNode> = {
  total_employees: <TeamOutlined />,
  active_milestones: <DashboardOutlined />,
  completed_month: <CheckCircleOutlined />,
  overdue: <AlertOutlined />,
  company_completion: <TrophyOutlined />,
  org_health: <HeartOutlined />,
};

export default function DashboardTab() {
  const [filters, setFilters] = useState<MilestoneFilters>({});
  const [data, setData] = useState<MilestoneDashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (next: MilestoneFilters) => {
    setLoading(true);
    try {
      setData(await api.milestoneDashboard(next));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    } finally {
      setLoading(false);
    }
  }, []);

  // Refetches whenever the applied filter set changes.
  useEffect(() => {
    load(filters);
  }, [filters, load]);

  const [refresh, refreshing] = useAsyncAction(() => load(filters));
  const [exportCsv, exporting] = useAsyncAction(() => api.exportMilestones(filters));

  if (error)
    return <Alert type="error" showIcon message="Cannot load Milestone Dashboard" description={error} />;

  return (
    <Flex vertical gap={16}>
      <MilestoneFilterBar
        value={filters}
        onChange={setFilters}
        loading={loading}
        fields={["department", "team", "project", "category", "manager", "dates"]}
        extra={
          <>
            <Button icon={<DownloadOutlined />} loading={exporting} onClick={exportCsv}>
              Export
            </Button>
            <Button icon={<ReloadOutlined />} loading={refreshing} onClick={refresh}>
              Refresh
            </Button>
          </>
        }
      />

      {!data ? (
        <Flex align="center" justify="center" className="min-h-[240px]">
          <Spin size="large" />
        </Flex>
      ) : (
        <Spin spinning={loading}>
          <Flex vertical gap={16}>
            <Row gutter={[16, 16]}>
              {data.cards?.map((card) => (
                <Col key={card.id} xs={12} sm={12} md={8} xl={4}>
                  <MiniStatCard card={card} icon={CARD_ICONS[card.id] ?? <DashboardOutlined />} />
                </Col>
              ))}
            </Row>

            <Row gutter={[16, 16]} align="stretch">
              <Col xs={24} xl={8}>
                <LabeledDonut
                  title="Milestones by Status"
                  slices={data.status_donut?.slices ?? []}
                  centerLabel="Total"
                />
              </Col>
              <Col xs={24} xl={10}>
                <ProgressTrendChart
                  title="Company Progress Trend"
                  points={data.trend?.points ?? []}
                  showGranularity
                />
              </Col>
              <Col xs={24} xl={6}>
                <DepartmentProgressCard rows={data.departments ?? []} />
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
              Organization Health {data.org_health?.score}/100 ({data.org_health?.band}) · last
              updated {new Date(data.generated_at).toLocaleString()}
            </Text>
          </Flex>
        </Spin>
      )}
    </Flex>
  );
}
