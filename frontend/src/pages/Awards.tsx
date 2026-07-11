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
import { BRAND } from "../lib/brand";

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
          <Card size="small" style={{ marginBottom: 16 }} title="Give Recognition">
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
            <Card size="small" style={{ marginBottom: 12 }}>
              <Flex justify="space-between" align="center">
                <Tag color="green">{a.category}</Tag>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {new Date(a.awarded_at).toLocaleDateString()}
                </Text>
              </Flex>
              <Paragraph strong style={{ marginBottom: 2, marginTop: 8 }}>
                {a.title}
              </Paragraph>
              <Text type="secondary">{a.description}</Text>
              <div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  To: {a.recipient_id}
                </Text>
              </div>
              <Flex gap={8} style={{ marginTop: 8 }}>
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
                  <Avatar style={{ background: i === 0 ? "#d4b106" : BRAND.primary }}>
                    {i + 1}
                  </Avatar>
                }
                title={r.name}
              />
              <Text strong style={{ color: BRAND.primary }}>
                {r.count}
              </Text>
            </List.Item>
          )}
        />
      </Col>
    </Row>
  );
}
