import { Card, Flex, Typography } from "antd";

const { Text } = Typography;

export const STAT_TINT = {
  green: "bg-emerald-500/15 text-emerald-600",
  blue: "bg-blue-500/15 text-blue-600",
  amber: "bg-amber-500/15 text-amber-600",
  indigo: "bg-indigo-500/15 text-indigo-600",
  teal: "bg-teal-500/15 text-teal-600",
  purple: "bg-purple-500/15 text-purple-600",
} as const;

export default function StatTile({
  icon, tint, value, label, sub, subTone,
}: {
  icon: React.ReactNode; tint: keyof typeof STAT_TINT; value: string; label: string;
  sub?: string; subTone?: "up" | "warn" | "muted";
}) {
  const subColor = subTone === "up" ? "text-io-600" : subTone === "warn" ? "text-amber-600" : undefined;
  return (
    <Card size="small" bordered={false} className="h-full shadow-sm" styles={{ body: { padding: 12 } }}>
      <Flex gap={10} align="center">
        <span className={`flex items-center justify-center w-9 h-9 rounded-full text-base shrink-0 ${STAT_TINT[tint]}`}>
          {icon}
        </span>
        <div className="min-w-0">
          <div className="text-xl font-bold leading-tight">{value}</div>
          <Text type="secondary" className="text-xs">{label}</Text>
          {sub && <div><Text className={`text-[11px] ${subColor ?? "text-gray-400"}`}>{sub}</Text></div>}
        </div>
      </Flex>
    </Card>
  );
}
