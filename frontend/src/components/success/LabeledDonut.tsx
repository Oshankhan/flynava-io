import { Card, Flex, Typography } from "antd";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { BRAND } from "../../lib/brand";

const { Text } = Typography;

const PALETTE = [
  BRAND.green[0], BRAND.green[1], BRAND.green[2],
  "#f59e0b", "#7cc8e0", "#9ca3af", "#ef7c3c",
];

export interface DonutSlice {
  label: string;
  value: number;
}

export default function LabeledDonut({
  title,
  slices,
  centerLabel,
  centerValue,
  formatValue,
}: {
  title: string;
  slices: DonutSlice[];
  centerLabel?: string;
  /** Overrides the center number (defaults to the sum of `slices`) — e.g. an
   * "overall progress %" that isn't simply the total of the slice values. */
  centerValue?: string;
  formatValue?: (v: number) => string;
}) {
  const total = slices.reduce((s, d) => s + d.value, 0);
  const fmt = formatValue ?? ((v: number) => v.toLocaleString());

  return (
    <Card title={title} size="small" bordered={false} className="h-full">
      <Flex align="center" gap={12} wrap>
        <div className="relative w-[160px] h-[160px] shrink-0 mx-auto sm:mx-0">
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={slices}
                dataKey="value"
                nameKey="label"
                innerRadius={48}
                outerRadius={76}
                paddingAngle={2}
              >
                {slices.map((s, i) => (
                  <Cell key={s.label} fill={PALETTE[i % PALETTE.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v: number) => fmt(v)} />
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <div className="text-lg font-bold">{centerValue ?? fmt(total)}</div>
            <div className="text-[11px] opacity-65">{centerLabel ?? "Total"}</div>
          </div>
        </div>
        <div className="flex-1 min-w-[140px]">
          {slices.map((s, i) => (
            <Flex key={s.label} align="center" justify="space-between" gap={8} className="py-1">
              <Flex align="center" gap={6} className="min-w-0">
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: PALETTE[i % PALETTE.length] }}
                />
                <Text className="text-xs truncate">{s.label}</Text>
              </Flex>
              <Text type="secondary" className="text-xs whitespace-nowrap">
                {fmt(s.value)} ({total ? Math.round((s.value / total) * 100) : 0}%)
              </Text>
            </Flex>
          ))}
        </div>
      </Flex>
    </Card>
  );
}
