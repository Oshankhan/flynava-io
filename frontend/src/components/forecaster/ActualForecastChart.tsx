import { Card } from "antd";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SeriesPoint } from "../../lib/api";
import { BRAND } from "../../lib/brand";

/** Renders actual (solid area) alongside forecast (dashed line) on one
 * timeline — never joins them into a single misleading line. `actual` and
 * `forecast` may cover different or overlapping month ranges; each series
 * simply has gaps where it has no data for a given point on the x-axis. */
export default function ActualForecastChart({
  title,
  actual,
  forecast,
  height = 220,
}: {
  title?: string;
  actual: SeriesPoint[];
  forecast: SeriesPoint[];
  height?: number;
}) {
  const months = Array.from(new Set([...actual.map((p) => p.t), ...forecast.map((p) => p.t)])).sort();
  const actualByMonth = Object.fromEntries(actual.map((p) => [p.t, p.v]));
  const forecastByMonth = Object.fromEntries(forecast.map((p) => [p.t, p.v]));
  const data = months.map((t) => ({ t, actual: actualByMonth[t], forecast: forecastByMonth[t] }));

  const chart = (
    <ResponsiveContainer>
      <ComposedChart data={data} margin={{ left: 4, right: 8, top: 8 }}>
        <defs>
          <linearGradient id="forecaster-af-actual" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={BRAND.primary} stopOpacity={0.3} />
            <stop offset="100%" stopColor={BRAND.primary} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#dfeee6" />
        <XAxis dataKey="t" tick={{ fontSize: 10 }} minTickGap={24} />
        <YAxis tick={{ fontSize: 10 }} width={56} />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Area
          type="monotone"
          dataKey="actual"
          name="Actual"
          stroke={BRAND.primary}
          strokeWidth={2}
          fill="url(#forecaster-af-actual)"
          connectNulls={false}
        />
        <Line
          type="monotone"
          dataKey="forecast"
          name="Forecast"
          stroke="#7c3aed"
          strokeWidth={2}
          strokeDasharray="5 4"
          dot={false}
          connectNulls={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );

  if (!title) return <div style={{ height }} className="w-full">{chart}</div>;
  return (
    <Card title={title} size="small" bordered={false} className="h-full">
      <div style={{ height }} className="w-full">
        {chart}
      </div>
    </Card>
  );
}
