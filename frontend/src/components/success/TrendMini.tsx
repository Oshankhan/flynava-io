import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SeriesPoint } from "../../lib/api";

/** A minimal single-series area chart, decoupled from the KPI engine (unlike
 * the existing `TrendChart`, which expects a full `KpiSeries` object) — used
 * across the Indicator Of Success screens for month/day trend lines. */
export default function TrendMini({
  points,
  color,
}: {
  points: SeriesPoint[];
  color: string;
}) {
  const gradId = `success-trend-${color.replace("#", "")}`;
  return (
    <ResponsiveContainer>
      <AreaChart data={points} margin={{ left: 4, right: 8, top: 8 }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#dfeee6" />
        <XAxis dataKey="t" tick={{ fontSize: 10 }} minTickGap={24} />
        <YAxis tick={{ fontSize: 10 }} width={48} />
        <Tooltip />
        <Area type="monotone" dataKey="v" stroke={color} strokeWidth={2} fill={`url(#${gradId})`} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
