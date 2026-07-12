import { Card } from "antd";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Kpi } from "../lib/api";
import { BRAND } from "../lib/brand";

export default function KpiBarChart({ kpis }: { kpis: Kpi[] }) {
  const data = kpis
    .filter((k) => k.value != null)
    .map((k) => ({ name: k.name, value: k.value as number }));
  if (!data.length) return null;
  return (
    <Card title="KPI Overview" size="small" bordered={false}>
      <div className="w-full h-[280px]">
        <ResponsiveContainer>
          <BarChart data={data} margin={{ left: 8, right: 8, top: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#dfeee6" />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11 }}
              interval={0}
              height={60}
              angle={-15}
              textAnchor="end"
            />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Bar dataKey="value" fill={BRAND.accent} radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
