import { Card } from "antd";
import {
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { ResourceTeamCapacity } from "../../lib/api";
import { ragHex, TEAM_STATUS_RAG } from "./statusColors";

export default function PerformanceMatrix({ rows }: { rows: ResourceTeamCapacity[] }) {
  const points = rows.map((r) => ({
    name: r.name,
    x: r.utilization_pct,
    y: r.completion_pct,
    status: r.status,
  }));

  return (
    <Card size="small" bordered={false} className="h-full shadow-sm" title="Team Performance Matrix">
      <div className="w-full h-[260px]">
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 8, right: 16, bottom: 8, left: -8 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-white/10" />
            <XAxis
              type="number"
              dataKey="x"
              name="Workload / Utilization"
              unit="%"
              tick={{ fontSize: 10 }}
              domain={[0, "dataMax + 20"]}
            />
            <YAxis
              type="number"
              dataKey="y"
              name="Task Completion"
              unit="%"
              tick={{ fontSize: 10 }}
              domain={[0, 100]}
            />
            <ZAxis range={[120, 120]} />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const p = payload[0].payload as (typeof points)[number];
                return (
                  <div className="rounded-md bg-white dark:bg-gray-800 shadow px-2 py-1 text-xs border border-gray-100 dark:border-white/10">
                    <div className="font-medium">{p.name}</div>
                    <div>Utilization: {p.x}%</div>
                    <div>Completion: {p.y}%</div>
                  </div>
                );
              }}
            />
            <Scatter data={points} shape="circle">
              {points.map((p, i) => (
                <Cell key={i} fill={ragHex(TEAM_STATUS_RAG[p.status])} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-1 flex flex-wrap gap-2">
        {points.map((p) => (
          <span key={p.name} className="text-[11px] text-gray-500 dark:text-gray-400">
            {p.name}
          </span>
        ))}
      </div>
    </Card>
  );
}
