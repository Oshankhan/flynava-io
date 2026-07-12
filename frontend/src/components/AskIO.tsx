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
    <div className="relative flex items-center">
      <Input.Search
        aria-label="Ask IO"
        placeholder="Ask IO…  e.g. which projects are at risk?"
        allowClear
        enterButton
        className="w-[180px] sm:w-[260px] md:w-[360px]"
        onSearch={ask}
        onFocus={() => answer && setOpen(true)}
      />
      {open && (loading || answer || error) && (
        <Card
          size="small"
          className="absolute right-0 top-11 w-[calc(100vw-32px)] max-w-[440px] z-[1050] shadow-lg"
          extra={
            <Text
              type="secondary"
              className="cursor-pointer"
              onClick={() => setOpen(false)}
            >
              ✕
            </Text>
          }
          title="Ask IO"
        >
          {loading && <Spin tip="Thinking…"><div className="h-10" /></Spin>}
          {error && <Empty description={error} />}
          {!loading && answer && (
            <>
              <Paragraph strong className="mb-2">
                {answer.answer}
              </Paragraph>
              <Descriptions column={1} size="small" colon>
                <Descriptions.Item label="Why">{answer.reason}</Descriptions.Item>
                <Descriptions.Item label="Action">
                  {answer.recommended_action}
                </Descriptions.Item>
              </Descriptions>
              {answer.evidence?.length > 0 && (
                <ul className="my-1.5 ps-[18px] text-xs opacity-75">
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
