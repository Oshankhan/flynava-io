import { Card } from "antd";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

export interface StatusSlice {
  status: string;
  count: number;
}

const COLORS: Record<string, string> = {
  Completed: "#157f52",
  Closed: "#157f52",
  Resolved: "#1ea562",
  Done: "#1ea562",
  "In Progress": "#f59e0b",
  "In progress": "#f59e0b",
  Pending: "#7cc8e0",
  Open: "#7cc8e0",
  New: "#dc2626",
  Overdue: "#ef4444",
  Reopen: "#ef7c3c",
  "On hold": "#9ca3af",
};
const FALLBACK = ["#0f3f2e", "#34c77b", "#c9f0da", "#fbbf24", "#7cc8e0", "#ef7c3c"];

export default function StatusDonut({
  title,
  data,
  centerLabel,
}: {
  title: string;
  data: StatusSlice[];
  centerLabel?: string;
}) {
  const total = data.reduce((s, d) => s + d.count, 0);
  return (
    <Card title={title} size="small" bordered={false} className="h-full">
      <div className="relative w-full h-[260px]">
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={data}
              dataKey="count"
              nameKey="status"
              innerRadius={58}
              outerRadius={90}
              paddingAngle={2}
            >
              {data.map((d, i) => (
                <Cell key={d.status} fill={COLORS[d.status] ?? FALLBACK[i % FALLBACK.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-x-0 top-[42%] text-center pointer-events-none">
          <div className="text-[22px] font-bold">{total}</div>
          <div className="text-[11px] opacity-65">{centerLabel ?? "Total"}</div>
        </div>
      </div>
    </Card>
  );
}
