import { useEffect, useState } from "react";
import { ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Col, Empty, Flex, Row, Select, Spin, Tabs, Typography } from "antd";
import { api, ApiError, type InsightProject, type InsightsPayload } from "../../lib/api";
import { useAsyncAction } from "../../lib/useAsyncAction";
import InsightCard from "./InsightCard";

const { Title } = Typography;

const DEPT_LABEL: Record<string, string> = {
  operations: "Operations",
  finance: "Finance",
  hr: "HR",
  marketing: "Marketing & Sales",
};

const ALL_PROJECTS = "__all__";

function DeptInsights({
  dept,
  project,
  projects,
  onProjectChange,
  onRefreshProjects,
}: {
  dept: string;
  project?: string;
  /** Only passed for the operations tab — its dropdown, rendered right next
   * to Refresh, since project scope only applies to OpenProject-shaped data. */
  projects?: InsightProject[];
  onProjectChange?: (project: string | undefined) => void;
  /** Re-fetches the dropdown's per-project task counts — wired into Refresh
   * so a stale count (e.g. after a new OpenProject sync) doesn't look stuck. */
  onRefreshProjects?: () => Promise<void>;
}) {
  const [data, setData] = useState<InsightsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    setData(null);
    setError(null);
    setLoading(true);
    api
      .insights(dept, project)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [dept, project]);

  const [runRefresh, refreshing] = useAsyncAction(async () => {
    setError(null);
    try {
      const [insights] = await Promise.all([
        api.refreshInsights(dept, project),
        onRefreshProjects?.(),
      ]);
      setData(insights);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Refresh failed");
    }
  });

  async function handleVote(insightId: string, useful: boolean) {
    const result = await api.insightFeedback(insightId, useful);
    setData((prev) =>
      prev
        ? {
            ...prev,
            cards: prev.cards.map((c) =>
              c.insight_id === insightId
                ? {
                    ...c,
                    feedback: { useful: result.useful, not_useful: result.not_useful, mine: result.mine },
                  }
                : c
            ),
          }
        : prev
    );
  }

  return (
    <Flex vertical gap={12}>
      <Flex justify="end" gap={8} wrap>
        {projects && projects.length > 0 && onProjectChange && (
          <Select
            className="w-full sm:w-[240px]"
            value={project ?? ALL_PROJECTS}
            onChange={(v) => onProjectChange(v === ALL_PROJECTS ? undefined : v)}
            options={[
              { value: ALL_PROJECTS, label: "All projects" },
              ...projects.map((p) => ({
                value: p.source_id,
                label: `${p.name} (${p.task_count})`,
              })),
            ]}
          />
        )}
        <Button icon={<ReloadOutlined />} loading={refreshing} onClick={runRefresh}>
          Refresh
        </Button>
      </Flex>

      {loading && (
        <Flex align="center" justify="center" className="min-h-[120px]">
          <Spin />
        </Flex>
      )}
      {error && <Alert type="error" showIcon message="Cannot load insights" description={error} />}
      {!loading && !error && data && data.cards.length === 0 && (
        <Empty description="No problems detected right now." />
      )}
      {!loading && !error && data && data.cards.length > 0 && (
        <Row gutter={[12, 12]}>
          {data.cards.map((c) => (
            <Col key={c.insight_id} xs={24} lg={12} xxl={8}>
              <InsightCard card={c} onVote={handleVote} />
            </Col>
          ))}
        </Row>
      )}
    </Flex>
  );
}

export default function InsightsSection({
  depts,
  project,
  projects,
  onProjectChange,
  onRefreshProjects,
}: {
  depts: string[];
  /** Project scope from the dashboard-level selector — only applied to the
   * operations tab, since only its data is OpenProject-project-shaped. */
  project?: string;
  projects?: InsightProject[];
  onProjectChange?: (project: string | undefined) => void;
  onRefreshProjects?: () => Promise<void>;
}) {
  if (depts.length === 0) return null;

  const opsProps = (dept: string) =>
    dept === "operations" ? { project, projects, onProjectChange, onRefreshProjects } : {};

  if (depts.length === 1) {
    return (
      <div>
        <Title level={5} className="!mb-3">
          AI Insights — {DEPT_LABEL[depts[0]] ?? depts[0]}
        </Title>
        <DeptInsights dept={depts[0]} {...opsProps(depts[0])} />
      </div>
    );
  }

  return (
    <div>
      <Title level={5} className="!mb-1">
        AI Insights
      </Title>
      <Tabs
        items={depts.map((d) => ({
          key: d,
          label: DEPT_LABEL[d] ?? d,
          children: <DeptInsights dept={d} {...opsProps(d)} />,
        }))}
      />
    </div>
  );
}
