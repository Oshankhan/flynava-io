import { useEffect, useRef, useState } from "react";
import { Avatar, Button, Card, Descriptions, Flex, Input, Spin, Tag, Typography } from "antd";
import { CloseOutlined, SendOutlined } from "@ant-design/icons";
import { api, ApiError, type AiAnswer } from "../lib/api";
import { BRAND } from "../lib/brand";
import inayaImg from "../assets/inaya/Inaya-img.png";

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
];

export const INAYA_OPEN_EVENT = "inaya:open";

export default function InayaChat() {
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onOpen = () => setOpen(true);
    window.addEventListener(INAYA_OPEN_EVENT, onOpen);
    return () => window.removeEventListener(INAYA_OPEN_EVENT, onOpen);
  }, []);

  useEffect(() => {
    if (open) bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy, open]);

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
      const msg = e instanceof ApiError ? e.message : "Inaya couldn't answer that";
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { ...x, error: msg } : x)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {open && (
        <Card
          size="small"
          style={{
            position: "fixed",
            bottom: 88,
            right: 24,
            width: 380,
            height: 560,
            zIndex: 1000,
            boxShadow: "0 12px 32px rgba(0,0,0,0.22)",
            display: "flex",
            flexDirection: "column",
          }}
          styles={{ body: { display: "flex", flexDirection: "column", height: "100%", padding: 12 } }}
          title={
            <Flex align="center" gap={8}>
              <Avatar size={26} src={inayaImg} />
              <span>Inaya</span>
            </Flex>
          }
          extra={<Button type="text" size="small" icon={<CloseOutlined />} onClick={() => setOpen(false)} />}
        >
          <div style={{ flex: 1, overflowY: "auto", paddingRight: 4 }}>
            {turns.length === 0 && (
              <Card bordered={false} style={{ textAlign: "center", marginTop: 24 }}>
                <Avatar size={48} src={inayaImg} />
                <Paragraph strong style={{ marginTop: 12 }}>
                  Hi, I'm Inaya. Ask me anything about your work.
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
              <div key={i} style={{ marginBottom: 14 }}>
                <Flex gap={8} justify="flex-end" style={{ marginBottom: 8 }}>
                  <Card size="small" style={{ maxWidth: "80%", background: `${BRAND.primary}14` }} bordered={false}>
                    <Text style={{ fontSize: 13 }}>{t.q}</Text>
                  </Card>
                </Flex>
                {(t.a || t.error || (i === turns.length - 1 && busy)) && (
                  <Flex gap={8}>
                    <Avatar size="small" src={inayaImg} style={{ flexShrink: 0 }} />
                    <Card size="small" style={{ maxWidth: "85%" }} bordered={false}>
                      {i === turns.length - 1 && busy && !t.a && !t.error ? (
                        <Spin size="small" />
                      ) : t.error ? (
                        <Text type="danger">{t.error}</Text>
                      ) : t.a ? (
                        <>
                          <Paragraph strong style={{ marginBottom: 8, fontSize: 13 }}>
                            {t.a.answer}
                          </Paragraph>
                          <Descriptions column={1} size="small" colon>
                            <Descriptions.Item label="Why">{t.a.reason}</Descriptions.Item>
                            <Descriptions.Item label="Action">{t.a.recommended_action}</Descriptions.Item>
                          </Descriptions>
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
          <Flex gap={8} style={{ marginTop: 10 }}>
            <Input
              placeholder="Ask Inaya…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onPressEnter={() => ask(q)}
              disabled={busy}
            />
            <Button type="primary" icon={<SendOutlined />} onClick={() => ask(q)} loading={busy} />
          </Flex>
        </Card>
      )}

      <Button
        shape="circle"
        onClick={() => setOpen((o) => !o)}
        style={{
          position: "fixed",
          bottom: 24,
          right: 24,
          width: 56,
          height: 56,
          zIndex: 1000,
          padding: 0,
          boxShadow: "0 8px 20px rgba(0,0,0,0.25)",
          border: `2px solid ${BRAND.primary}`,
        }}
      >
        <img src={inayaImg} alt="Inaya" style={{ width: "100%", height: "100%", objectFit: "cover", borderRadius: "50%" }} />
      </Button>
    </>
  );
}
