import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  Alert,
  Avatar,
  Button,
  Card,
  DatePicker,
  Empty,
  Flex,
  Form,
  Input,
  message,
  Modal,
  Progress,
  Select,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import {
  BugOutlined,
  CalendarOutlined,
  PlusOutlined,
  SearchOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import {
  api,
  ApiError,
  type MyTasks,
  type ProjectSummary,
  type TaskRow,
  type TeamInfo,
  type TeamTasks,
  type UserLite,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { levelOf } from "../components/Layout";
import ProjectDrawer from "../components/ProjectDrawer";

const { Text, Title } = Typography;

const STATUS_TAG: Record<string, string> = {
  planning: "blue",
  active: "success",
  on_hold: "orange",
  completed: "default",
};

const ACCENT_COLORS = ["#dc2626", "#d97706", "#059669", "#2563eb", "#7c3aed", "#db2777"];
function accentFor(code: string): string {
  const idx = code.split("").reduce((a, c) => a + c.charCodeAt(0), 0) % ACCENT_COLORS.length;
  return ACCENT_COLORS[idx];
}

const BUCKET_TAG: Record<string, string> = {
  completed: "success",
  in_progress: "processing",
  pending: "default",
  overdue: "error",
};

function daysLeft(due?: string | null): string | null {
  if (!due) return null;
  const d = Math.ceil((new Date(due).getTime() - Date.now()) / 86_400_000);
  if (d < 0) return `${Math.abs(d)} days overdue`;
  return `${d} days left`;
}

function ProjectsTab({ canCreate }: { canCreate: boolean }) {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [clientFilter, setClientFilter] = useState<string>("all");

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
    description?: string;
    engagement?: string;
    priority?: string;
    project_manager_id?: string;
    team_ids?: string[];
    member_ids?: string[];
    start_date?: { format: (f: string) => string } | null;
    due_date?: { format: (f: string) => string } | null;
  }) {
    setSaving(true);
    try {
      await api.createProject({
        code: values.code,
        name: values.name,
        client: values.client ?? "",
        description: values.description ?? "",
        engagement: values.engagement ?? "",
        priority: values.priority ?? "Medium",
        project_manager_id: values.project_manager_id ?? null,
        team_ids: values.team_ids ?? [],
        member_ids: values.member_ids ?? [],
        start_date: values.start_date ? values.start_date.format("YYYY-MM-DD") : null,
        due_date: values.due_date ? values.due_date.format("YYYY-MM-DD") : null,
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

  const clients = Array.from(new Set(projects.map((p) => p.client).filter(Boolean))) as string[];
  const filtered = projects.filter((p) => {
    const q = search.trim().toLowerCase();
    const matchesSearch =
      !q ||
      p.name.toLowerCase().includes(q) ||
      p.code.toLowerCase().includes(q) ||
      (p.client ?? "").toLowerCase().includes(q);
    const matchesStatus = statusFilter === "all" || p.status === statusFilter;
    const matchesClient = clientFilter === "all" || p.client === clientFilter;
    return matchesSearch && matchesStatus && matchesClient;
  });

  return (
    <div>
      <Flex gap={8} wrap className="mb-4">
        <Input
          placeholder="Search projects..."
          prefix={<SearchOutlined className="text-gray-400" />}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
          allowClear
        />
        <Select
          value={statusFilter}
          onChange={setStatusFilter}
          className="w-40"
          options={[
            { value: "all", label: "All Status" },
            { value: "planning", label: "Planning" },
            { value: "active", label: "Active" },
            { value: "on_hold", label: "On Hold" },
            { value: "completed", label: "Completed" },
          ]}
        />
        <Select
          value={clientFilter}
          onChange={setClientFilter}
          className="w-44"
          options={[
            { value: "all", label: "All Clients" },
            ...clients.map((c) => ({ value: c, label: c })),
          ]}
        />
        <div className="flex-1" />
        {canCreate && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
            Add Project
          </Button>
        )}
      </Flex>

      {filtered.length === 0 ? (
        <Card size="small" bordered={false}>
          <Empty description="No projects match your filters." />
        </Card>
      ) : (
        <Flex vertical gap={12}>
          {filtered.map((p) => {
            const accent = accentFor(p.code);
            const dleft = daysLeft(p.due_date);
            return (
              <Card
                key={p.project_id}
                size="small"
                hoverable
                onClick={() => navigate(`/projects/${p.project_id}`)}
                style={{ borderLeft: `4px solid ${accent}` }}
                styles={{ body: { padding: 16 } }}
              >
                <Flex justify="space-between" gap={16} wrap>
                  <Flex gap={12} className="min-w-0 flex-1">
                    <Avatar size={40} style={{ backgroundColor: accent, flexShrink: 0 }}>
                      {p.code}
                    </Avatar>
                    <div className="min-w-0 flex-1">
                      <Flex align="center" gap={8} wrap>
                        <Text strong>({p.code}) {p.name}</Text>
                        <Tag color={STATUS_TAG[p.status] ?? "default"} className="capitalize">
                          {p.status.replace("_", " ")}
                        </Tag>
                      </Flex>
                      {p.engagement && (
                        <Text type="secondary" className="text-[12px]">{p.engagement}</Text>
                      )}
                      {p.description && (
                        <div>
                          <Text type="secondary" className="text-[12px]">{p.description}</Text>
                        </div>
                      )}
                      <Flex gap={16} wrap className="mt-2">
                        {p.client && (
                          <Text type="secondary" className="text-[12px]">
                            <TeamOutlined className="mr-1" />Client: {p.client}
                          </Text>
                        )}
                        {p.project_manager && (
                          <Text type="secondary" className="text-[12px]">
                            <UserOutlined className="mr-1" />PM: {p.project_manager.name}
                          </Text>
                        )}
                        {p.start_date && (
                          <Text type="secondary" className="text-[12px]">
                            <CalendarOutlined className="mr-1" />Start: {p.start_date}
                          </Text>
                        )}
                        {p.due_date && (
                          <Text type="secondary" className="text-[12px]">
                            <CalendarOutlined className="mr-1" />Due: {p.due_date}
                          </Text>
                        )}
                      </Flex>
                    </div>
                  </Flex>

                  <Flex vertical gap={8} className="w-full sm:w-52 shrink-0">
                    <div>
                      <Flex justify="space-between">
                        <Text type="secondary" className="text-[12px]">Progress</Text>
                        <Text className="text-[12px]" strong>{p.progress}%</Text>
                      </Flex>
                      <Progress percent={p.progress} showInfo={false} size="small" />
                    </div>
                    <Flex justify="space-between" align="center">
                      <Avatar.Group max={{ count: 4 }} size="small">
                        {p.members.map((m) => (
                          <Tooltip key={m.user_id} title={m.name}>
                            <Avatar className="bg-io-600">{m.name[0]}</Avatar>
                          </Tooltip>
                        ))}
                      </Avatar.Group>
                      <Text type="secondary" className="text-[11px]">
                        {p.member_count} member{p.member_count === 1 ? "" : "s"}
                      </Text>
                    </Flex>
                    <Flex justify="space-between" align="center">
                      <Flex gap={6}>
                        {p.bug_count > 0 && (
                          <Tag icon={<BugOutlined />} color="red">{p.bug_count}</Tag>
                        )}
                        <Tag>{p.open_tasks} open tasks</Tag>
                      </Flex>
                      {dleft && (
                        <Text type={dleft.includes("overdue") ? "danger" : "secondary"}
                          className="text-[11px]">
                          {dleft}
                        </Text>
                      )}
                    </Flex>
                  </Flex>
                </Flex>
              </Card>
            );
          })}
        </Flex>
      )}

      <Text type="secondary" className="text-[12px] block mt-3">
        Showing {filtered.length} of {projects.length} project{projects.length === 1 ? "" : "s"}
      </Text>

      <Modal
        title="Add Project"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={saving}
        okText="Create"
        width={640}
      >
        <Form form={form} layout="vertical" onFinish={create}>
          <Flex gap={12}>
            <Form.Item name="code" label="Code" className="flex-1"
              rules={[{ required: true, message: "Required" }]}>
              <Input placeholder="e.g. KQ" maxLength={10} />
            </Form.Item>
            <Form.Item name="name" label="Project name" className="flex-[2]"
              rules={[{ required: true, message: "Required" }]}>
              <Input placeholder="e.g. Kenya Airways" maxLength={200} />
            </Form.Item>
          </Flex>
          <Flex gap={12}>
            <Form.Item name="client" label="Client" className="flex-1">
              <Input maxLength={200} />
            </Form.Item>
            <Form.Item name="engagement" label="Engagement" className="flex-1">
              <Input placeholder="e.g. New Prospect" maxLength={200} />
            </Form.Item>
          </Flex>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} maxLength={500} />
          </Form.Item>
          <Flex gap={12}>
            <Form.Item name="project_manager_id" label="Project Manager" className="flex-1">
              <Select
                showSearch
                allowClear
                optionFilterProp="label"
                options={people.map((p) => ({
                  value: p.user_id,
                  label: p.designation ? `${p.name} — ${p.designation}` : p.name,
                }))}
              />
            </Form.Item>
            <Form.Item name="priority" label="Priority" initialValue="Medium" className="flex-1">
              <Select
                options={["Low", "Medium", "High"].map((p) => ({ value: p, label: p }))}
              />
            </Form.Item>
          </Flex>
          <Flex gap={12}>
            <Form.Item name="start_date" label="Start date" className="flex-1">
              <DatePicker className="w-full" />
            </Form.Item>
            <Form.Item name="due_date" label="Due date" className="flex-1">
              <DatePicker className="w-full" />
            </Form.Item>
          </Flex>
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

function TaskListPanel({ mode }: { mode: "mine" | "all" }) {
  const isLead = mode === "all";
  const [data, setData] = useState<MyTasks | TeamTasks | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [params, setParams] = useSearchParams();
  const [open, setOpen] = useState(mode === "mine" && params.get("new") === "1");
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
    if (open) api.orgUsers().then(setPeople).catch(() => setPeople([]));
  }, [open]);

  const columns = useMemo(
    () => [
      {
        title: "Task", dataIndex: "title", key: "title", ellipsis: true,
        render: (t: string, r: TaskRow) => (
          <div>
            <Text className="text-[13px]">{t}</Text>
            {r.project && (
              <div>
                <Text type="secondary" className="text-[11px]">{r.project}</Text>
              </div>
            )}
          </div>
        ),
      },
      ...(isLead
        ? [{ title: "Assignee", dataIndex: "assignee", key: "assignee", width: 150, ellipsis: true }]
        : []),
      {
        title: "Type", dataIndex: "wp_type", key: "type", width: 90,
        render: (t: string | null) => t ?? "—",
      },
      {
        title: "Status", key: "status", width: 130,
        filters: [
          { text: "Completed", value: "completed" },
          { text: "In Progress", value: "in_progress" },
          { text: "Pending", value: "pending" },
          { text: "Overdue", value: "overdue" },
        ],
        onFilter: (v: unknown, r: TaskRow) => r.bucket === v,
        render: (_: unknown, r: TaskRow) => <Tag color={BUCKET_TAG[r.bucket]}>{r.status ?? "—"}</Tag>,
      },
      {
        title: "Priority", dataIndex: "priority", key: "priority", width: 100,
        render: (p: string | null) =>
          p ? <Tag color={/high|immediate/i.test(p) ? "red" : undefined}>{p}</Tag> : "—",
      },
      {
        title: "Due", dataIndex: "due_date", key: "due", width: 110,
        render: (d: string | null, r: TaskRow) => (
          <Text type={r.bucket === "overdue" ? "danger" : "secondary"} className="text-xs">
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
      <Flex justify="center" className="pt-20">
        <Spin />
      </Flex>
    );

  const b = data.buckets;

  return (
    <div>
      <Flex justify="space-between" align="center" className="mb-3" wrap gap={8}>
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
          scroll={{ x: true }}
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
                  label: p.designation ? `${p.name} — ${p.designation}` : p.name,
                }))}
              />
            </Form.Item>
          )}
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
    </div>
  );
}

export default function Tasks() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { projectId } = useParams<{ projectId: string }>();
  const level = levelOf(user);
  const canCreateProject = level >= 3;
  const isLead = level >= 2;
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "projects";

  return (
    <div>
      <Title level={4} className="mt-0 mb-3">Team Tasks</Title>
      <Tabs
        activeKey={tab}
        onChange={(key) => {
          params.set("tab", key);
          setParams(params, { replace: true });
        }}
        items={[
          { key: "projects", label: "Projects", children: <ProjectsTab canCreate={canCreateProject} /> },
          { key: "mine", label: "My Tasks", children: <TaskListPanel mode="mine" /> },
          ...(isLead
            ? [{ key: "all", label: "All Tasks", children: <TaskListPanel mode="all" /> }]
            : []),
        ]}
      />
      <ProjectDrawer projectId={projectId} onClose={() => navigate("/tasks")} />
    </div>
  );
}
