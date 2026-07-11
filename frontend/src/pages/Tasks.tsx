import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Flex,
  Form,
  Input,
  message,
  Modal,
  Select,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import {
  api,
  ApiError,
  type MyTasks,
  type TaskRow,
  type TeamTasks,
  type UserLite,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { levelOf } from "../components/Layout";

const { Text } = Typography;

const BUCKET_TAG: Record<string, string> = {
  completed: "success",
  in_progress: "processing",
  pending: "default",
  overdue: "error",
};

export default function Tasks() {
  const { user } = useAuth();
  const level = levelOf(user);
  const isLead = level >= 2;
  const [data, setData] = useState<MyTasks | TeamTasks | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();
  const [open, setOpen] = useState(params.get("new") === "1");
  const [saving, setSaving] = useState(false);
  const [people, setPeople] = useState<UserLite[]>([]);
  const [form] = Form.useForm();

  const load = useCallback(() => {
    const fetcher = isLead ? api.teamTasks() : api.myTasks();
    fetcher
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load tasks"));
  }, [isLead]);

  useEffect(load, [load]);

  useEffect(() => {
    if (open && isLead)
      api.orgUsers().then(setPeople).catch(() => setPeople([]));
  }, [open, isLead]);

  const columns = useMemo(
    () => [
      {
        title: "Task",
        dataIndex: "title",
        key: "title",
        ellipsis: true,
        render: (t: string, r: TaskRow) => (
          <div>
            <Text style={{ fontSize: 13 }}>{t}</Text>
            {r.project && (
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>{r.project}</Text>
              </div>
            )}
          </div>
        ),
      },
      ...(isLead
        ? [{
            title: "Assignee",
            dataIndex: "assignee",
            key: "assignee",
            width: 150,
            ellipsis: true,
          }]
        : []),
      {
        title: "Type",
        dataIndex: "wp_type",
        key: "type",
        width: 90,
        render: (t: string | null) => t ?? "—",
      },
      {
        title: "Status",
        key: "status",
        width: 130,
        filters: [
          { text: "Completed", value: "completed" },
          { text: "In Progress", value: "in_progress" },
          { text: "Pending", value: "pending" },
          { text: "Overdue", value: "overdue" },
        ],
        onFilter: (v: unknown, r: TaskRow) => r.bucket === v,
        render: (_: unknown, r: TaskRow) => (
          <Tag color={BUCKET_TAG[r.bucket]}>{r.status ?? "—"}</Tag>
        ),
      },
      {
        title: "Priority",
        dataIndex: "priority",
        key: "priority",
        width: 100,
        render: (p: string | null) =>
          p ? <Tag color={/high|immediate/i.test(p) ? "red" : undefined}>{p}</Tag> : "—",
      },
      {
        title: "Due",
        dataIndex: "due_date",
        key: "due",
        width: 110,
        render: (d: string | null, r: TaskRow) => (
          <Text type={r.bucket === "overdue" ? "danger" : "secondary"} style={{ fontSize: 12 }}>
            {d ?? "—"}
          </Text>
        ),
      },
    ],
    [isLead]
  );

  async function create(values: {
    title: string;
    description?: string;
    assignee_id?: string;
    due_date?: { format: (f: string) => string } | null;
    priority?: string;
  }) {
    setSaving(true);
    try {
      await api.createTask({
        title: values.title,
        description: values.description ?? "",
        assignee_id: values.assignee_id ?? "",
        due_date: values.due_date ? values.due_date.format("YYYY-MM-DD") : null,
        priority: values.priority ?? "Normal",
      });
      message.success("Task created");
      setOpen(false);
      form.resetFields();
      params.delete("new");
      setParams(params, { replace: true });
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Create failed");
    } finally {
      setSaving(false);
    }
  }

  if (error) return <Alert type="error" message={error} showIcon />;
  if (!data)
    return (
      <Flex justify="center" style={{ paddingTop: 80 }}>
        <Spin size="large" />
      </Flex>
    );

  const b = data.buckets;

  return (
    <div>
      <Flex justify="space-between" align="center" style={{ marginBottom: 12 }} wrap gap={8}>
        <Flex gap={8} wrap>
          <Tag>{b.total} total</Tag>
          <Tag color="success">{b.completed} completed</Tag>
          <Tag color="processing">{b.in_progress} in progress</Tag>
          <Tag>{b.pending} pending</Tag>
          <Tag color="error">{b.overdue} overdue</Tag>
          {data.reopened.length > 0 && (
            <Tag color="orange">{data.reopened.length} reopened bugs</Tag>
          )}
        </Flex>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          Create Task
        </Button>
      </Flex>

      <Card size="small" bordered={false}>
        <Table
          size="small"
          rowKey="task_id"
          dataSource={data.rows}
          columns={columns}
          pagination={{ pageSize: 15, showSizeChanger: false }}
        />
      </Card>

      <Modal
        title="Create Task"
        open={open}
        onCancel={() => {
          setOpen(false);
          params.delete("new");
          setParams(params, { replace: true });
        }}
        onOk={() => form.submit()}
        confirmLoading={saving}
        okText="Create"
      >
        <Form form={form} layout="vertical" onFinish={create}>
          <Form.Item name="title" label="Title" rules={[{ required: true, message: "Title required" }]}>
            <Input placeholder="What needs to be done?" maxLength={300} />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} />
          </Form.Item>
          {isLead && (
            <Form.Item name="assignee_id" label="Assign to" extra="Leave empty to assign to yourself">
              <Select
                allowClear
                showSearch
                optionFilterProp="label"
                options={people.map((p) => ({
                  value: p.user_id,
                  label: `${p.name}${p.designation ? ` — ${p.designation}` : ""}`,
                }))}
              />
            </Form.Item>
          )}
          <Flex gap={12}>
            <Form.Item name="due_date" label="Due date" style={{ flex: 1 }}>
              <DatePicker style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="priority" label="Priority" initialValue="Normal" style={{ flex: 1 }}>
              <Select
                options={["Low", "Normal", "High", "Immediate"].map((p) => ({
                  value: p,
                  label: p,
                }))}
              />
            </Form.Item>
          </Flex>
        </Form>
      </Modal>
    </div>
  );
}
