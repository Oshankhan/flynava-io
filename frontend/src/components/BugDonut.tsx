import { Card } from "antd";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { BugSlice } from "../lib/api";

const COLORS: Record<string, string> = {
  Closed: "#157f52",
  Resolved: "#1ea562",
  "Replica Done": "#5fd093",
  Developed: "#34c77b",
  Retest: "#95e2b8",
  "In testing": "#7cc8e0",
  "In progress": "#f59e0b",
  "On hold": "#9ca3af",
  Reopen: "#ef7c3c",
  New: "#dc2626",
};
const FALLBACK = ["#0f3f2e", "#34c77b", "#c9f0da", "#fbbf24", "#7cc8e0"];

export default function BugDonut({ data }: { data: BugSlice[] }) {
  const total = data.reduce((s, d) => s + d.count, 0);
  return (
    <Card
      title={`Bugs by Status · ${total} total (live from OpenProject)`}
      size="small"
      bordered={false}
    >
      <div className="w-full h-[260px]">
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
      </div>
    </Card>
  );
}
