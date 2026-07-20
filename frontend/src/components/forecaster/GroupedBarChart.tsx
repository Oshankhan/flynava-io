import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SeriesPoint } from "../../lib/api";

export interface NamedSeries {
  key: string;
  name: string;
  color: string;
  points: SeriesPoint[];
}

/** Grouped/paired bar chart (e.g. joiners vs resigned, cash in vs out) —
 * merges any number of named point series onto a shared month axis. */
export default function GroupedBarChart({
  series,
  height = 220,
}: {
  series: NamedSeries[];
  height?: number;
}) {
  const months = Array.from(new Set(series.flatMap((s) => s.points.map((p) => p.t)))).sort();
  const data = months.map((t) => {
    const row: Record<string, string | number | null> = { t };
    series.forEach((s) => {
      row[s.key] = s.points.find((p) => p.t === t)?.v ?? null;
    });
    return row;
  });

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ left: 4, right: 8, top: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#dfeee6" />
          <XAxis dataKey="t" tick={{ fontSize: 10 }} minTickGap={24} />
          <YAxis tick={{ fontSize: 10 }} width={56} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {series.map((s) => (
            <Bar key={s.key} dataKey={s.key} name={s.name} fill={s.color} radius={[4, 4, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
