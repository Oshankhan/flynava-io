import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  Avatar,
  Button,
  Card,
  Descriptions,
  Flex,
  Input,
  Spin,
  Tag,
  Typography,
} from "antd";
import { CommentOutlined, SendOutlined, UserOutlined } from "@ant-design/icons";
import { api, ApiError, type AiAnswer } from "../lib/api";
import { BRAND } from "../lib/brand";

const { Paragraph, Text } = Typography;

interface ChatTurn {
  q: string;
  a?: AiAnswer;
  error?: string;
}

const CONF_COLOR: Record<string, string> = {
  High: "success",
  Medium: "warning",
  Low: "error",
};

const SUGGESTIONS = [
  "Show me my overdue tasks",
  "What are my reopened bugs?",
  "How is the team performing?",
  "Which projects are at risk?",
  "Summarize compliance deadlines",
];

export default function AIWorkspace() {
  const location = useLocation();
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const asked = useRef(false);

  async function ask(question: string) {
    const text = question.trim();
    if (!text || busy) return;
    setBusy(true);
    setQ("");
    setTurns((t) => [...t, { q: text }]);
    try {
      const a = await api.askIO(text);
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, a } : x)));
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Ask IO failed";
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error: msg } : x)));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    const st = location.state as { q?: string } | null;
    if (st?.q && !asked.current) {
      asked.current = true;
      ask(st.q);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy]);

  return (
    <Flex vertical style={{ height: "calc(100vh - 130px)" }}>
      <div style={{ flex: 1, overflowY: "auto", paddingRight: 4 }}>
        {turns.length === 0 && (
          <Card bordered={false} style={{ textAlign: "center", marginTop: 40 }}>
            <CommentOutlined style={{ fontSize: 34, color: BRAND.primary }} />
            <Paragraph strong style={{ marginTop: 12 }}>
              Ask IO anything about your work
            </Paragraph>
            <Flex gap={8} wrap justify="center">
              {SUGGESTIONS.map((s) => (
                <Button key={s} size="small" onClick={() => ask(s)}>
                  {s}
                </Button>
              ))}
            </Flex>
          </Card>
        )}
        {turns.map((t, i) => (
          <div key={i} style={{ marginBottom: 16 }}>
            <Flex gap={8} justify="flex-end" style={{ marginBottom: 8 }}>
              <Card size="small" style={{ maxWidth: "75%", background: `${BRAND.primary}14` }} bordered={false}>
                <Text>{t.q}</Text>
              </Card>
              <Avatar size="small" icon={<UserOutlined />} style={{ background: BRAND.primary, flexShrink: 0 }} />
            </Flex>
            {(t.a || t.error || (i === turns.length - 1 && busy)) && (
              <Flex gap={8}>
                <Avatar size="small" style={{ background: "#0f3f2e", flexShrink: 0, fontSize: 10, fontWeight: 700 }}>IO</Avatar>
                <Card size="small" style={{ maxWidth: "80%" }} bordered={false}>
                  {i === turns.length - 1 && busy && !t.a && !t.error ? (
                    <Spin size="small" />
                  ) : t.error ? (
                    <Text type="danger">{t.error}</Text>
                  ) : t.a ? (
                    <>
                      <Paragraph strong style={{ marginBottom: 8 }}>
                        {t.a.answer}
                      </Paragraph>
                      <Descriptions column={1} size="small" colon>
                        <Descriptions.Item label="Why">{t.a.reason}</Descriptions.Item>
                        <Descriptions.Item label="Action">{t.a.recommended_action}</Descriptions.Item>
                      </Descriptions>
                      {t.a.evidence?.length > 0 && (
                        <ul style={{ margin: "6px 0", paddingInlineStart: 18, fontSize: 12, opacity: 0.75 }}>
                          {t.a.evidence.slice(0, 6).map((e, j) => (
                            <li key={j}>{e}</li>
                          ))}
                        </ul>
                      )}
                      <Tag color={CONF_COLOR[t.a.confidence] ?? "default"}>
                        Confidence: {t.a.confidence}
                      </Tag>
                    </>
                  ) : null}
                </Card>
              </Flex>
            )}
          </div>
        ))}
        <div ref={bottom} />
      </div>
      <Flex gap={8} style={{ marginTop: 12 }}>
        <Input
          size="large"
          placeholder="Ask IO…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onPressEnter={() => ask(q)}
          disabled={busy}
        />
        <Button
          size="large"
          type="primary"
          icon={<SendOutlined />}
          onClick={() => ask(q)}
          loading={busy}
        />
      </Flex>
    </Flex>
  );
}
