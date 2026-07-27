import { useEffect, useState } from "react";
import { Alert, Descriptions, Drawer, Empty, Flex, Spin, Table, Tag, Typography } from "antd";
import { api, ApiError, type KpiExplainEvidence, type KpiExplanation } from "../lib/api";
import { formatValue } from "../lib/format";
import RagBadge from "./RagBadge";
import TrendChart from "./TrendChart";

const { Title, Paragraph, Text } = Typography;

const CONF_COLOR: Record<string, string> = {
  High: "success",
  Medium: "warning",
  Low: "error",
};

function extraText(e: KpiExplainEvidence): string {
  const extra = e.extra ?? {};
  return Object.entries(extra)
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`)
    .join(" · ");
}

export default function KpiExplainDrawer({
  kpiId,
  onClose,
}: {
  kpiId: string | null;
  onClose: () => void;
}) {
  const [data, setData] = useState<KpiExplanation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!kpiId) return;
    let alive = true;
    setData(null);
    setError(null);
    setLoading(true);
    api
      .explainKpi(kpiId)
      .then((d) => alive && setData(d))
      .catch((err) => alive && setError(err instanceof ApiError ? err.message : "Load failed"))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [kpiId]);

  return (
    <Drawer
      title="Why this number?"
      open={kpiId != null}
      onClose={onClose}
      width={560}
      className="max-w-full"
    >
      {loading && (
        <Flex align="center" justify="center" className="min-h-[240px]">
          <Spin size="large" />
        </Flex>
      )}
      {error && <Alert type="error" showIcon message="Cannot load explanation" description={error} />}

      {!loading && !error && data && (
        <Flex vertical gap={20}>
          <div>
            <Text type="secondary" className="block text-[13px] font-medium">
              {data.name}
            </Text>
            <Flex align="baseline" gap={10} wrap className="mt-1">
              <span className="text-[28px] font-bold text-io-900 leading-none">
                {formatValue(data.value, data.unit)}
              </span>
              <RagBadge rag={data.rag} />
            </Flex>
            {data.target != null && (
              <Text type="secondary" className="block text-[12px] mt-1">
                Target {formatValue(data.target, data.unit)} ·{" "}
                {data.direction === "higher" ? "higher" : "lower"} is better
              </Text>
            )}
          </div>

          <div>
            <Title level={5} className="!mb-2">
              How this number is computed
            </Title>
            <Paragraph className="!mb-2 text-[13px]">{data.formula_text}</Paragraph>
            <Paragraph
              strong
              className="!mb-0 text-[13px] bg-gray-50 dark:bg-white/5 rounded-lg px-3 py-2"
            >
              {data.computation}
            </Paragraph>
          </div>

          {!!data.evidence?.length && (
            <div>
              <Title level={5} className="!mb-2">
                Evidence ({(data.evidence?.length ?? 0)}
                {(data.evidence?.length ?? 0) >= 15 ? "+" : ""} record
                {(data.evidence?.length ?? 0) === 1 ? "" : "s"})
              </Title>
              <Table<KpiExplainEvidence>
                size="small"
                pagination={false}
                rowKey={(r) => r.id ?? `${r.kind}-${r.label}`}
                dataSource={data.evidence}
                scroll={{ y: 280 }}
                columns={[
                  { title: "Kind", dataIndex: "kind", width: 70,
                    render: (v: string) => <Tag className="me-0">{v}</Tag> },
                  {
                    title: "Record", dataIndex: "label",
                    render: (label: string, r) => {
                      // Only show the id when it's a real link behind it —
                      // otherwise it's just the row's own name/label again
                      // (e.g. static-KPI evidence has no distinct id at all).
                      const text = r.url && r.id ? `#${r.id} ${label}` : label;
                      return r.url ? (
                        <a href={r.url} target="_blank" rel="noopener noreferrer"
                           className="text-io-600 hover:underline">
                          {text}
                        </a>
                      ) : (
                        text
                      );
                    },
                  },
                  { title: "Detail", key: "extra", render: (_, r) => extraText(r) },
                ]}
              />
            </div>
          )}

          <div>
            <Title level={5} className="!mb-2">
              Source & freshness
            </Title>
            <Descriptions column={1} size="small" colon>
              <Descriptions.Item label="System">
                <Tag color={data.source.live ? "success" : "default"}>{data.source.system}</Tag>
                {data.source.collection && (
                  <Text type="secondary" className="text-[12px]">
                    {" "}
                    → <code>{data.source.collection}</code>
                  </Text>
                )}
              </Descriptions.Item>
              {data.source.last_sync && (
                <Descriptions.Item label="Last synced">
                  {new Date(data.source.last_sync).toLocaleString()}
                </Descriptions.Item>
              )}
              <Descriptions.Item label="Note">
                <Text type="secondary" className="text-[12px]">
                  {data.source.note}
                </Text>
              </Descriptions.Item>
            </Descriptions>
          </div>

          <div>
            <Title level={5} className="!mb-2">
              AI explanation
            </Title>
            <Paragraph strong className="!mb-2 text-[13px]">
              {data.answer}
            </Paragraph>
            <Descriptions column={1} size="small" colon>
              <Descriptions.Item label="Why">{data.reason}</Descriptions.Item>
              <Descriptions.Item label="Recommended action">
                {data.recommended_action}
              </Descriptions.Item>
            </Descriptions>
            <Flex gap={8} wrap className="mt-2">
              <Tag color={CONF_COLOR[data.confidence] ?? "default"}>
                Confidence: {data.confidence}
              </Tag>
              <Tag className="me-0">via {data.ai_provider}</Tag>
              <Text type="secondary" className="text-[11px]">
                Generated {new Date(data.generated_at).toLocaleString()}
              </Text>
            </Flex>
          </div>

          {(data.history?.length ?? 0) >= 3 && (
            <TrendChart
              series={{ kpi_id: data.kpi_id, name: data.name, unit: data.unit, points: data.history }}
            />
          )}
        </Flex>
      )}

      {!loading && !error && !data && <Empty description="No explanation available" />}
    </Drawer>
  );
}
