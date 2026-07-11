import { useState } from "react";
import { Card, Descriptions, Empty, Input, Spin, Tag, Typography } from "antd";
import { api, ApiError, type AiAnswer } from "../lib/api";

const { Paragraph, Text } = Typography;
const CONF_COLOR: Record<string, string> = {
  High: "success",
  Medium: "warning",
  Low: "error",
};

export default function AskIO() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<AiAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function ask(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setOpen(true);
    try {
      setAnswer(await api.askIO(q));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ask IO failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
      <Input.Search
        aria-label="Ask IO"
        placeholder="Ask IO…  e.g. which projects are at risk?"
        allowClear
        enterButton
        style={{ width: 360 }}
        onSearch={ask}
        onFocus={() => answer && setOpen(true)}
      />
      {open && (loading || answer || error) && (
        <Card
          size="small"
          style={{
            position: "absolute",
            right: 0,
            top: 44,
            width: 440,
            zIndex: 1050,
            boxShadow: "0 8px 24px rgba(0,0,0,0.18)",
          }}
          extra={
            <Text
              type="secondary"
              style={{ cursor: "pointer" }}
              onClick={() => setOpen(false)}
            >
              ✕
            </Text>
          }
          title="Ask IO"
        >
          {loading && <Spin tip="Thinking…"><div style={{ height: 40 }} /></Spin>}
          {error && <Empty description={error} />}
          {!loading && answer && (
            <>
              <Paragraph strong style={{ marginBottom: 8 }}>
                {answer.answer}
              </Paragraph>
              <Descriptions column={1} size="small" colon>
                <Descriptions.Item label="Why">{answer.reason}</Descriptions.Item>
                <Descriptions.Item label="Action">
                  {answer.recommended_action}
                </Descriptions.Item>
              </Descriptions>
              {answer.evidence?.length > 0 && (
                <ul style={{ margin: "6px 0", paddingInlineStart: 18, fontSize: 12, opacity: 0.75 }}>
                  {answer.evidence.slice(0, 6).map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              )}
              <Tag color={CONF_COLOR[answer.confidence] ?? "default"}>
                Confidence: {answer.confidence}
              </Tag>
            </>
          )}
        </Card>
      )}
    </div>
  );
}
