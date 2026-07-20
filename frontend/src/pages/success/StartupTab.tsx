import { useEffect, useMemo, useState } from "react";
import { Alert, Card, Checkbox, Col, Dropdown, Flex, Input, Row, Spin, Table, Typography } from "antd";
import {
  DownloadOutlined,
  DollarOutlined,
  FireOutlined,
  SettingOutlined,
  TeamOutlined,
  WalletOutlined,
} from "@ant-design/icons";
import { api, ApiError, type StartupPayload } from "../../lib/api";
import PeriodFilter, {
  periodToParams,
  type SuccessPeriodValue,
} from "../../components/success/PeriodFilter";
import HeroKpiCard from "../../components/success/HeroKpiCard";
import SparkCell from "../../components/success/SparkCell";
import TrendMini from "../../components/success/TrendMini";

const { Text } = Typography;

type ColumnKey = "current" | "previous" | "change" | "trend";
const COLUMN_LABELS: Record<ColumnKey, string> = {
  current: "Current Month",
  previous: "Last Month",
  change: "Change",
  trend: "Trend",
};

function downloadCsv(rows: StartupPayload["tables"]["kpi_overview"]) {
  const header = ["Metric", "Current Month", "Last Month", "Change", "Change %"];
  const lines = rows.map((r) =>
    [r.metric, r.current ?? "", r.previous ?? "", r.change ?? "", r.change_pct ?? ""].join(",")
  );
  const csv = [header.join(","), ...lines].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "startup-kpi-overview.csv";
  a.click();
  URL.revokeObjectURL(url);
}

export default function StartupTab() {
  const [period, setPeriod] = useState<SuccessPeriodValue>({ mode: "current" });
  const [data, setData] = useState<StartupPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [visibleCols, setVisibleCols] = useState<ColumnKey[]>([
    "current",
    "previous",
    "change",
    "trend",
  ]);

  useEffect(() => {
    let alive = true;
    setError(null);
    api
      .successStartup(periodToParams(period).month)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"));
    return () => {
      alive = false;
    };
  }, [period.mode, period.month, period.from, period.to]);

  async function refresh() {
    try {
      setData(await api.successStartup(periodToParams(period).month));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }

  const filteredRows = useMemo(() => {
    if (!data) return [];
    const q = search.trim().toLowerCase();
    return q ? data.tables.kpi_overview.filter((r) => r.metric.toLowerCase().includes(q)) : data.tables.kpi_overview;
  }, [data, search]);

  if (error)
    return <Alert type="error" showIcon message="Cannot load Startup Metrics" description={error} />;
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const [activeCustomers, arpa, grossBurn, mrr, arr] = data.cards;

  const columns = [
    { title: "Metric", dataIndex: "metric", key: "metric" },
    visibleCols.includes("current") && {
      title: "Current Month",
      dataIndex: "current",
      key: "current",
      render: (v: number | null) => (v == null ? "—" : v.toLocaleString()),
    },
    visibleCols.includes("previous") && {
      title: "Last Month",
      dataIndex: "previous",
      key: "previous",
      render: (v: number | null) => (v == null ? "—" : v.toLocaleString()),
    },
    visibleCols.includes("change") && {
      title: "Change",
      key: "change",
      render: (_: unknown, row: StartupPayload["tables"]["kpi_overview"][number]) =>
        row.change == null ? (
          "—"
        ) : (
          <span className={row.change >= 0 ? "text-io-600" : "text-red-600"}>
            {row.change >= 0 ? "+" : ""}
            {row.change.toLocaleString()}
            {row.change_pct != null && ` (${row.change_pct > 0 ? "+" : ""}${row.change_pct}%)`}
          </span>
        ),
    },
    visibleCols.includes("trend") && {
      title: "Trend",
      dataIndex: "spark",
      key: "trend",
      render: (spark: StartupPayload["tables"]["kpi_overview"][number]["spark"]) => (
        <SparkCell points={spark} />
      ),
    },
  ].filter(Boolean) as never[];

  return (
    <Flex vertical gap={20}>
      <PeriodFilter period={period} onChange={setPeriod} lastUpdated={data.last_updated} onRefresh={refresh} />

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={5}>
          <HeroKpiCard card={activeCustomers} icon={<TeamOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={5}>
          <HeroKpiCard card={arpa} icon={<WalletOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={5}>
          <HeroKpiCard card={grossBurn} icon={<FireOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={5}>
          <HeroKpiCard card={mrr} icon={<DollarOutlined />} />
        </Col>
        <Col xs={24} sm={12} xl={4}>
          <HeroKpiCard card={arr} icon={<DollarOutlined />} />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="Monthly Recurring Revenue (MRR) Trend" size="small" bordered={false} className="h-full">
            <div className="w-full h-[220px]">
              <TrendMini points={data.charts.mrr_trend.points} color="#157f52" />
            </div>
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="Daily Active Users (DAU) Trend" size="small" bordered={false} className="h-full">
            <div className="w-full h-[220px]">
              <TrendMini points={data.charts.dau_trend.points} color="#4f46e5" />
            </div>
            <Text type="secondary" className="text-xs">
              Average DAU: {data.charts.dau_trend.average.toLocaleString()}
            </Text>
          </Card>
        </Col>
        <Col xs={24} xl={8}>
          <Card title="Customer Acquisition Cost (CAC) Trend" size="small" bordered={false} className="h-full">
            <div className="w-full h-[220px]">
              <TrendMini points={data.charts.cac_trend.points} color="#d97706" />
            </div>
          </Card>
        </Col>
      </Row>

      <Card
        title="Startup KPI Overview"
        size="small"
        bordered={false}
        extra={
          <Flex gap={8}>
            <Input.Search
              placeholder="Search KPI..."
              allowClear
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-40 sm:w-56"
            />
            <Dropdown
              menu={{
                items: (Object.keys(COLUMN_LABELS) as ColumnKey[]).map((key) => ({
                  key,
                  label: (
                    <Checkbox
                      checked={visibleCols.includes(key)}
                      onChange={(e) => {
                        setVisibleCols((prev) =>
                          e.target.checked ? [...prev, key] : prev.filter((c) => c !== key)
                        );
                      }}
                    >
                      {COLUMN_LABELS[key]}
                    </Checkbox>
                  ),
                })),
              }}
              trigger={["click"]}
            >
              <a onClick={(e) => e.preventDefault()} className="inline-flex items-center gap-1 text-sm">
                <SettingOutlined /> Columns
              </a>
            </Dropdown>
            <a
              onClick={() => downloadCsv(filteredRows)}
              className="inline-flex items-center gap-1 text-sm text-io-600"
            >
              <DownloadOutlined /> Export
            </a>
          </Flex>
        }
      >
        <Table size="small" pagination={false} rowKey="metric" scroll={{ x: true }} dataSource={filteredRows} columns={columns} />
      </Card>
    </Flex>
  );
}
