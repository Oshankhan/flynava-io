import type { ReactNode } from "react";
import { Card, Flex, Typography } from "antd";
import { ArrowDownOutlined, ArrowRightOutlined, ArrowUpOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import type { SuccessCard } from "../../lib/api";
import { formatSuccessValue } from "../../lib/format";
import { STAT_TINT } from "../StatTile";

const { Text } = Typography;

const TINTS: (keyof typeof STAT_TINT)[] = ["blue", "green", "amber", "indigo", "teal", "purple"];
function tintFor(id: string): keyof typeof STAT_TINT {
  const h = id.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  return TINTS[h % TINTS.length];
}

export default function HeroKpiCard({
  card,
  icon,
  linkLabel = "View Trend",
  deltaLabel = "vs last month",
}: {
  card: SuccessCard;
  icon: ReactNode;
  linkLabel?: string;
  /** What the delta_pct is actually measured against — defaults to the
   * month-over-month framing every other card uses, but forecast cards
   * (FY total vs current annualized run-rate) need to say so explicitly. */
  deltaLabel?: string;
}) {
  const tint = tintFor(card.id);
  return (
    <Card size="small" bordered={false} className="h-full shadow-sm">
      <Flex vertical gap={6}>
        <span
          className={`flex items-center justify-center w-9 h-9 rounded-full text-base shrink-0 ${STAT_TINT[tint]}`}
        >
          {icon}
        </span>
        <Text type="secondary" className="text-xs font-medium uppercase tracking-wide">
          {card.label}
        </Text>
        <Flex align="baseline" gap={8} wrap>
          <span className="text-2xl font-bold text-io-900 leading-none">
            {formatSuccessValue(card.value, card.unit)}
          </span>
          {card.delta_pct != null && card.delta_direction !== "flat" && (
            <span
              className={`text-xs font-semibold ${card.good ? "text-io-600" : "text-red-600"}`}
            >
              {card.delta_direction === "up" ? <ArrowUpOutlined /> : <ArrowDownOutlined />}{" "}
              {Math.abs(card.delta_pct)}%
            </span>
          )}
        </Flex>
        <Text type="secondary" className="text-[11px]">
          {deltaLabel}
        </Text>
        {card.link && (
          <Link
            to={card.link}
            className="text-xs font-medium text-io-600 inline-flex items-center gap-1 mt-1"
          >
            {linkLabel} <ArrowRightOutlined className="text-[10px]" />
          </Link>
        )}
      </Flex>
    </Card>
  );
}
