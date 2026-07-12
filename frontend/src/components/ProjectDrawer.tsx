import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Avatar,
  Button,
  Card,
  Col,
  DatePicker,
  Drawer,
  Dropdown,
  Empty,
  Flex,
  Form,
  Input,
  InputNumber,
  List,
  message,
  Modal,
  Progress,
  Row,
  Select,
  Spin,
  Statistic,
  Table,
  Tabs,
  Tag,
  Timeline,
  Tooltip,
  Typography,
  Upload,
} from "antd";
import {
  ClockCircleOutlined,
  DeleteOutlined,
  EditOutlined,
  FileTextOutlined,
  InboxOutlined,
  PlusOutlined,
  UserAddOutlined,
} from "@ant-design/icons";
import {
  api,
  ApiError,
  type IoDocument,
  type ProjectActivityItem,
  type ProjectDetail as ProjectDetailData,
  type ProjectStage,
  type ProjectTaskRow,
  type UserLite,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { levelOf } from "./Layout";

const { Text, Title } = Typography;

const STATUS_TAG: Record<string, string> = {
  planning: "blue", active: "success", on_hold: "orange", completed: "default",
};
const STAGE_STATUS_TAG: Record<string, string> = {
  done: "success", active: "processing", pending: "default",
};

function classify(status: string | null | undefined): "completed" | "in_progress" | "pending" {
  const s = (status ?? "").toLowerCase();
  if (["done", "closed", "resolved"].some((k) => s.includes(k))) return "completed";
  if (["progress", "develop", "test", "specif", "review"].some((k) => s.includes(k))) return "in_progress";
  return "pending";
}
const BUCKET_TAG: Record<string, string> = {
  completed: "success", in_progress: "processing", pending: "default",
};
function isOverdue(row: ProjectTaskRow): boolean {
  if (!row.due_date || classify(row.status) === "completed") return false;
  return new Date(row.due_date) < new Date(new Date().toDateString());
}
function daysLeft(due?: string | null): string | null {
  if (!due) return null;
  const d = Math.ceil((new Date(due).getTime() - Date.now()) / 86_400_000);
  return d < 0 ? `${Math.abs(d)} days overdue` : `${d} days left`;
}

const ACTION_LABEL: Record<string, string> = {
  project_created: "created the project",
  project_updated: "updated the project details",
  stage_added: "added a stage",
  stage_updated: "updated a stage",
  stage_deleted: "deleted a stage",
  project_members_added: "added member(s)",
  task_created: "created a task",
};

export default function ProjectDrawer({
  projectId, onClose,
}: {
  projectId: string | undefined;
  onClose: () => void;
}) {
  const { user } = useAuth();
  const level = levelOf(user);
  const canEditProject = level >= 3;
  const canManageMembers = level >= 2;

  const [data, setData] = useState<ProjectDetailData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");

  const [editOpen, setEditOpen] = useState(false);
  const [editSaving, setEditSaving] = useState(false);
  const [editForm] = Form.useForm();

  const [stageOpen, setStageOpen] = useState(false);
  const [stageMode, setStageMode] = useState<"add" | "edit">("add");
  const [editingStage, setEditingStage] = useState<ProjectStage | null>(null);
  const [stageSaving, setStageSaving] = useState(false);
  const [stageForm] = Form.useForm();

  const [taskOpen, setTaskOpen] = useState(false);
  const [taskSaving, setTaskSaving] = useState(false);
  const [taskForm] = Form.useForm();

  const [memberOpen, setMemberOpen] = useState(false);
  const [memberSaving, setMemberSaving] = useState(false);
  const [allPeople, setAllPeople] = useState<UserLite[]>([]);
  const [memberForm] = Form.useForm();

  const [docs, setDocs] = useState<IoDocument[] | null>(null);
  const [docTitle, setDocTitle] = useState("");
  const [docKind, setDocKind] = useState("document");
  const [docFile, setDocFile] = useState<File | null>(null);
  const [docUploading, setDocUploading] = useState(false);

  const [activity, setActivity] = useState<ProjectActivityItem[] | null>(null);

  const load = useCallback(() => {
    if (!projectId) return;
    api.project(projectId).then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load this project"));
  }, [projectId]);

  useEffect(() => {
    setData(null);
    setError(null);
    setActiveTab("overview");
    load();
  }, [load]);

  useEffect(() => {
    if (activeTab === "documents" && projectId) {
      api.documents(projectId).then(setDocs).catch(() => setDocs([]));
    }
    if (activeTab === "activity" && projectId) {
      api.projectActivity(projectId).then(setActivity).catch(() => setActivity([]));
    }
  }, [activeTab, projectId]);

  useEffect(() => {
    if ((memberOpen || taskOpen) && allPeople.length === 0) {
      api.orgUsers().then(setAllPeople).catch(() => setAllPeople([]));
    }
  }, [memberOpen, taskOpen, allPeople.length]);

  async function saveProjectEdit(values: Record<string, unknown>) {
    if (!projectId) return;
    setEditSaving(true);
    try {
      const sd = values.start_date as { format: (f: string) => string } | null | undefined;
      const dd = values.due_date as { format: (f: string) => string } | null | undefined;
      await api.updateProject(projectId, {
        name: values.name as string, client: values.client as string,
        description: values.description as string, engagement: values.engagement as string,
        priority: values.priority as string, status: values.status as string,
        project_manager_id: (values.project_manager_id as string) || null,
        start_date: sd ? sd.format("YYYY-MM-DD") : undefined,
        due_date: dd ? dd.format("YYYY-MM-DD") : undefined,
      });
      message.success("Project updated");
      setEditOpen(false);
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Update failed");
    } finally {
      setEditSaving(false);
    }
  }

  function openAddStage() {
    setStageMode("add");
    setEditingStage(null);
    stageForm.resetFields();
    setStageOpen(true);
  }
  function openEditStage(s: ProjectStage) {
    setStageMode("edit");
    setEditingStage(s);
    stageForm.setFieldsValue({
      name: s.name, description: s.description, status: s.status, progress: s.progress,
    });
    setStageOpen(true);
  }
  async function saveStage(values: {
    key?: string; name: string; description?: string; status: string; progress: number;
  }) {
    if (!projectId) return;
    setStageSaving(true);
    try {
      if (stageMode === "add") {
        await api.addStage(projectId, {
          key: (values.key ?? values.name).toLowerCase().replace(/[^a-z0-9]+/g, "_"),
          name: values.name, description: values.description ?? "",
          status: values.status, progress: values.progress,
        });
      } else if (editingStage) {
        await api.updateStage(projectId, editingStage.key, {
          name: values.name, description: values.description, status: values.status,
          progress: values.progress,
        });
      }
      message.success(stageMode === "add" ? "Stage added" : "Stage updated");
      setStageOpen(false);
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setStageSaving(false);
    }
  }
  async function quickStageAction(s: ProjectStage, status: "active" | "done") {
    if (!projectId) return;
    try {
      await api.updateStage(projectId, s.key, {
        status, progress: status === "done" ? 100 : s.progress,
      });
      message.success("Stage updated");
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Update failed");
    }
  }
  async function removeStage(s: ProjectStage) {
    if (!projectId) return;
    try {
      await api.deleteStage(projectId, s.key);
      message.success("Stage deleted");
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Delete failed");
    }
  }

  async function createTask(values: {
    title: string; description?: string; assignee_id?: string;
    due_date?: { format: (f: string) => string } | null; priority?: string; stage?: string;
  }) {
    if (!projectId) return;
    setTaskSaving(true);
    try {
      await api.createTask({
        title: values.title, description: values.description ?? "",
        assignee_id: values.assignee_id ?? "",
        due_date: values.due_date ? values.due_date.format("YYYY-MM-DD") : null,
        priority: values.priority ?? "Normal", project_id: projectId,
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
      message.success(res.added.length ? `Added ${res.added.length} member(s)` : "Already on the project");
      setMemberOpen(false);
      memberForm.resetFields();
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Add failed");
    } finally {
      setMemberSaving(false);
    }
  }

  async function uploadDoc() {
    if (!projectId || !docFile || !docTitle) return;
    setDocUploading(true);
    try {
      await api.uploadDocument(docTitle, docKind, docFile, projectId);
      message.success("Document uploaded");
      setDocTitle("");
      setDocFile(null);
      api.documents(projectId).then(setDocs);
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Upload failed");
    } finally {
      setDocUploading(false);
    }
  }

  const open = !!projectId;

  const stageCols = [
    {
      title: "#", key: "idx", width: 40,
      render: (_: unknown, __: ProjectStage, i: number) => (
        <Avatar size={22} className="bg-io-600 text-[11px]">{i + 1}</Avatar>
      ),
    },
    {
      title: "Stage", key: "name",
      render: (_: unknown, s: ProjectStage) => (
        <div>
          <Text strong className="text-[13px]">{s.name}</Text>
          {s.description && (
            <div><Text type="secondary" className="text-[11px]">{s.description}</Text></div>
          )}
        </div>
      ),
    },
    {
      title: "Status", key: "status", width: 110,
      render: (_: unknown, s: ProjectStage) => (
        <Tag color={STAGE_STATUS_TAG[s.status] ?? "default"} className="capitalize">
          {s.status.replace("_", " ")}
        </Tag>
      ),
    },
    {
      title: "Progress", key: "progress", width: 140,
      render: (_: unknown, s: ProjectStage) => (
        <Flex align="center" gap={8}>
          <Progress percent={s.progress} size="small" className="flex-1 mb-0" showInfo={false} />
          <Text className="text-[11px] w-8 shrink-0">{s.progress}%</Text>
        </Flex>
      ),
    },
    {
      title: "Dates", key: "dates", width: 170,
      render: (_: unknown, s: ProjectStage) => (
        <Text type="secondary" className="text-[11px]">
          {s.start_date ?? "—"} → {s.end_date ?? "—"}
        </Text>
      ),
    },
    ...(canManageMembers
      ? [{
          title: "", key: "actions", width: 50,
          render: (_: unknown, s: ProjectStage) => (
            <Dropdown
              menu={{
                items: [
                  { key: "edit", icon: <EditOutlined />, label: "Edit" },
                  { key: "active", label: "Mark In Progress", disabled: s.status === "active" },
                  { key: "done", label: "Mark Completed", disabled: s.status === "done" },
                  ...(canEditProject
                    ? [{ key: "delete", icon: <DeleteOutlined />, label: "Delete", danger: true }]
                    : []),
                ],
                onClick: ({ key }) => {
                  if (key === "edit") openEditStage(s);
                  else if (key === "active") quickStageAction(s, "active");
                  else if (key === "done") quickStageAction(s, "done");
                  else if (key === "delete") removeStage(s);
                },
              }}
            >
              <Button type="text" size="small">⋮</Button>
            </Dropdown>
          ),
        }]
      : []),
  ];

  const taskCols = [
    { title: "Task", dataIndex: "title", key: "title", ellipsis: true },
    {
      title: "Stage", dataIndex: "stage", key: "stage", width: 130,
      render: (s: string | null) => {
        const stage = data?.stages.find((st) => st.key === s);
        return stage ? <Text className="text-xs">{stage.name}</Text> : "—";
      },
    },
    { title: "Assignee", dataIndex: "assignee", key: "assignee", width: 130, ellipsis: true },
    {
      title: "Status", key: "status", width: 110,
      render: (_: unknown, r: ProjectTaskRow) => (
        <Tag color={isOverdue(r) ? "error" : BUCKET_TAG[classify(r.status)]}>
          {isOverdue(r) ? "Overdue" : r.status ?? "—"}
        </Tag>
      ),
    },
    { title: "Due", dataIndex: "due_date", key: "due", width: 100, render: (d: string | null) => d ?? "—" },
  ];
  const bugCols = [
    { title: "Bug", dataIndex: "title", key: "title", ellipsis: true },
    { title: "Assignee", dataIndex: "assignee", key: "assignee", width: 130, ellipsis: true },
    {
      title: "Priority", dataIndex: "priority", key: "priority", width: 90,
      render: (p: string | null) => (p ? <Tag color={/high|immediate/i.test(p) ? "red" : undefined}>{p}</Tag> : "—"),
    },
    { title: "Status", dataIndex: "status", key: "status", width: 110, render: (s: string | null) => <Tag>{s ?? "—"}</Tag> },
  ];

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width="min(860px, 100vw)"
      destroyOnClose
      title={
        data ? (
          <Flex justify="space-between" align="center" wrap gap={8}>
            <Flex align="center" gap={10}>
              <Avatar className="bg-io-600">{data.code}</Avatar>
              <div>
                <Flex align="center" gap={8}>
                  <Title level={5} className="m-0">({data.code}) {data.name}</Title>
                  <Tag color={STATUS_TAG[data.status] ?? "default"} className="capitalize">
                    {data.status.replace("_", " ")}
                  </Tag>
                </Flex>
                {data.engagement && <Text type="secondary" className="text-[12px]">{data.engagement}</Text>}
              </div>
            </Flex>
            {canEditProject && (
              <Button
                icon={<EditOutlined />}
                onClick={() => {
                  editForm.setFieldsValue({
                    name: data.name, client: data.client, description: data.description,
                    engagement: data.engagement, priority: data.priority, status: data.status,
                    project_manager_id: data.project_manager?.user_id,
                  });
                  setEditOpen(true);
                }}
              >
                Edit Project
              </Button>
            )}
          </Flex>
        ) : "Project"
      }
    >
      {error && <Alert type="error" message={error} showIcon />}
      {!data && !error && (
        <Flex justify="center" className="pt-20"><Spin /></Flex>
      )}
      {data && (
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={[
            {
              key: "overview", label: "Overview",
              children: (
                <div>
                  <Row gutter={[12, 12]} className="mb-4">
                    <Col span={12} md={6}><Card size="small"><Statistic title="Progress" value={data.progress} suffix="%" /></Card></Col>
                    <Col span={12} md={6}><Card size="small"><Statistic title="Open Tasks" value={data.tasks.filter((t) => classify(t.status) !== "completed").length} /></Card></Col>
                    <Col span={12} md={6}><Card size="small"><Statistic title="Team Members" value={data.members.length} /></Card></Col>
                    <Col span={12} md={6}>
                      <Card size="small">
                        <Text type="secondary" className="text-xs">Due Date</Text>
                        <div className="text-[15px] font-semibold">{data.due_date ?? "—"}</div>
                        {daysLeft(data.due_date) && (
                          <Text type="secondary" className="text-[11px]">{daysLeft(data.due_date)}</Text>
                        )}
                      </Card>
                    </Col>
                  </Row>

                  {data.description && (
                    <Card size="small" title="Project Description" className="mb-4">
                      <Text>{data.description}</Text>
                    </Card>
                  )}

                  <Card
                    size="small"
                    title="Project Stages"
                    className="mb-4"
                    extra={canEditProject && (
                      <Button size="small" icon={<PlusOutlined />} onClick={openAddStage}>Add Stage</Button>
                    )}
                  >
                    <Table
                      size="small" rowKey="key" dataSource={data.stages} columns={stageCols}
                      pagination={false} scroll={{ x: true }}
                    />
                  </Card>

                  <Card size="small" title="Project Details">
                    <Row gutter={[16, 12]}>
                      <Col span={12}><Text type="secondary" className="text-xs block">Client</Text><Text>{data.client ?? "—"}</Text></Col>
                      <Col span={12}><Text type="secondary" className="text-xs block">Project Manager</Text><Text>{data.project_manager?.name ?? "—"}</Text></Col>
                      <Col span={12}><Text type="secondary" className="text-xs block">Start Date</Text><Text>{data.start_date ?? "—"}</Text></Col>
                      <Col span={12}><Text type="secondary" className="text-xs block">Due Date</Text><Text>{data.due_date ?? "—"}</Text></Col>
                      <Col span={12}><Text type="secondary" className="text-xs block">Status</Text><Text className="capitalize">{data.status.replace("_", " ")}</Text></Col>
                      <Col span={12}>
                        <Text type="secondary" className="text-xs block">Priority</Text>
                        <Text type={data.priority === "High" ? "danger" : undefined}>{data.priority ?? "—"}</Text>
                      </Col>
                    </Row>
                  </Card>
                </div>
              ),
            },
            {
              key: "team", label: "Team & Members",
              children: (
                <div>
                  {canManageMembers && (
                    <Flex justify="end" className="mb-3">
                      <Button icon={<UserAddOutlined />} onClick={() => setMemberOpen(true)}>Add Members</Button>
                    </Flex>
                  )}
                  <Flex vertical gap={10}>
                    {data.members.map((m) => (
                      <Flex key={m.user_id} align="center" gap={10} className="p-2 rounded-lg bg-[#f7f8fa] dark:bg-white/[0.04]">
                        <Tooltip title={m.name}><Avatar className="bg-io-600">{m.name[0]}</Avatar></Tooltip>
                        <div className="min-w-0">
                          <Text className="text-[13px]" ellipsis>{m.name}</Text>
                          <div><Text type="secondary" className="text-[11px]" ellipsis>{m.designation ?? "—"}</Text></div>
                        </div>
                      </Flex>
                    ))}
                  </Flex>
                </div>
              ),
            },
            {
              key: "tasks", label: "Tasks",
              children: (
                <div>
                  {canManageMembers && (
                    <Flex justify="end" className="mb-3">
                      <Button type="primary" icon={<PlusOutlined />} onClick={() => setTaskOpen(true)}>Add Task</Button>
                    </Flex>
                  )}
                  <Card size="small" bordered={false} title="Tasks" className="mb-4">
                    {data.tasks.length === 0 ? (
                      <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No tasks yet" />
                    ) : (
                      <Table size="small" rowKey="task_id" dataSource={data.tasks} columns={taskCols}
                        pagination={{ pageSize: 8, showSizeChanger: false }} scroll={{ x: true }} />
                    )}
                  </Card>
                  {data.bugs.length > 0 && (
                    <Card size="small" bordered={false} title={`Bugs (${data.bugs.length})`}>
                      <Table size="small" rowKey="task_id" dataSource={data.bugs} columns={bugCols}
                        pagination={{ pageSize: 8, showSizeChanger: false }} scroll={{ x: true }} />
                    </Card>
                  )}
                </div>
              ),
            },
            {
              key: "timeline", label: "Timeline",
              children: (
                <Timeline
                  items={[...data.stages]
                    .sort((a, b) => (a.start_date ?? "").localeCompare(b.start_date ?? ""))
                    .map((s) => ({
                      color: s.status === "done" ? "green" : s.status === "active" ? "blue" : "gray",
                      children: (
                        <div>
                          <Text strong>{s.name}</Text>{" "}
                          <Tag color={STAGE_STATUS_TAG[s.status]} className="capitalize">{s.status}</Tag>
                          <div><Text type="secondary" className="text-[12px]">{s.start_date ?? "—"} → {s.end_date ?? "—"}</Text></div>
                          {s.description && <div><Text type="secondary" className="text-[12px]">{s.description}</Text></div>}
                        </div>
                      ),
                    }))}
                />
              ),
            },
            {
              key: "documents", label: "Documents",
              children: (
                <div>
                  <Card size="small" bordered={false} title="Upload document" className="mb-4">
                    <Flex vertical gap={10}>
                      <Input placeholder="Title" value={docTitle} onChange={(e) => setDocTitle(e.target.value)} />
                      <Select value={docKind} onChange={setDocKind} options={[
                        { value: "document", label: "Document" },
                        { value: "mom", label: "MOM" },
                        { value: "policy", label: "Policy" },
                      ]} />
                      <Upload.Dragger
                        beforeUpload={(f) => { setDocFile(f as unknown as File); return false; }}
                        maxCount={1}
                        fileList={docFile ? [{ uid: "1", name: docFile.name } as never] : []}
                        onRemove={() => setDocFile(null)}
                      >
                        <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                        <p className="ant-upload-text">Click or drag a file here</p>
                      </Upload.Dragger>
                      <Button type="primary" loading={docUploading} disabled={!docFile || !docTitle}
                        onClick={uploadDoc}>
                        Upload
                      </Button>
                    </Flex>
                  </Card>
                  {docs === null ? (
                    <Flex justify="center"><Spin /></Flex>
                  ) : docs.length === 0 ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No documents yet" />
                  ) : (
                    <List
                      dataSource={docs}
                      renderItem={(d) => (
                        <List.Item actions={[<Tag key="s">{d.status}</Tag>]}>
                          <List.Item.Meta
                            avatar={<FileTextOutlined className="text-io-600 text-lg" />}
                            title={d.title}
                            description={d.filename}
                          />
                        </List.Item>
                      )}
                    />
                  )}
                </div>
              ),
            },
            {
              key: "activity", label: "Activity",
              children:
                activity === null ? (
                  <Flex justify="center"><Spin /></Flex>
                ) : activity.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Nothing yet" />
                ) : (
                  <List
                    dataSource={activity}
                    renderItem={(a) => (
                      <List.Item>
                        <List.Item.Meta
                          avatar={<ClockCircleOutlined className="text-io-600" />}
                          title={<Text className="text-[13px]">
                            <b>{a.actor_name}</b> {ACTION_LABEL[a.action] ?? a.action}
                          </Text>}
                          description={<Text type="secondary" className="text-[11px]">
                            {new Date(a.at).toLocaleString()}
                          </Text>}
                        />
                      </List.Item>
                    )}
                  />
                ),
            },
          ]}
        />
      )}

      <Modal title="Edit Project" open={editOpen} onCancel={() => setEditOpen(false)}
        onOk={() => editForm.submit()} confirmLoading={editSaving} okText="Save">
        <Form form={editForm} layout="vertical" onFinish={saveProjectEdit}>
          <Form.Item name="name" label="Project name" rules={[{ required: true }]}>
            <Input maxLength={200} />
          </Form.Item>
          <Flex gap={12}>
            <Form.Item name="client" label="Client" className="flex-1"><Input maxLength={200} /></Form.Item>
            <Form.Item name="engagement" label="Engagement" className="flex-1"><Input maxLength={200} /></Form.Item>
          </Flex>
          <Form.Item name="description" label="Description"><Input.TextArea rows={2} /></Form.Item>
          <Flex gap={12}>
            <Form.Item name="status" label="Status" className="flex-1">
              <Select options={["planning", "active", "on_hold", "completed"].map((s) => ({ value: s, label: s }))} />
            </Form.Item>
            <Form.Item name="priority" label="Priority" className="flex-1">
              <Select options={["Low", "Medium", "High"].map((p) => ({ value: p, label: p }))} />
            </Form.Item>
          </Flex>
          <Form.Item name="project_manager_id" label="Project Manager">
            <Select showSearch allowClear optionFilterProp="label"
              options={allPeople.map((p) => ({ value: p.user_id, label: p.name }))} />
          </Form.Item>
          <Flex gap={12}>
            <Form.Item name="start_date" label="Start date" className="flex-1"><DatePicker className="w-full" /></Form.Item>
            <Form.Item name="due_date" label="Due date" className="flex-1"><DatePicker className="w-full" /></Form.Item>
          </Flex>
        </Form>
      </Modal>

      <Modal title={stageMode === "add" ? "Add Stage" : "Edit Stage"} open={stageOpen}
        onCancel={() => setStageOpen(false)} onOk={() => stageForm.submit()}
        confirmLoading={stageSaving} okText={stageMode === "add" ? "Add" : "Save"}>
        <Form form={stageForm} layout="vertical" onFinish={saveStage} initialValues={{ status: "pending", progress: 0 }}>
          <Form.Item name="name" label="Stage name" rules={[{ required: true }]}>
            <Input maxLength={100} />
          </Form.Item>
          <Form.Item name="description" label="Description"><Input.TextArea rows={2} /></Form.Item>
          <Flex gap={12}>
            <Form.Item name="status" label="Status" className="flex-1">
              <Select options={["pending", "active", "done"].map((s) => ({ value: s, label: s }))} />
            </Form.Item>
            <Form.Item name="progress" label="Progress %" className="flex-1">
              <InputNumber min={0} max={100} className="w-full" />
            </Form.Item>
          </Flex>
        </Form>
      </Modal>

      <Modal title="Add Task" open={taskOpen} onCancel={() => setTaskOpen(false)}
        onOk={() => taskForm.submit()} confirmLoading={taskSaving} okText="Create">
        <Form form={taskForm} layout="vertical" onFinish={createTask}>
          <Form.Item name="title" label="Title" rules={[{ required: true, message: "Title required" }]}>
            <Input placeholder="What needs to be done?" maxLength={300} />
          </Form.Item>
          <Form.Item name="description" label="Description"><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="assignee_id" label="Assign to" extra="Leave empty to assign to yourself">
            <Select allowClear showSearch optionFilterProp="label"
              options={(data?.members ?? []).map((m) => ({
                value: m.user_id, label: m.designation ? `${m.name} — ${m.designation}` : m.name,
              }))} />
          </Form.Item>
          <Form.Item name="stage" label="Stage" initialValue={data?.current_stage}>
            <Select options={(data?.stages ?? []).map((s) => ({ value: s.key, label: s.name }))} />
          </Form.Item>
          <Flex gap={12}>
            <Form.Item name="due_date" label="Due date" className="flex-1"><DatePicker className="w-full" /></Form.Item>
            <Form.Item name="priority" label="Priority" initialValue="Normal" className="flex-1">
              <Select options={["Low", "Normal", "High", "Immediate"].map((p) => ({ value: p, label: p }))} />
            </Form.Item>
          </Flex>
        </Form>
      </Modal>

      <Modal title="Add Members" open={memberOpen} onCancel={() => setMemberOpen(false)}
        onOk={() => memberForm.submit()} confirmLoading={memberSaving} okText="Add">
        <Form form={memberForm} layout="vertical" onFinish={addMembers}>
          <Form.Item name="member_ids" label="People to add" rules={[{ required: true, message: "Select at least one person" }]}>
            <Select mode="multiple" showSearch optionFilterProp="label"
              options={allPeople
                .filter((p) => !(data?.members ?? []).some((m) => m.user_id === p.user_id))
                .map((p) => ({ value: p.user_id, label: p.designation ? `${p.name} — ${p.designation}` : p.name }))} />
          </Form.Item>
        </Form>
      </Modal>
    </Drawer>
  );
}
