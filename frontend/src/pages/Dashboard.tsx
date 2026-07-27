import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Alert, Col, Empty, Flex, Row, Spin } from "antd";
import { api, ApiError, type DashboardPayload, type InsightProject, type Kpi } from "../lib/api";
import KpiCard from "../components/KpiCard";
import KpiBarChart from "../components/KpiBarChart";
import KpiExplainDrawer from "../components/KpiExplainDrawer";
import ProjectHealth from "../components/ProjectHealth";
import TrendChart from "../components/TrendChart";
import BugDonut from "../components/BugDonut";
import InsightsSection from "../components/insights/InsightsSection";

export default function Dashboard() {
  const { key = "leadership" } = useParams();
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [explainKpiId, setExplainKpiId] = useState<string | null>(null);
  const [projects, setProjects] = useState<InsightProject[]>([]);
  const [project, setProject] = useState<string | undefined>(undefined);

  // Switching dashboards resets the project scope and shows the full-page
  // loading state again; switching just the project scope (below) re-fetches
  // in place so the grid doesn't flash empty on every dropdown change.
  useEffect(() => {
    setProject(undefined);
    setData(null);
    setError(null);
  }, [key]);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .getDashboard(key, project)
      .then((d) => alive && setData(d))
      .catch((err) =>
        alive && setError(err instanceof ApiError ? err.message : "Load failed")
      );
    return () => {
      alive = false;
    };
  }, [key, project]);

  const hasOperations = (data?.insight_depts ?? []).includes("operations");

  // Project dropdown data only makes sense (and is only RBAC-permitted) once
  // we know this dashboard actually surfaces operations data.
  useEffect(() => {
    if (!hasOperations) {
      setProjects([]);
      return;
    }
    let alive = true;
    api
      .insightProjects()
      .then((rows) => alive && setProjects(rows))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [hasOperations]);

  // Project task_counts are a point-in-time snapshot from the fetch above —
  // the Insights "Refresh" button re-runs the detectors, but a project's
  // count only changes when the underlying OpenProject sync adds/removes
  // tasks. Let Refresh pull a fresh count too, so it doesn't look stuck.
  async function refreshProjects() {
    if (!hasOperations) return;
    try {
      setProjects(await api.insightProjects());
    } catch {
      /* keep showing the last known counts */
    }
  }

  if (error)
    return <Alert type="error" showIcon message="Cannot load dashboard" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const charts = data.series ?? [];
  const hasCharts = charts.length > 0 || data.bug_breakdown;
  const seriesById = Object.fromEntries(charts.map((s) => [s.kpi_id, s]));

  return (
    <Flex vertical gap={20}>
      <InsightsSection
        depts={data.insight_depts ?? []}
        project={project}
        projects={projects}
        onProjectChange={setProject}
        onRefreshProjects={refreshProjects}
      />

      {!data.kpis?.length ? (
        <Empty description="No KPIs yet — connect integrations and recalculate." />
      ) : (
        <Row gutter={[16, 16]}>
          {data.kpis?.map((k) => (
            <Col key={k.kpi_id} xs={24} sm={12} lg={8} xl={6}>
              <KpiCard
                kpi={k}
                series={seriesById[k.kpi_id]}
                onClick={(kpi: Kpi) => setExplainKpiId(kpi.kpi_id)}
              />
            </Col>
          ))}
        </Row>
      )}

      {hasCharts && (
        <Row gutter={[16, 16]}>
          {charts.map((s) => (
            <Col key={s.kpi_id} xs={24} lg={12}>
              <TrendChart series={s} />
            </Col>
          ))}
          {data.bug_breakdown && (
            <Col xs={24} lg={12}>
              <BugDonut data={data.bug_breakdown} />
            </Col>
          )}
        </Row>
      )}

      <KpiBarChart kpis={data.kpis} />
      <ProjectHealth projects={data.projects} />

      <KpiExplainDrawer kpiId={explainKpiId} onClose={() => setExplainKpiId(null)} />
    </Flex>
  );
}
