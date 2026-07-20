import type { ReactNode } from "react";
import { Card, Flex, Typography } from "antd";
import { ArrowDownOutlined, ArrowUpOutlined } from "@ant-design/icons";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import type { SuccessCard } from "../../lib/api";
import { formatSuccessValue } from "../../lib/format";
import { STAT_TINT } from "../StatTile";

const { Text } = Typography;

const TINTS: (keyof typeof STAT_TINT)[] = ["teal", "blue", "purple", "amber", "green", "indigo"];
const ACCENT_HEX: Record<keyof typeof STAT_TINT, string> = {
  green: "#059669",
  blue: "#2563eb",
  amber: "#d97706",
  indigo: "#4f46e5",
  teal: "#0d9488",
  purple: "#7c3aed",
};
function tintFor(id: string): keyof typeof STAT_TINT {
  const h = id.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  return TINTS[h % TINTS.length];
}

export default function MiniStatCard({ card, icon }: { card: SuccessCard; icon: ReactNode }) {
  const tint = tintFor(card.id);
  const accent = ACCENT_HEX[tint];
  const points = card.spark ?? [];
  const gradId = `success-spark-${card.id}`;

  return (
    <Card size="small" bordered={false} className="h-full shadow-sm" styles={{ body: { padding: 12 } }}>
      <Flex gap={10} align="center">
        <span
          className={`flex items-center justify-center w-9 h-9 rounded-full text-base shrink-0 ${STAT_TINT[tint]}`}
        >
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-lg font-bold leading-tight">
            {formatSuccessValue(card.value, card.unit)}
          </div>
          <Text type="secondary" className="text-xs">
            {card.label}
          </Text>
          {card.delta_pct != null && card.delta_direction !== "flat" && (
            <div>
              <Text
                className={`text-[11px] font-medium ${card.good ? "text-io-600" : "text-red-600"}`}
              >
                {card.delta_direction === "up" ? <ArrowUpOutlined /> : <ArrowDownOutlined />}{" "}
                {Math.abs(card.delta_pct)}% vs last month
              </Text>
            </div>
          )}
        </div>
      </Flex>
      {points.length >= 3 && (
        <div className="w-full h-7 mt-2 -mx-1">
          <ResponsiveContainer>
            <AreaChart data={points} margin={{ top: 2, bottom: 0, left: 0, right: 0 }}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={accent} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={accent} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="v"
                stroke={accent}
                strokeWidth={2}
                fill={`url(#${gradId})`}
                isAnimationActive={false}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </Card>
  );
}
