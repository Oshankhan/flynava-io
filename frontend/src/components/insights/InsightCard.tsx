import type { KeyboardEvent, MouseEvent } from "react";
import { LikeFilled, LikeOutlined, DislikeFilled, DislikeOutlined, MessageOutlined } from "@ant-design/icons";
import { Button, Card, Descriptions, Flex, Tag, Typography } from "antd";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { AiAnswer, InsightCard as InsightCardData, InsightEntity } from "../../lib/api";
import { BRAND } from "../../lib/brand";
import { openInayaWithAnswer } from "../InayaChat";
import { useAsyncAction } from "../../lib/useAsyncAction";

const { Paragraph, Text } = Typography;

const SEVERITY_COLOR: Record<string, string> = {
  high: "error",
  medium: "warning",
  low: "processing",
  info: "default",
};
const CONF_COLOR: Record<string, string> = {
  High: "success",
  Medium: "warning",
  Low: "error",
};

function metricText(value: number | string, unit?: string): string {
  if (typeof value !== "number") return String(value);
  if (unit === "USD") return `$${value.toLocaleString()}`;
  if (unit === "%") return `${value}%`;
  return value.toLocaleString();
}

function toInayaAnswer(card: InsightCardData): AiAnswer {
  return {
    answer: card.answer,
    reason: card.reason,
    evidence: card.evidence,
    recommended_action: card.recommended_action,
    confidence: card.confidence,
    last_updated: card.generated_at,
  };
}

function entityText(e: InsightEntity): string {
  const extra = Object.entries(e.extra ?? {})
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`)
    .join(" · ");
  // Only prefix with the id when it's a real, distinct reference behind a
  // link (e.g. an OpenProject work-package number) — several detectors
  // (overburdened, late-clients, ...) set id === label (a person/client
  // name standing in for a real id), which would otherwise double the name.
  const idPrefix = e.url && e.id ? `#${e.id} ` : "";
  const text = `${idPrefix}${e.label ?? ""}`;
  return extra ? `${text} (${extra})` : text;
}

export default function InsightCard({
  card,
  onVote,
}: {
  card: InsightCardData;
  onVote: (insightId: string, useful: boolean) => Promise<void>;
}) {
  const [vote, voting] = useAsyncAction((useful: boolean) => onVote(card.insight_id, useful));

  function openInInaya() {
    openInayaWithAnswer(card.title, toInayaAnswer(card));
  }

  return (
    <Card
      size="small"
      bordered={false}
      hoverable
      className="h-full shadow-sm cursor-pointer"
      role="button"
      tabIndex={0}
      aria-label={`Ask Inaya about: ${card.title}`}
      onClick={openInInaya}
      onKeyDown={(e: KeyboardEvent) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openInInaya();
        }
      }}
    >
      <Flex justify="space-between" align="start" gap={8}>
        <Text strong className="text-[13px] leading-snug">
          {card.title}
        </Text>
        <Tag color={SEVERITY_COLOR[card.severity] ?? "default"} className="me-0 shrink-0">
          {card.severity}
        </Tag>
      </Flex>

      <Paragraph strong className="!mb-2 !mt-2 text-[13px]">
        {card.answer}
      </Paragraph>

      <Descriptions column={1} size="small" colon>
        <Descriptions.Item label="Why">{card.reason}</Descriptions.Item>
        <Descriptions.Item label="Action">{card.recommended_action}</Descriptions.Item>
      </Descriptions>

      {card.metrics.length > 0 && (
        <Flex gap={6} wrap className="mt-2">
          {card.metrics.map((m, i) => (
            <span
              key={i}
              className="text-[11px] rounded-full px-2 py-0.5 bg-gray-100 dark:bg-white/10 text-gray-600 dark:text-gray-300"
            >
              {m.label}: <strong>{metricText(m.value, m.unit)}</strong>
            </span>
          ))}
        </Flex>
      )}

      {card.chart && card.chart.points.length > 0 && (
        <div className="w-full h-[110px] mt-2">
          <ResponsiveContainer>
            <BarChart data={card.chart.points} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-15} textAnchor="end" height={30} />
              <YAxis tick={{ fontSize: 10 }} width={40} />
              <Tooltip />
              <Bar dataKey="value" fill={BRAND.primary} radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {card.entities.length > 0 ? (
        <ul className="my-2 ps-[18px] text-xs opacity-75">
          {card.entities.slice(0, 6).map((e, i) => (
            <li key={e.id ?? i}>
              {e.url ? (
                <a
                  href={e.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-io-600 hover:underline"
                  onClick={(ev: MouseEvent) => ev.stopPropagation()}
                >
                  {entityText(e)}
                </a>
              ) : (
                entityText(e)
              )}
            </li>
          ))}
        </ul>
      ) : (
        card.evidence.length > 0 && (
          <ul className="my-2 ps-[18px] text-xs opacity-75">
            {card.evidence.slice(0, 6).map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        )
      )}

      <Flex justify="space-between" align="center" wrap gap={8} className="mt-2">
        <Flex gap={6} align="center" wrap>
          <Tag color={CONF_COLOR[card.confidence] ?? "default"} className="me-0">
            Confidence: {card.confidence}
          </Tag>
          <Text type="secondary" className="text-[11px]">
            via {card.ai_provider}
          </Text>
          <Text type="secondary" className="text-[11px]">
            <MessageOutlined /> Ask Inaya
          </Text>
        </Flex>
        <Flex gap={4} onClick={(e: MouseEvent) => e.stopPropagation()}>
          <Button
            size="small"
            type="text"
            loading={voting}
            icon={card.feedback.mine === true ? <LikeFilled /> : <LikeOutlined />}
            onClick={() => vote(true)}
            aria-label="Mark useful"
          >
            {card.feedback.useful}
          </Button>
          <Button
            size="small"
            type="text"
            loading={voting}
            icon={card.feedback.mine === false ? <DislikeFilled /> : <DislikeOutlined />}
            onClick={() => vote(false)}
            aria-label="Mark not useful"
          >
            {card.feedback.not_useful}
          </Button>
        </Flex>
      </Flex>
    </Card>
  );
}
