import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Alert,
  Avatar,
  Button,
  Card,
  Col,
  Empty,
  Flex,
  Form,
  Input,
  message,
  Modal,
  Progress,
  Row,
  Select,
  Spin,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { BugOutlined, PlusOutlined } from "@ant-design/icons";
import { api, ApiError, type ProjectSummary, type TeamInfo, type UserLite } from "../lib/api";
import { useAuth } from "../lib/auth";
import { levelOf } from "../components/Layout";

const { Text } = Typography;

const STATUS_TAG: Record<string, string> = {
  pipeline: "default",
  active: "processing",
  maintenance: "success",
};

export default function Tasks() {
  const { user } = useAuth();
  const level = levelOf(user);
  const canCreateProject = level >= 3;
  const navigate = useNavigate();

  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [teams, setTeams] = useState<TeamInfo[]>([]);
  const [people, setPeople] = useState<UserLite[]>([]);
  const [form] = Form.useForm();

  const load = useCallback(() => {
    api
      .projects()
      .then(setProjects)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load projects"));
  }, []);

  useEffect(load, [load]);

  useEffect(() => {
    if (open) {
      api.orgTeams().then(setTeams).catch(() => setTeams([]));
      api.orgUsers().then(setPeople).catch(() => setPeople([]));
    }
  }, [open]);

  async function create(values: {
    code: string;
    name: string;
    client?: string;
    team_ids?: string[];
    member_ids?: string[];
  }) {
    setSaving(true);
    try {
      await api.createProject({
        code: values.code,
        name: values.name,
        client: values.client ?? "",
        team_ids: values.team_ids ?? [],
        member_ids: values.member_ids ?? [],
      });
      message.success("Project created");
      setOpen(false);
      form.resetFields();
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Create failed");
    } finally {
      setSaving(false);
    }
  }

  if (error) return <Alert type="error" message={error} showIcon />;
  if (!projects)
    return (
      <Flex justify="center" className="pt-20">
        <Spin />
      </Flex>
    );

  return (
    <div>
      <Flex justify="space-between" align="center" className="mb-4" wrap gap={8}>
        <Text type="secondary">
          {projects.length} project{projects.length === 1 ? "" : "s"} — organized by client
          engagement, each moving through its own stage pipeline.
        </Text>
        {canCreateProject && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
            Add Project
          </Button>
        )}
      </Flex>

      {projects.length === 0 ? (
        <Card size="small" bordered={false}>
          <Empty description="No projects yet." />
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {projects.map((p) => (
            <Col key={p.project_id} xs={24} md={12} xl={8}>
              <Card
                size="small"
                hoverable
                className="h-full"
                onClick={() => navigate(`/projects/${p.project_id}`)}
              >
                <Flex justify="space-between" align="start" className="mb-1">
                  <div className="min-w-0">
                    <Flex align="center" gap={8}>
                      <Tag color="blue">{p.code}</Tag>
                      <Text strong ellipsis>{p.name}</Text>
                    </Flex>
                    <Text type="secondary" className="text-[12px]">{p.client}</Text>
                  </div>
                  <Tag color={STATUS_TAG[p.status] ?? "default"} className="capitalize shrink-0">
                    {p.status}
                  </Tag>
                </Flex>

                <div className="mt-2 mb-1">
                  <Flex justify="space-between">
                    <Text type="secondary" className="text-[12px]">
                      {p.current_stage_name ?? p.current_stage}
                    </Text>
                    <Text type="secondary" className="text-[12px]">{p.progress}%</Text>
                  </Flex>
                  <Progress percent={p.progress} showInfo={false} size="small" />
                </div>

                <Flex justify="space-between" align="center" className="mt-3">
                  <Avatar.Group max={{ count: 5 }} size="small">
                    {p.members.map((m) => (
                      <Tooltip key={m.user_id} title={m.name}>
                        <Avatar className="bg-io-600">{m.name[0]}</Avatar>
                      </Tooltip>
                    ))}
                  </Avatar.Group>
                  <Flex gap={6}>
                    {p.bug_count > 0 && (
                      <Tag icon={<BugOutlined />} color="red">{p.bug_count}</Tag>
                    )}
                    <Tag>{p.task_count} tasks</Tag>
                  </Flex>
                </Flex>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Modal
        title="Add Project"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={saving}
        okText="Create"
      >
        <Form form={form} layout="vertical" onFinish={create}>
          <Flex gap={12}>
            <Form.Item
              name="code"
              label="Code"
              className="flex-1"
              rules={[{ required: true, message: "Required" }]}
            >
              <Input placeholder="e.g. KQ" maxLength={10} />
            </Form.Item>
            <Form.Item
              name="name"
              label="Project name"
              className="flex-[2]"
              rules={[{ required: true, message: "Required" }]}
            >
              <Input placeholder="e.g. Kenya Airways" maxLength={200} />
            </Form.Item>
          </Flex>
          <Form.Item name="client" label="Client">
            <Input maxLength={200} />
          </Form.Item>
          <Form.Item name="team_ids" label="Teams involved">
            <Select
              mode="multiple"
              placeholder="Select teams"
              options={teams.map((t) => ({ value: t.team_id, label: t.name }))}
            />
          </Form.Item>
          <Form.Item name="member_ids" label="Members">
            <Select
              mode="multiple"
              showSearch
              optionFilterProp="label"
              placeholder="Select members"
              options={people.map((p) => ({
                value: p.user_id,
                label: p.designation ? `${p.name} — ${p.designation}` : p.name,
              }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
