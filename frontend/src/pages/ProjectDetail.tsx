import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  Avatar,
  Button,
  Card,
  Col,
  DatePicker,
  Empty,
  Flex,
  Form,
  Input,
  message,
  Modal,
  Row,
  Select,
  Spin,
  Steps,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { ArrowLeftOutlined, PlusOutlined, UserAddOutlined } from "@ant-design/icons";
import {
  api,
  ApiError,
  type ProjectDetail as ProjectDetailData,
  type ProjectTaskRow,
  type UserLite,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { levelOf } from "../components/Layout";

const { Text, Title } = Typography;

function classify(status: string | null | undefined): "completed" | "in_progress" | "pending" {
  const s = (status ?? "").toLowerCase();
  if (["done", "closed", "resolved"].some((k) => s.includes(k))) return "completed";
  if (["progress", "develop", "test", "specif", "review"].some((k) => s.includes(k)))
    return "in_progress";
  return "pending";
}

const BUCKET_TAG: Record<string, string> = {
  completed: "success",
  in_progress: "processing",
  pending: "default",
};

function isOverdue(row: ProjectTaskRow): boolean {
  if (!row.due_date || classify(row.status) === "completed") return false;
  return new Date(row.due_date) < new Date(new Date().toDateString());
}

export default function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>();
  const { user } = useAuth();
  const level = levelOf(user);
  const navigate = useNavigate();

  const [data, setData] = useState<ProjectDetailData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stageBusy, setStageBusy] = useState(false);

  const [taskOpen, setTaskOpen] = useState(false);
  const [taskSaving, setTaskSaving] = useState(false);
  const [taskForm] = Form.useForm();

  const [memberOpen, setMemberOpen] = useState(false);
  const [memberSaving, setMemberSaving] = useState(false);
  const [allPeople, setAllPeople] = useState<UserLite[]>([]);
  const [memberForm] = Form.useForm();

  const load = useCallback(() => {
    if (!projectId) return;
    api
      .project(projectId)
      .then(setData)
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Failed to load this project")
      );
  }, [projectId]);

  useEffect(load, [load]);

  useEffect(() => {
    if (memberOpen) api.orgUsers().then(setAllPeople).catch(() => setAllPeople([]));
  }, [memberOpen]);

  async function advanceStage(stage: string) {
    if (!projectId) return;
    setStageBusy(true);
    try {
      await api.setProjectStage(projectId, stage);
      message.success("Stage updated");
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Stage update failed");
    } finally {
      setStageBusy(false);
    }
  }

  async function createTask(values: {
    title: string;
    description?: string;
    assignee_id?: string;
    due_date?: { format: (f: string) => string } | null;
    priority?: string;
    stage?: string;
  }) {
    if (!projectId) return;
    setTaskSaving(true);
    try {
      await api.createTask({
        title: values.title,
        description: values.description ?? "",
        assignee_id: values.assignee_id ?? "",
        due_date: values.due_date ? values.due_date.format("YYYY-MM-DD") : null,
        priority: values.priority ?? "Normal",
        project_id: projectId,
        stage: values.stage ?? data?.current_stage,
      });
      message.success("Task created");
      setTaskOpen(false);
      taskForm.resetFields();
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Create failed");
    } finally {
      setTaskSaving(false);
    }
  }

  async function addMembers(values: { member_ids: string[] }) {
    if (!projectId) return;
    setMemberSaving(true);
    try {
      const res = await api.addProjectMembers(projectId, values.member_ids);
      message.success(
        res.added.length ? `Added ${res.added.length} member(s)` : "Already on the project"
      );
      setMemberOpen(false);
      memberForm.resetFields();
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Add failed");
    } finally {
      setMemberSaving(false);
    }
  }

  if (error) return <Alert type="error" message={error} showIcon />;
  if (!data)
    return (
      <Flex justify="center" className="pt-20">
        <Spin />
      </Flex>
    );

  const memberIds = new Set(data.members.map((m) => m.user_id));
  const nonMembers = allPeople.filter((p) => !memberIds.has(p.user_id));

  const taskCols = [
    { title: "Task", dataIndex: "title", key: "title", ellipsis: true },
    {
      title: "Stage", dataIndex: "stage", key: "stage", width: 140,
      render: (s: string | null) => {
        const stage = data.stages.find((st) => st.key === s);
        return stage ? <Text className="text-xs">{stage.name}</Text> : "—";
      },
    },
    { title: "Assignee", dataIndex: "assignee", key: "assignee", width: 140, ellipsis: true },
    {
      title: "Status", key: "status", width: 120,
      render: (_: unknown, r: ProjectTaskRow) => (
        <Tag color={isOverdue(r) ? "error" : BUCKET_TAG[classify(r.status)]}>
          {isOverdue(r) ? "Overdue" : r.status ?? "—"}
        </Tag>
      ),
    },
    {
      title: "Due", dataIndex: "due_date", key: "due", width: 110,
      render: (d: string | null) => d ?? "—",
    },
  ];

  const bugCols = [
    { title: "Bug", dataIndex: "title", key: "title", ellipsis: true },
    { title: "Assignee", dataIndex: "assignee", key: "assignee", width: 140, ellipsis: true },
    {
      title: "Priority", dataIndex: "priority", key: "priority", width: 100,
      render: (p: string | null) =>
        p ? <Tag color={/high|immediate/i.test(p) ? "red" : undefined}>{p}</Tag> : "—",
    },
    {
      title: "Status", dataIndex: "status", key: "status", width: 120,
      render: (s: string | null) => <Tag>{s ?? "—"}</Tag>,
    },
  ];

  return (
    <div>
      <Button type="link" icon={<ArrowLeftOutlined />} onClick={() => navigate("/tasks")} className="px-0 mb-2">
        Back to Projects
      </Button>

      <Card size="small" bordered={false} className="mb-4">
        <Flex justify="space-between" align="start" wrap gap={12}>
          <div>
            <Flex align="center" gap={8}>
              <Tag color="blue">{data.code}</Tag>
              <Title level={4} className="m-0">{data.name}</Title>
            </Flex>
            <Text type="secondary">
              {data.client}
              {data.owner ? ` · Owned by ${data.owner.name}` : ""}
            </Text>
          </div>
          <Flex gap={8}>
            {level >= 2 && (
              <Button icon={<UserAddOutlined />} onClick={() => setMemberOpen(true)}>
                Add Members
              </Button>
            )}
            {level >= 2 && (
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setTaskOpen(true)}>
                Add Task
              </Button>
            )}
          </Flex>
        </Flex>
      </Card>

      <Card size="small" bordered={false} className="mb-4">
        <Steps
          size="small"
          items={data.stages.map((s) => ({
            title: s.name,
            status: s.status === "done" ? "finish" : s.status === "active" ? "process" : "wait",
          }))}
        />
        {level >= 3 && (
          <Flex align="center" gap={8} className="mt-4">
            <Text type="secondary" className="text-xs">Move to stage:</Text>
            <Select
              size="small"
              className="w-56"
              value={data.current_stage}
              loading={stageBusy}
              onChange={advanceStage}
              options={data.stages.map((s) => ({ value: s.key, label: s.name }))}
            />
          </Flex>
        )}
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={16}>
          <Card size="small" bordered={false} title="Tasks" className="mb-4">
            {data.tasks.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No tasks yet" />
            ) : (
              <Table
                size="small"
                rowKey="task_id"
                dataSource={data.tasks}
                columns={taskCols}
                pagination={{ pageSize: 8, showSizeChanger: false }}
                scroll={{ x: true }}
              />
            )}
          </Card>

          {data.bugs.length > 0 && (
            <Card size="small" bordered={false} title={`Bugs (${data.bugs.length})`}>
              <Table
                size="small"
                rowKey="task_id"
                dataSource={data.bugs}
                columns={bugCols}
                pagination={{ pageSize: 8, showSizeChanger: false }}
                scroll={{ x: true }}
              />
            </Card>
          )}
        </Col>

        <Col xs={24} lg={8}>
          <Card size="small" bordered={false} title={`Members (${data.members.length})`}>
            <Flex vertical gap={10}>
              {data.members.map((m) => (
                <Flex key={m.user_id} align="center" gap={10}>
                  <Tooltip title={m.name}>
                    <Avatar className="bg-io-600">{m.name[0]}</Avatar>
                  </Tooltip>
                  <div className="min-w-0">
                    <Text className="text-[13px]" ellipsis>{m.name}</Text>
                    <div>
                      <Text type="secondary" className="text-[11px]" ellipsis>
                        {m.designation ?? "—"}
                      </Text>
                    </div>
                  </div>
                </Flex>
              ))}
            </Flex>
          </Card>
        </Col>
      </Row>

      <Modal
        title="Add Task"
        open={taskOpen}
        onCancel={() => setTaskOpen(false)}
        onOk={() => taskForm.submit()}
        confirmLoading={taskSaving}
        okText="Create"
      >
        <Form form={taskForm} layout="vertical" onFinish={createTask}>
          <Form.Item name="title" label="Title" rules={[{ required: true, message: "Title required" }]}>
            <Input placeholder="What needs to be done?" maxLength={300} />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="assignee_id" label="Assign to" extra="Leave empty to assign to yourself">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              options={data.members.map((m) => ({
                value: m.user_id,
                label: m.designation ? `${m.name} — ${m.designation}` : m.name,
              }))}
            />
          </Form.Item>
          <Form.Item name="stage" label="Stage" initialValue={data.current_stage}>
            <Select options={data.stages.map((s) => ({ value: s.key, label: s.name }))} />
          </Form.Item>
          <Flex gap={12}>
            <Form.Item name="due_date" label="Due date" className="flex-1">
              <DatePicker className="w-full" />
            </Form.Item>
            <Form.Item name="priority" label="Priority" initialValue="Normal" className="flex-1">
              <Select
                options={["Low", "Normal", "High", "Immediate"].map((p) => ({ value: p, label: p }))}
              />
            </Form.Item>
          </Flex>
        </Form>
      </Modal>

      <Modal
        title="Add Members"
        open={memberOpen}
        onCancel={() => setMemberOpen(false)}
        onOk={() => memberForm.submit()}
        confirmLoading={memberSaving}
        okText="Add"
      >
        <Form form={memberForm} layout="vertical" onFinish={addMembers}>
          <Form.Item
            name="member_ids"
            label="People to add"
            rules={[{ required: true, message: "Select at least one person" }]}
          >
            <Select
              mode="multiple"
              showSearch
              optionFilterProp="label"
              options={nonMembers.map((p) => ({
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
