import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Alert, Col, Empty, Flex, Row, Spin } from "antd";
import { api, ApiError, type DashboardPayload } from "../lib/api";
import KpiCard from "../components/KpiCard";
import KpiBarChart from "../components/KpiBarChart";
import ProjectHealth from "../components/ProjectHealth";
import TrendChart from "../components/TrendChart";
import BugDonut from "../components/BugDonut";

export default function Dashboard() {
  const { key = "leadership" } = useParams();
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(null);
    api
      .getDashboard(key)
      .then((d) => alive && setData(d))
      .catch((err) =>
        alive && setError(err instanceof ApiError ? err.message : "Load failed")
      );
    return () => {
      alive = false;
    };
  }, [key]);

  if (error)
    return <Alert type="error" showIcon message="Cannot load dashboard" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" style={{ minHeight: 240 }}>
        <Spin tip="Loading…">
          <div style={{ height: 60 }} />
        </Spin>
      </Flex>
    );

  const charts = data.series ?? [];
  const hasCharts = charts.length > 0 || data.bug_breakdown;

  return (
    <Flex vertical gap={20}>
      {data.kpis.length === 0 ? (
        <Empty description="No KPIs yet — connect integrations and recalculate." />
      ) : (
        <Row gutter={[16, 16]}>
          {data.kpis.map((k) => (
            <Col key={k.kpi_id} xs={24} sm={12} lg={8} xl={6}>
              <KpiCard kpi={k} />
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
    </Flex>
  );
}
