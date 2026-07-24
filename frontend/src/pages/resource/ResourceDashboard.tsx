import { useEffect, useState } from "react";
import { Alert, Button, Col, Flex, Row, Spin, Typography } from "antd";
import { DownloadOutlined, ReloadOutlined } from "@ant-design/icons";
import { api, ApiError, type ResourceDashboardPayload } from "../../lib/api";
import { useAsyncAction } from "../../lib/useAsyncAction";
import KpiCard from "../../components/KpiCard";
import TeamCapacityCard from "../../components/resource/TeamCapacityCard";
import WorkloadHeatmap from "../../components/resource/WorkloadHeatmap";
import TopPerformers from "../../components/resource/TopPerformers";
import PerformanceMatrix from "../../components/resource/PerformanceMatrix";
import AtRiskResources from "../../components/resource/AtRiskResources";
import ProjectResourceStatusCard from "../../components/resource/ProjectResourceStatus";
import WorkLifecycleOverview from "../../components/resource/WorkLifecycleOverview";
import ResourceInsights from "../../components/resource/ResourceInsights";

const { Text } = Typography;

function toCsv(data: ResourceDashboardPayload): string {
  const lines = ["Employee,Role,Team,Workload %,Tasks,Completion %,Status"];
  for (const r of data.heatmap ?? []) {
    lines.push(
      [r.name, r.designation ?? "", r.team_name ?? "", r.workload_pct, r.tasks, r.completion_pct, r.status]
        .map((v) => `"${String(v).replace(/"/g, '""')}"`)
        .join(",")
    );
  }
  return lines.join("\n");
}

function downloadCsv(data: ResourceDashboardPayload) {
  const blob = new Blob([toCsv(data)], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `resource-report-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ResourceDashboard() {
  const [data, setData] = useState<ResourceDashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .resourceDashboard()
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, []);

  const [refresh, refreshing] = useAsyncAction(async () => {
    try {
      setData(await api.resourceDashboard());
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  });

  if (error)
    return <Alert type="error" showIcon message="Cannot load Resource Dashboard" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  return (
    <Flex vertical gap={20}>
      <Flex justify="space-between" align="center" wrap gap={8}>
        <Text type="secondary" className="text-xs">
          Last updated {new Date(data.generated_at).toLocaleString()}
        </Text>
        <Flex gap={8}>
          <Button icon={<DownloadOutlined />} onClick={() => downloadCsv(data)}>
            Export Report
          </Button>
          <Button icon={<ReloadOutlined />} loading={refreshing} onClick={refresh}>
            Refresh
          </Button>
        </Flex>
      </Flex>

      <Row gutter={[16, 16]}>
        {data.kpi_cards?.map((kpi) => (
          <Col key={kpi.kpi_id} xs={12} sm={12} md={8} xl={4}>
            <KpiCard kpi={kpi} />
          </Col>
        ))}
      </Row>

      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} xl={12}>
          <TeamCapacityCard rows={data.team_capacity} />
        </Col>
        <Col xs={24} xl={12}>
          <WorkloadHeatmap rows={data.heatmap} />
        </Col>
      </Row>

      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} xl={12}>
          <PerformanceMatrix rows={data.team_capacity} />
        </Col>
        <Col xs={24} xl={12}>
          <AtRiskResources rows={data.at_risk_resources} />
        </Col>
      </Row>

      <Row gutter={[16, 16]} align="stretch">
        <Col xs={24} xl={12}>
          <TopPerformers rows={data.top_performers} />
        </Col>
        <Col xs={24} xl={12}>
          <ProjectResourceStatusCard rows={data.project_resource_status} />
        </Col>
      </Row>

      <WorkLifecycleOverview departments={data.work_lifecycle} />

      <ResourceInsights insights={data.insights} />
    </Flex>
  );
}
