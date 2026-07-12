import { Card, Flex, Typography } from "antd";
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  BugOutlined,
  CheckSquareOutlined,
  ClockCircleOutlined,
  DollarOutlined,
  LineChartOutlined,
  PercentageOutlined,
  ProjectOutlined,
  RocketOutlined,
  SafetyCertificateOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import type { Kpi, KpiSeries } from "../lib/api";
import { formatValue } from "../lib/format";
import RagBadge from "./RagBadge";

const { Text } = Typography;

// A stable accent per KPI — derived from its id so the same KPI always gets
// the same hue (follows the entity, never its position in the list).
const ACCENTS = [
  "#2563eb", "#059669", "#d97706", "#7c3aed",
  "#0d9488", "#dc2626", "#4f46e5", "#db2777",
];
function accentFor(id: string): string {
  const h = id.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  return ACCENTS[h % ACCENTS.length];
}

function iconFor(kpi: Kpi) {
  const s = `${kpi.kpi_id} ${kpi.name}`.toLowerCase();
  if (/bug/.test(s)) return <BugOutlined />;
  if (/project/.test(s)) return <ProjectOutlined />;
  if (/task/.test(s)) return <CheckSquareOutlined />;
  if (/overdue|late|pending|time/.test(s)) return <ClockCircleOutlined />;
  if (/risk|compliance|audit/.test(s)) return <SafetyCertificateOutlined />;
  if (/active|launch|velocity|throughput/.test(s)) return <RocketOutlined />;
  if (/revenue|finance|cost|budget|spend|margin/.test(s)) return <DollarOutlined />;
  if (/closure|rate|conversion|percent/.test(s)) return <PercentageOutlined />;
  if (/head|hire|attrition|staff|team|recruit/.test(s)) return <TeamOutlined />;
  return <LineChartOutlined />;
}

export default function KpiCard({ kpi, series }: { kpi: Kpi; series?: KpiSeries }) {
  const change = kpi.change_pct;
  const good = change != null && (change > 0) === (kpi.direction === "higher");
  const accent = accentFor(kpi.kpi_id);
  const points = kpi.spark ?? series?.points ?? [];
  const gradId = `kpi-spark-${kpi.kpi_id}`;

  return (
    <Card
      size="small"
      bordered={false}
      className="h-full shadow-sm"
      styles={{ body: { display: "flex", flexDirection: "column", height: "100%" } }}
    >
      <Flex justify="space-between" align="center" gap={8}>
        <span
          className="flex items-center justify-center w-8 h-8 rounded-lg text-[15px] shrink-0"
          style={{ backgroundColor: `${accent}1a`, color: accent }}
        >
          {iconFor(kpi)}
        </span>
        <RagBadge rag={kpi.rag} />
      </Flex>

      <Text
        type="secondary"
        className="block text-[12px] font-medium leading-snug mt-2 break-words min-h-[2.4em]"
      >
        {kpi.name}
      </Text>

      <Flex align="baseline" gap={6} wrap className="mt-1">
        <span className="text-[22px] font-bold text-io-900 leading-none">
          {formatValue(kpi.value, kpi.unit)}
        </span>
        {change != null && change !== 0 && (
          <span
            data-testid="kpi-change"
            className={`text-[12px] font-semibold ${good ? "text-io-600" : "text-red-600"}`}
          >
            {change > 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {Math.abs(change)}%
          </span>
        )}
      </Flex>

      {kpi.target != null && (
        <Text type="secondary" className="block text-[11px] leading-tight mt-0.5">
          Target {formatValue(kpi.target, kpi.unit)} ·{" "}
          {kpi.direction === "higher" ? "higher" : "lower"} is better
        </Text>
      )}

      {points.length >= 3 && (
        <div className="w-full h-8 mt-auto pt-2 -mx-1">
          <ResponsiveContainer>
            <AreaChart data={points} margin={{ top: 2, bottom: 0, left: 0, right: 0 }}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={accent} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={accent} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="v"
                stroke={accent}
                strokeWidth={2}
                fill={`url(#${gradId})`}
                isAnimationActive={false}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}
