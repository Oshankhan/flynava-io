import { useEffect, useState } from "react";
import {
  Avatar,
  Button,
  Card,
  Col,
  Flex,
  Form,
  Input,
  List,
  message,
  Row,
  Select,
  Tag,
  Typography,
} from "antd";
import { LikeOutlined, SmileOutlined, TrophyOutlined } from "@ant-design/icons";
import { api, type Award, type LeaderRow } from "../lib/api";
import { useAuth } from "../lib/auth";

const { Title, Text, Paragraph } = Typography;
const CREATORS = ["super_admin", "leadership", "manager", "hr"];
const REACTIONS: { type: string; icon: React.ReactNode }[] = [
  { type: "like", icon: <LikeOutlined /> },
  { type: "celebrate", icon: <TrophyOutlined /> },
  { type: "clap", icon: <SmileOutlined /> },
];

export default function Awards() {
  const { user } = useAuth();
  const [awards, setAwards] = useState<Award[]>([]);
  const [board, setBoard] = useState<LeaderRow[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [form] = Form.useForm();

  const canCreate = user && CREATORS.includes(user.role);

  async function load() {
    setAwards(await api.awards());
    setBoard(await api.awardLeaderboard());
  }
  useEffect(() => {
    load();
    api.awardCategories().then(setCategories);
  }, []);

  async function submit(v: {
    recipient_id: string;
    title: string;
    description?: string;
    category: string;
  }) {
    await api.createAward({ description: "", ...v });
    message.success("Recognition sent");
    form.resetFields();
    load();
  }

  async function react(id: string, type: string) {
    await api.reactAward(id, type);
    load();
  }

  return (
    <Row gutter={[20, 20]}>
      <Col xs={24} lg={16}>
        <Title level={4}>Recognition Feed</Title>
        {canCreate && (
          <Card size="small" className="mb-4" title="Give Recognition">
            <Form form={form} layout="vertical" onFinish={submit}>
              <Row gutter={12}>
                <Col span={12}>
                  <Form.Item name="recipient_id" label="Recipient user_id" rules={[{ required: true }]}>
                    <Input placeholder="e.g. u_emp" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="category" label="Category" initialValue={categories[0]}>
                    <Select options={categories.map((c) => ({ value: c, label: c }))} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="title" label="Title" rules={[{ required: true }]}>
                <Input placeholder="Award title" />
              </Form.Item>
              <Form.Item name="description" label="Description">
                <Input.TextArea rows={2} />
              </Form.Item>
              <Button type="primary" htmlType="submit">
                Give Recognition
              </Button>
            </Form>
          </Card>
        )}

        <List
          dataSource={awards}
          locale={{ emptyText: "No recognitions yet." }}
          renderItem={(a) => (
            <Card size="small" className="mb-3">
              <Flex justify="space-between" align="center">
                <Tag color="green">{a.category}</Tag>
                <Text type="secondary" className="text-xs">
                  {new Date(a.awarded_at).toLocaleDateString()}
                </Text>
              </Flex>
              <Paragraph strong className="mb-0.5 mt-2">
                {a.title}
              </Paragraph>
              <Text type="secondary">{a.description}</Text>
              <div>
                <Text type="secondary" className="text-xs">
                  To: {a.recipient_id}
                </Text>
              </div>
              <Flex gap={8} className="mt-2">
                {REACTIONS.map((r) => (
                  <Button
                    key={r.type}
                    size="small"
                    icon={r.icon}
                    onClick={() => react(a.award_id, r.type)}
                  >
                    {a.reactions?.[r.type] ?? 0}
                  </Button>
                ))}
              </Flex>
            </Card>
          )}
        />
      </Col>

      <Col xs={24} lg={8}>
        <Title level={4}>Leaderboard</Title>
        <List
          dataSource={board}
          renderItem={(r, i) => (
            <List.Item>
              <List.Item.Meta
                avatar={
                  <Avatar className={i === 0 ? "bg-[#d4b106]" : "bg-io-600"}>
                    {i + 1}
                  </Avatar>
                }
                title={r.name}
              />
              <Text strong className="text-io-600">
                {r.count}
              </Text>
            </List.Item>
          )}
        />
      </Col>
    </Row>
  );
}
