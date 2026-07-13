import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Avatar,
  Button,
  Card,
  Col,
  Dropdown,
  Empty,
  Flex,
  Form,
  Input,
  message,
  Modal,
  Pagination,
  Row,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  Upload,
} from "antd";
import {
  BankOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  DownloadOutlined,
  EditOutlined,
  FileExcelOutlined,
  FileImageOutlined,
  FileOutlined,
  FilePdfOutlined,
  FilePptOutlined,
  FileTextOutlined,
  FileWordOutlined,
  FileZipOutlined,
  FolderOpenOutlined,
  InboxOutlined,
  PlusOutlined,
  SearchOutlined,
  SendOutlined,
  ShareAltOutlined,
  StarFilled,
  StarOutlined,
  TableOutlined,
  UnorderedListOutlined,
  UploadOutlined,
} from "@ant-design/icons";
import {
  api,
  ApiError,
  type DocStats,
  type DocTab,
  type Folder,
  type IoDocument,
  type ProjectSummary,
  type UserLite,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { levelOf } from "../components/Layout";
import StatTile from "../components/StatTile";

const { Text } = Typography;

const FILE_ICON: Record<string, { icon: React.ReactNode; color: string }> = {
  pdf: { icon: <FilePdfOutlined />, color: "#dc2626" },
  pptx: { icon: <FilePptOutlined />, color: "#ea580c" },
  ppt: { icon: <FilePptOutlined />, color: "#ea580c" },
  docx: { icon: <FileWordOutlined />, color: "#2563eb" },
  doc: { icon: <FileWordOutlined />, color: "#2563eb" },
  xlsx: { icon: <FileExcelOutlined />, color: "#16a34a" },
  xls: { icon: <FileExcelOutlined />, color: "#16a34a" },
  zip: { icon: <FileZipOutlined />, color: "#7c3aed" },
  png: { icon: <FileImageOutlined />, color: "#0891b2" },
  jpg: { icon: <FileImageOutlined />, color: "#0891b2" },
};
function fileIcon(type?: string) {
  return FILE_ICON[(type ?? "").toLowerCase()] ?? { icon: <FileOutlined />, color: "#6b7280" };
}

const STATUS_TAG: Record<string, { color: string; label: string }> = {
  draft: { color: "default", label: "Draft" },
  pending: { color: "warning", label: "Pending Review" },
  approved: { color: "success", label: "Approved" },
  rejected: { color: "error", label: "Rejected" },
};

const TAB_ITEMS: { key: DocTab; label: string }[] = [
  { key: "all", label: "All Documents" },
  { key: "mine", label: "My Documents" },
  { key: "shared", label: "Shared With Me" },
  { key: "starred", label: "Starred" },
];

export default function Documents() {
  const { user } = useAuth();
  const level = levelOf(user);
  const isManager = level >= 3;

  const [folders, setFolders] = useState<Folder[] | null>(null);
  const [activeFolder, setActiveFolder] = useState<string | null>(null);
  const [tab, setTab] = useState<DocTab>("all");
  const [sort, setSort] = useState<"newest" | "oldest" | "name" | "size">("newest");
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [projectFilter, setProjectFilter] = useState("all");
  const [view, setView] = useState<"list" | "grid">("list");
  const [gridPage, setGridPage] = useState(1);
  const GRID_PAGE_SIZE = 12;

  const [docs, setDocs] = useState<IoDocument[] | null>(null);
  const [stats, setStats] = useState<DocStats | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadForm] = Form.useForm();

  const [folderModalOpen, setFolderModalOpen] = useState(false);
  const [folderSaving, setFolderSaving] = useState(false);
  const [editingFolder, setEditingFolder] = useState<Folder | null>(null);
  const [folderForm] = Form.useForm();

  const [shareOpen, setShareOpen] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [shareDoc, setShareDoc] = useState<IoDocument | null>(null);
  const [people, setPeople] = useState<UserLite[]>([]);
  const [shareForm] = Form.useForm();

  const loadFolders = useCallback(() => {
    api.folders().then(setFolders).catch(() => setFolders([]));
  }, []);
  const loadStats = useCallback(() => {
    api.documentStats().then(setStats).catch(() => setStats(null));
  }, []);
  const loadDocs = useCallback(() => {
    api.documents({
      folderId: activeFolder ?? undefined,
      projectId: projectFilter !== "all" ? projectFilter : undefined,
      q: search || undefined,
      fileType: typeFilter !== "all" ? typeFilter : undefined,
      docStatus: statusFilter !== "all" ? statusFilter : undefined,
      tab, sort,
    })
      .then(setDocs)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load documents"));
  }, [activeFolder, projectFilter, search, typeFilter, statusFilter, tab, sort]);

  useEffect(loadFolders, [loadFolders]);
  useEffect(loadStats, [loadStats]);
  useEffect(loadDocs, [loadDocs]);
  useEffect(() => setGridPage(1), [activeFolder, tab, sort, search, typeFilter, statusFilter, projectFilter]);
  useEffect(() => {
    api.projects().then(setProjects).catch(() => setProjects([]));
  }, []);
  useEffect(() => {
    if (uploadOpen || shareOpen) api.orgUsers().then(setPeople).catch(() => setPeople([]));
  }, [uploadOpen, shareOpen]);

  const refreshAll = useCallback(() => {
    loadDocs();
    loadFolders();
    loadStats();
  }, [loadDocs, loadFolders, loadStats]);

  async function doUpload(values: { title: string; kind: string; folder_id?: string; project_id?: string }) {
    if (!uploadFile) return message.error("Choose a file");
    setUploading(true);
    try {
      await api.uploadDocument(values.title, values.kind, uploadFile, {
        folderId: values.folder_id, projectId: values.project_id,
      });
      message.success("Saved as draft — submit it for approval when ready");
      setUploadOpen(false);
      uploadForm.resetFields();
      setUploadFile(null);
      refreshAll();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function saveFolder(values: { name: string; description?: string; category?: string;
    roles?: string[]; teams?: string[] }) {
    setFolderSaving(true);
    try {
      if (editingFolder) {
        await api.updateFolder(editingFolder.folder_id, values);
        message.success("Folder updated");
      } else {
        await api.createFolder(values);
        message.success("Folder created");
      }
      setFolderModalOpen(false);
      setEditingFolder(null);
      folderForm.resetFields();
      loadFolders();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setFolderSaving(false);
    }
  }

  async function submit(doc: IoDocument) {
    try {
      await api.submitDocument(doc.doc_id);
      message.success("Submitted for approval");
      refreshAll();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Submit failed");
    }
  }
  async function decide(doc: IoDocument, decision: "approve" | "reject") {
    try {
      await api.decideDocument(doc.doc_id, decision);
      message.success(`Document ${decision}d`);
      refreshAll();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Action failed");
    }
  }
  async function toggleStar(doc: IoDocument) {
    try {
      await api.starDocument(doc.doc_id);
      loadDocs();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Action failed");
    }
  }
  async function doShare(values: { user_ids: string[] }) {
    if (!shareDoc) return;
    setSharing(true);
    try {
      await api.shareDocument(shareDoc.doc_id, values.user_ids);
      message.success("Document shared");
      setShareOpen(false);
      shareForm.resetFields();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Share failed");
    } finally {
      setSharing(false);
    }
  }
  async function doDelete(doc: IoDocument) {
    try {
      await api.deleteDocument(doc.doc_id);
      message.success("Document deleted");
      refreshAll();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Delete failed");
    }
  }
  async function download(doc: IoDocument) {
    try {
      await api.downloadDocument(doc.doc_id, doc.filename || doc.title);
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Download failed");
    }
  }

  const pendingCount = stats?.pending_approval ?? 0;

  const columns = useMemo(() => [
    {
      title: "Document Name", key: "name",
      render: (_: unknown, d: IoDocument) => {
        const { icon, color } = fileIcon(d.file_type);
        const folderName = folders?.find((f) => f.folder_id === d.folder_id)?.name;
        const starred = (d.starred_by ?? []).includes(user?.user_id ?? "");
        return (
          <Flex align="center" gap={10}>
            <span style={{ color }} className="text-xl">{icon}</span>
            <div className="min-w-0">
              <Text strong className="text-[13px]" ellipsis>{d.title}</Text>
              <div><Text type="secondary" className="text-[11px]">{folderName ?? "—"}</Text></div>
            </div>
            <Button
              type="text" size="small"
              icon={starred ? <StarFilled className="text-amber-400" /> : <StarOutlined />}
              onClick={() => toggleStar(d)}
            />
          </Flex>
        );
      },
    },
    {
      title: "Project", dataIndex: "project_id", key: "project",
      render: (pid: string | null) => {
        const p = projects.find((pr) => pr.project_id === pid);
        return p ? <Text className="text-[12px]">{p.name} ({p.code})</Text> : <Text type="secondary">—</Text>;
      },
    },
    {
      title: "Type", dataIndex: "file_type", key: "type", width: 90,
      render: (t: string) => {
        const { color } = fileIcon(t);
        return <Tag color={color} className="uppercase">{t ?? "file"}</Tag>;
      },
    },
    {
      title: "Owner", key: "owner",
      render: (_: unknown, d: IoDocument) => (
        <Flex align="center" gap={8}>
          <Avatar size="small" className="bg-io-600">{(d.uploaded_by_name ?? "?")[0]}</Avatar>
          <Text className="text-[12px]">{d.uploaded_by_name ?? d.uploaded_by}</Text>
        </Flex>
      ),
    },
    {
      title: "Status", dataIndex: "status", key: "status", width: 130,
      render: (s: string) => {
        const cfg = STATUS_TAG[s] ?? { color: "default", label: s };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: "Updated", dataIndex: "updated_at", key: "updated", width: 130,
      render: (d: string | undefined) => d ? (
        <div>
          <div className="text-[12px]">{new Date(d).toLocaleDateString()}</div>
          <Text type="secondary" className="text-[11px]">
            {new Date(d).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </Text>
        </div>
      ) : "—",
    },
    {
      title: "", key: "actions", width: 50,
      render: (_: unknown, d: IoDocument) => {
        const isOwner = d.uploaded_by === user?.user_id;
        const items = [
          d.source !== "seed" && { key: "download", icon: <DownloadOutlined />, label: "Download" },
          isOwner && d.status === "draft" && { key: "submit", icon: <SendOutlined />, label: "Submit for approval" },
          isManager && d.status === "pending" && { key: "approve", icon: <CheckCircleOutlined />, label: "Approve" },
          isManager && d.status === "pending" && { key: "reject", label: "Reject", danger: true },
          isManager && { key: "share", icon: <ShareAltOutlined />, label: "Allot / Share" },
          (isManager || (isOwner && d.status === "draft")) &&
            { key: "delete", icon: <DeleteOutlined />, label: "Delete", danger: true },
        ].filter(Boolean) as { key: string; icon?: React.ReactNode; label: string; danger?: boolean }[];
        return (
          <Dropdown
            menu={{
              items,
              onClick: ({ key }) => {
                if (key === "download") download(d);
                else if (key === "submit") submit(d);
                else if (key === "approve") decide(d, "approve");
                else if (key === "reject") decide(d, "reject");
                else if (key === "delete") doDelete(d);
                else if (key === "share") { setShareDoc(d); setShareOpen(true); }
              },
            }}
          >
            <Button type="text" size="small">⋮</Button>
          </Dropdown>
        );
      },
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
  ], [folders, projects, isManager, user?.user_id]);

  if (error) return <Alert type="error" message={error} showIcon />;

  const totalDocs = stats?.total_documents ?? 0;

  return (
    <div>
      <Flex gap={8} wrap className="mb-4">
        <Input
          placeholder="Search documents..."
          prefix={<SearchOutlined className="text-gray-400" />}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
          allowClear
        />
        <Select
          value={projectFilter} onChange={setProjectFilter} className="w-40"
          options={[{ value: "all", label: "All Projects" },
            ...projects.map((p) => ({ value: p.project_id, label: `${p.name} (${p.code})` }))]}
        />
        <Select
          value={typeFilter} onChange={setTypeFilter} className="w-36"
          options={[{ value: "all", label: "All Types" },
            ...["pdf", "pptx", "docx", "xlsx", "zip", "png"].map((t) => ({ value: t, label: t.toUpperCase() }))]}
        />
        <Select
          value={statusFilter} onChange={setStatusFilter} className="w-40"
          options={[{ value: "all", label: "All Statuses" },
            { value: "draft", label: "Draft" }, { value: "pending", label: "Pending Review" },
            { value: "approved", label: "Approved" }, { value: "rejected", label: "Rejected" }]}
        />
        <div className="flex-1" />
        <Space.Compact>
          <Button type={view === "list" ? "primary" : "default"} icon={<UnorderedListOutlined />}
            onClick={() => setView("list")} />
          <Button type={view === "grid" ? "primary" : "default"} icon={<TableOutlined />}
            onClick={() => setView("grid")} />
        </Space.Compact>
        <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadOpen(true)}>
          Upload Document
        </Button>
      </Flex>

      <Row gutter={[16, 16]} className="mb-4">
        <Col xs={24} sm={8}>
          <StatTile icon={<FolderOpenOutlined />} tint="green" value={String(totalDocs)}
            label="Total Documents" sub={stats ? `↑ ${stats.uploaded_this_month} this month` : undefined} subTone="up" />
        </Col>
        <Col xs={24} sm={8}>
          <StatTile icon={<FileTextOutlined />} tint="blue" value={String(stats?.marketing_assets ?? 0)}
            label="Marketing Assets"
            sub={stats && totalDocs > 0 ? `${Math.round((stats.marketing_assets / totalDocs) * 100)}% of total` : undefined} />
        </Col>
        <Col xs={24} sm={8}>
          <StatTile icon={<CheckCircleOutlined />} tint="amber" value={String(pendingCount)}
            label="Pending Approval" sub={pendingCount > 0 ? `${pendingCount} requires action` : "All clear"}
            subTone={pendingCount > 0 ? "warn" : "muted"} />
        </Col>
      </Row>

      <Row gutter={16}>
        <Col xs={24} lg={6}>
          <Card
            size="small" bordered={false} className="mb-4"
            title="Folders"
            extra={isManager && (
              <Button size="small" type="text" icon={<PlusOutlined />}
                onClick={() => { setEditingFolder(null); folderForm.resetFields(); setFolderModalOpen(true); }} />
            )}
          >
            {folders === null ? (
              <Flex justify="center" className="py-6"><Spin /></Flex>
            ) : (
              <Flex vertical gap={2}>
                <Flex
                  justify="space-between" align="center"
                  className={`px-2 py-1.5 rounded-lg cursor-pointer ${activeFolder === null ? "bg-io-600/10 text-io-600" : ""}`}
                  onClick={() => setActiveFolder(null)}
                >
                  <Text strong={activeFolder === null} className="text-sm">
                    <BankOutlined className="mr-2" />All Documents
                  </Text>
                  <Text type="secondary" className="text-[12px]">{totalDocs}</Text>
                </Flex>
                {folders.map((f) => (
                  <Flex
                    key={f.folder_id} justify="space-between" align="center"
                    className={`px-2 py-1.5 rounded-lg cursor-pointer group ${activeFolder === f.folder_id ? "bg-io-600/10 text-io-600" : ""}`}
                    onClick={() => setActiveFolder(f.folder_id)}
                  >
                    <Text strong={activeFolder === f.folder_id} className="text-sm" ellipsis>
                      <FolderOpenOutlined className="mr-2" />{f.name}
                    </Text>
                    <Flex align="center" gap={6}>
                      <Text type="secondary" className="text-[12px]">{f.document_count}</Text>
                      {isManager && (
                        <Tooltip title="Edit folder">
                          <EditOutlined
                            className="text-gray-400 hover:text-io-600 opacity-0 group-hover:opacity-100"
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingFolder(f);
                              folderForm.setFieldsValue({
                                name: f.name, description: f.description, category: f.category,
                                roles: f.roles, teams: f.teams,
                              });
                              setFolderModalOpen(true);
                            }}
                          />
                        </Tooltip>
                      )}
                    </Flex>
                  </Flex>
                ))}
              </Flex>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={18}>
          <Card size="small" bordered={false}>
            <Flex justify="space-between" align="center" wrap gap={8} className="mb-2">
              <Tabs
                activeKey={tab}
                onChange={(k) => setTab(k as DocTab)}
                items={TAB_ITEMS}
                className="flex-1 min-w-0"
              />
              <Select
                value={sort} onChange={setSort} size="small" className="w-40"
                options={[
                  { value: "newest", label: "Sort by: Newest" }, { value: "oldest", label: "Sort by: Oldest" },
                  { value: "name", label: "Sort by: Name" }, { value: "size", label: "Sort by: Size" },
                ]}
              />
            </Flex>

            {docs === null ? (
              <Flex justify="center" className="pt-16"><Spin /></Flex>
            ) : docs.length === 0 ? (
              <Empty description="No documents match your filters." />
            ) : view === "list" ? (
              <Table
                size="small" rowKey="doc_id" dataSource={docs} columns={columns}
                pagination={{ pageSize: 10, showTotal: (t, r) => `Showing ${r[0]} to ${r[1]} of ${t} documents` }}
                scroll={{ x: true }}
              />
            ) : (
              <>
                <Row gutter={[12, 12]}>
                  {docs.slice((gridPage - 1) * GRID_PAGE_SIZE, gridPage * GRID_PAGE_SIZE).map((d) => {
                    const { icon, color } = fileIcon(d.file_type);
                    const cfg = STATUS_TAG[d.status] ?? { color: "default", label: d.status };
                    return (
                      <Col key={d.doc_id} xs={24} sm={12} md={8} xl={6}>
                        <Card size="small" className="h-full">
                          <Flex vertical gap={6}>
                            <span style={{ color }} className="text-2xl">{icon}</span>
                            <Text strong className="text-[13px]" ellipsis>{d.title}</Text>
                            <Tag color={cfg.color}>{cfg.label}</Tag>
                          </Flex>
                        </Card>
                      </Col>
                    );
                  })}
                </Row>
                <Flex justify="end" className="mt-4">
                  <Pagination
                    current={gridPage}
                    pageSize={GRID_PAGE_SIZE}
                    total={docs.length}
                    onChange={setGridPage}
                    showTotal={(t, r) => `Showing ${r[0]} to ${r[1]} of ${t} documents`}
                  />
                </Flex>
              </>
            )}
          </Card>
        </Col>
      </Row>

      <Modal
        title="Upload Document" open={uploadOpen} onCancel={() => setUploadOpen(false)}
        onOk={() => uploadForm.submit()} confirmLoading={uploading} okText="Upload"
      >
        <Form form={uploadForm} layout="vertical" onFinish={doUpload} initialValues={{ kind: "document" }}>
          <Form.Item name="title" label="Title" rules={[{ required: true }]}>
            <Input placeholder="Document title" />
          </Form.Item>
          <Flex gap={12}>
            <Form.Item name="kind" label="Type" className="flex-1">
              <Select options={[{ value: "document", label: "Document" }, { value: "mom", label: "MOM" },
                { value: "policy", label: "Policy" }]} />
            </Form.Item>
            <Form.Item name="folder_id" label="Folder" className="flex-1">
              <Select allowClear placeholder="No folder"
                options={(folders ?? []).map((f) => ({ value: f.folder_id, label: f.name }))} />
            </Form.Item>
          </Flex>
          <Form.Item name="project_id" label="Project (optional)">
            <Select allowClear placeholder="No project"
              options={projects.map((p) => ({ value: p.project_id, label: `${p.name} (${p.code})` }))} />
          </Form.Item>
          <Form.Item label="File" required>
            <Upload.Dragger
              beforeUpload={(f) => { setUploadFile(f as File); return false; }}
              maxCount={1}
              fileList={uploadFile ? [{ uid: "1", name: uploadFile.name } as never] : []}
              onRemove={() => setUploadFile(null)}
            >
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text">Click or drag a file to upload</p>
            </Upload.Dragger>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={editingFolder ? "Edit Folder" : "Create Folder"} open={folderModalOpen}
        onCancel={() => setFolderModalOpen(false)} onOk={() => folderForm.submit()}
        confirmLoading={folderSaving} okText={editingFolder ? "Save" : "Create"}
      >
        <Form form={folderForm} layout="vertical" onFinish={saveFolder} initialValues={{ category: "general" }}>
          <Form.Item name="name" label="Folder name" rules={[{ required: true }]}>
            <Input maxLength={100} />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="category" label="Category">
            <Select options={["general", "marketing", "product"].map((c) => ({ value: c, label: c }))} />
          </Form.Item>
          <Form.Item name="roles" label="Visible to roles" extra="Leave empty to make visible to everyone">
            <Select mode="tags" placeholder="e.g. marketing, manager, hr" />
          </Form.Item>
          <Form.Item name="teams" label="Visible to teams">
            <Select mode="tags" placeholder="e.g. team_marketing" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`Allot "${shareDoc?.title ?? ""}"`} open={shareOpen}
        onCancel={() => setShareOpen(false)} onOk={() => shareForm.submit()}
        confirmLoading={sharing} okText="Share"
      >
        <Form form={shareForm} layout="vertical" onFinish={doShare}>
          <Form.Item name="user_ids" label="Share with" rules={[{ required: true, message: "Select at least one person" }]}>
            <Select mode="multiple" showSearch optionFilterProp="label"
              options={people.map((p) => ({
                value: p.user_id, label: p.designation ? `${p.name} — ${p.designation}` : p.name,
              }))} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
