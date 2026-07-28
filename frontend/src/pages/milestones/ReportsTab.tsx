import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Empty,
  Flex,
  Row,
  Select,
  Spin,
  Table,
  Tabs,
  Typography,
} from "antd";
import { DownloadOutlined, FileTextOutlined } from "@ant-design/icons";
import { useSearchParams } from "react-router-dom";
import {
  api,
  ApiError,
  type MilestoneFilters,
  type MilestoneReportCatalog,
  type MilestoneReportResult,
} from "../../lib/api";
import { useAsyncAction } from "../../lib/useAsyncAction";
import MilestoneFilterBar from "../../components/milestones/MilestoneFilterBar";

const { Text, Title } = Typography;

function ReportTable({ result }: { result: MilestoneReportResult }) {
  return (
    <Table
      size="small"
      rowKey={(_, index) => String(index)}
      dataSource={result.rows ?? []}
      scroll={{ x: "max-content" }}
      pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `${t} rows` }}
      columns={(result.columns ?? []).map((c) => ({
        title: c.title,
        dataIndex: c.key,
        render: (value: unknown) => (value == null || value === "" ? "—" : String(value)),
      }))}
    />
  );
}

/** Screen 6. Predefined reports run server-side against the caller's scope;
 * the custom builder posts a column/group-by selection to the same engine. */
export default function ReportsTab() {
  const { message } = App.useApp();
  const [searchParams, setSearchParams] = useSearchParams();
  const [catalog, setCatalog] = useState<MilestoneReportCatalog | null>(null);
  const [filters, setFilters] = useState<MilestoneFilters>({});
  const [active, setActive] = useState<string | null>(searchParams.get("report"));
  const [result, setResult] = useState<MilestoneReportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [columns, setColumns] = useState<string[]>([
    "milestone_id",
    "name",
    "owner_name",
    "status",
    "progress_pct",
    "due_date",
  ]);
  const [groupBy, setGroupBy] = useState<string | undefined>();

  useEffect(() => {
    api
      .milestoneReportCatalog()
      .then(setCatalog)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Load failed"));
  }, []);

  const run = useCallback(
    async (key: string, next: MilestoneFilters) => {
      setLoading(true);
      setActive(key);
      setSearchParams({ report: key }, { replace: true });
      try {
        setResult(await api.runMilestoneReport(key, next));
        setError(null);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Report failed");
      } finally {
        setLoading(false);
      }
    },
    [setSearchParams]
  );

  // Deep link (?report=…) and re-runs when filters change on an open report.
  useEffect(() => {
    if (active) run(active, filters);
    // `run` is stable; re-running on `active` change is what opens a report.
  }, [active, filters, run]);

  const [exportCsv, exporting] = useAsyncAction(async () => {
    if (!active) return;
    await api.exportMilestoneReport(active, filters);
  });

  const [runCustom, runningCustom] = useAsyncAction(async () => {
    setLoading(true);
    try {
      setResult(
        await api.runCustomMilestoneReport({
          title: "Custom Report",
          columns,
          group_by: groupBy ?? null,
          filters,
        })
      );
      setActive(null);
      setError(null);
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Report failed");
    } finally {
      setLoading(false);
    }
  });

  if (error && !catalog)
    return <Alert type="error" showIcon message="Cannot load reports" description={error} />;
  if (!catalog)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const predefined = (
    <Flex vertical gap={16}>
      <Row gutter={[16, 16]}>
        {catalog.predefined.map((report) => (
          <Col key={report.key} xs={24} md={12} xl={8}>
            <Card
              size="small"
              bordered={false}
              className={`h-full shadow-sm ${active === report.key ? "ring-2 ring-io-600" : ""}`}
            >
              <Flex justify="space-between" align="flex-start" gap={8}>
                <Flex gap={10} align="flex-start" className="min-w-0">
                  <span className="flex items-center justify-center w-9 h-9 rounded-full bg-io-600/10 text-io-600 shrink-0">
                    <FileTextOutlined />
                  </span>
                  <div className="min-w-0">
                    <div className="font-medium">{report.title}</div>
                    <Text type="secondary" className="text-xs">
                      {report.description}
                    </Text>
                  </div>
                </Flex>
                <Button
                  size="small"
                  type="primary"
                  loading={loading && active === report.key}
                  onClick={() => setActive(report.key)}
                >
                  View
                </Button>
              </Flex>
            </Card>
          </Col>
        ))}
      </Row>

      {result && active && (
        <Card
          size="small"
          bordered={false}
          title={
            <div>
              <Title level={5} className="!mb-0">
                {result.title}
              </Title>
              <Text type="secondary" className="text-xs">
                {result.row_count} rows · generated {new Date(result.generated_at).toLocaleString()}
              </Text>
            </div>
          }
          extra={
            <Button icon={<DownloadOutlined />} loading={exporting} onClick={exportCsv}>
              Export CSV
            </Button>
          }
        >
          <ReportTable result={result} />
        </Card>
      )}
    </Flex>
  );

  const custom = (
    <Flex vertical gap={16}>
      <Card size="small" bordered={false} title="Build a report">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <div>
            <Text className="text-xs">Columns</Text>
            <Select
              mode="multiple"
              className="w-full"
              value={columns}
              onChange={setColumns}
              options={catalog.columns.map((c) => ({ value: c.key, label: c.title }))}
            />
          </div>
          <div>
            <Text className="text-xs">Group by (optional)</Text>
            <Select
              allowClear
              className="w-full"
              value={groupBy}
              onChange={setGroupBy}
              placeholder="No grouping"
              options={catalog.columns.map((c) => ({ value: c.key, label: c.title }))}
            />
          </div>
        </div>
        <Flex justify="end" className="mt-3">
          <Button type="primary" loading={runningCustom} onClick={runCustom}>
            Run report
          </Button>
        </Flex>
      </Card>
      {result && !active ? (
        <Card size="small" bordered={false} title={result.title}>
          <ReportTable result={result} />
        </Card>
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Run a report to see results" />
      )}
    </Flex>
  );

  return (
    <Flex vertical gap={16}>
      <MilestoneFilterBar
        value={filters}
        onChange={setFilters}
        loading={loading}
        fields={["department", "team", "project", "status", "priority", "health", "dates"]}
      />
      <Tabs
        defaultActiveKey="predefined"
        items={[
          { key: "predefined", label: "Predefined Reports", children: predefined },
          { key: "custom", label: "Custom Reports", children: custom },
        ]}
      />
    </Flex>
  );
}
