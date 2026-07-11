import { Card } from "antd";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { KpiSeries } from "../lib/api";
import { BRAND } from "../lib/brand";

export default function TrendChart({ series }: { series: KpiSeries }) {
  return (
    <Card title={`${series.name} · 12-month trend`} size="small" bordered={false}>
      <div style={{ width: "100%", height: 180 }}>
        <ResponsiveContainer>
          <AreaChart data={series.points} margin={{ left: 8, right: 8, top: 8 }}>
            <defs>
              <linearGradient id={`g-${series.kpi_id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={BRAND.accent} stopOpacity={0.35} />
                <stop offset="100%" stopColor={BRAND.accent} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#dfeee6" />
            <XAxis dataKey="t" tick={{ fontSize: 10 }} minTickGap={24} />
            <YAxis tick={{ fontSize: 10 }} width={56} />
            <Tooltip />
            <Area
              type="monotone"
              dataKey="v"
              name={series.name}
              stroke={BRAND.primary}
              strokeWidth={2}
              fill={`url(#g-${series.kpi_id})`}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
