import { useEffect, useRef, useState } from "react";
import { Avatar, Button, Card, Descriptions, Flex, Input, Spin, Tag, Typography } from "antd";
import { CloseOutlined, SendOutlined } from "@ant-design/icons";
import { api, ApiError, type AiAnswer } from "../lib/api";
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
          className="fixed inset-x-4 bottom-24 sm:inset-x-auto sm:bottom-[88px] sm:right-6 w-auto sm:w-[380px] h-[70vh] max-h-[560px] sm:h-[560px] z-[1000] shadow-2xl flex flex-col"
          styles={{ body: { display: "flex", flexDirection: "column", height: "100%", padding: 12 } }}
          title={
            <Flex align="center" gap={8}>
              <Avatar size={26} src={inayaImg} />
              <span>Inaya</span>
            </Flex>
          }
          extra={<Button type="text" size="small" icon={<CloseOutlined />} onClick={() => setOpen(false)} />}
        >
          <div className="flex-1 overflow-y-auto pe-1">
            {turns.length === 0 && (
              <Card bordered={false} className="text-center mt-6">
                <Avatar size={48} src={inayaImg} />
                <Paragraph strong className="mt-3">
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
              <div key={i} className="mb-3.5">
                <Flex gap={8} justify="flex-end" className="mb-2">
                  <Card size="small" className="max-w-[80%] bg-io-600/10" bordered={false}>
                    <Text className="text-[13px]">{t.q}</Text>
                  </Card>
                </Flex>
                {(t.a || t.error || (i === turns.length - 1 && busy)) && (
                  <Flex gap={8}>
                    <Avatar size="small" src={inayaImg} className="shrink-0" />
                    <Card size="small" className="max-w-[85%]" bordered={false}>
                      {i === turns.length - 1 && busy && !t.a && !t.error ? (
                        <Spin size="small" />
                      ) : t.error ? (
                        <Text type="danger">{t.error}</Text>
                      ) : t.a ? (
                        <>
                          <Paragraph strong className="mb-2 text-[13px]">
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
          <Flex gap={8} className="mt-2.5">
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
        className="fixed bottom-6 right-6 w-11 h-11 z-[1000] p-0 shadow-xl border-2 border-io-600"
      >
        <img src={inayaImg} alt="Inaya" className="w-full h-full object-cover rounded-full" />
      </Button>
    </>
  );
}
