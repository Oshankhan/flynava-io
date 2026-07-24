import { useState } from "react";
import { Card, Descriptions, Empty, Flex, Input, Spin, Typography } from "antd";
import { api, ApiError, type AiAnswer } from "../lib/api";
import { linkify } from "../lib/linkify";

const { Paragraph, Text } = Typography;

export default function AskIO() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<AiAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSources, setShowSources] = useState(false);

  async function ask(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setOpen(true);
    setShowSources(false);
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
          {loading && (
            <Flex align="center" justify="center" className="h-10">
              <Spin />
            </Flex>
          )}
          {error && <Empty description={error} />}
          {!loading && answer && (
            <>
              <Paragraph strong className="mb-2">
                {linkify(answer.answer)}
              </Paragraph>
              <Descriptions column={1} size="small" colon>
                <Descriptions.Item label="Why">{linkify(answer.reason)}</Descriptions.Item>
                <Descriptions.Item label="Action">
                  {linkify(answer.recommended_action)}
                </Descriptions.Item>
              </Descriptions>
              {answer.evidence?.length > 0 && (
                <>
                  <Text
                    type="secondary"
                    className="text-xs cursor-pointer hover:underline"
                    onClick={() => setShowSources((s) => !s)}
                  >
                    {showSources ? "Hide sources" : `Show sources (${answer.evidence.length})`}
                  </Text>
                  {showSources && (
                    <ul className="my-1.5 ps-[18px] text-xs opacity-75">
                      {answer.evidence.slice(0, 6).map((e, i) => (
                        <li key={i}>{linkify(e)}</li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </>
          )}
        </Card>
      )}
    </div>
  );
}
