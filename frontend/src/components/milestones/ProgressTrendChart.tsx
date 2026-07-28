import { useMemo, useState } from "react";
import { Card, Segmented } from "antd";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MilestoneTrendPoint } from "../../lib/api";

const SERIES = [
  { key: "planned", label: "Planned", color: "#2563eb", dash: "6 4" },
  { key: "actual", label: "Actual", color: "#157f52", dash: undefined },
  { key: "delayed", label: "Delayed", color: "#cf1322", dash: undefined },
] as const;

/** Quarterly is folded from the monthly points the API already returns rather
 * than asking for a second series — the average of a quarter's months is the
 * same number either way, and it keeps the toggle instant. */
function toQuarterly(points: MilestoneTrendPoint[]): MilestoneTrendPoint[] {
  const buckets = new Map<string, MilestoneTrendPoint[]>();
  points.forEach((p) => {
    const [year, month] = (p.month ?? "").split("-");
    const quarter = `${year}-Q${Math.floor((Number(month) - 1) / 3) + 1}`;
    buckets.set(quarter, [...(buckets.get(quarter) ?? []), p]);
  });
  return [...buckets.entries()].map(([quarter, items]) => {
    const avg = (key: "planned" | "actual" | "delayed") =>
      Math.round((items.reduce((sum, i) => sum + (i?.[key] ?? 0), 0) / items.length) * 10) / 10;
    return {
      t: quarter.split("-")[1],
      month: quarter,
      planned: avg("planned"),
      actual: avg("actual"),
      delayed: avg("delayed"),
    };
  });
}

/** Planned vs actual vs delayed, replayed month by month from the approved
 * daily entries. */
export default function ProgressTrendChart({
  title,
  points,
  showGranularity = false,
  height = 260,
}: {
  title: string;
  points: MilestoneTrendPoint[];
  showGranularity?: boolean;
  height?: number;
}) {
  const [granularity, setGranularity] = useState<"monthly" | "quarterly">("monthly");
  const data = useMemo(
    () => (granularity === "quarterly" ? toQuarterly(points ?? []) : points ?? []),
    [granularity, points]
  );

  return (
    <Card
      title={title}
      size="small"
      bordered={false}
      className="h-full"
      extra={
        showGranularity ? (
          <Segmented
            size="small"
            value={granularity}
            onChange={(v) => setGranularity(v as "monthly" | "quarterly")}
            options={[
              { label: "Monthly", value: "monthly" },
              { label: "Quarterly", value: "quarterly" },
            ]}
          />
        ) : undefined
      }
    >
      {/* Recharts needs a resolved pixel height; Tailwind can't express the
          caller-controlled value as a class at build time. */}
      <div style={{ height }} className="w-full">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dfeee6" />
            <XAxis dataKey="t" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} width={40} domain={[0, 100]} unit="%" />
            <Tooltip formatter={(v: number) => `${v}%`} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {SERIES.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                strokeWidth={2}
                strokeDasharray={s.dash}
                dot={{ r: 2 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
