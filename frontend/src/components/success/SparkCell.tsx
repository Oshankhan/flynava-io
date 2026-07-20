import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { BRAND } from "../../lib/brand";
import type { SeriesPoint } from "../../lib/api";

export default function SparkCell({
  points,
}: {
  points?: SeriesPoint[] | number[] | null;
}) {
  if (!points || points.length < 2) return <span className="text-gray-400">—</span>;
  const data: { v: number }[] =
    typeof points[0] === "number"
      ? (points as number[]).map((v) => ({ v }))
      : (points as SeriesPoint[]).map((p) => ({ v: p.v }));

  return (
    <div className="w-20 h-6">
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 2, bottom: 0, left: 0, right: 0 }}>
          <Area
            type="monotone"
            dataKey="v"
            stroke={BRAND.primary}
            strokeWidth={1.5}
            fill={BRAND.primary}
            fillOpacity={0.15}
            isAnimationActive={false}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
