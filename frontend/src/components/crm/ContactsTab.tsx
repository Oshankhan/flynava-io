import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Avatar,
  Button,
  Card,
  DatePicker,
  Dropdown,
  Empty,
  Flex,
  Form,
  Input,
  Modal,
  Popover,
  Segmented,
  Select,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import {
  AppstoreOutlined,
  BankOutlined,
  DownOutlined,
  MailOutlined,
  MoreOutlined,
  PhoneOutlined,
  PlusOutlined,
  SaveOutlined,
  SearchOutlined,
  UnorderedListOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import {
  api,
  ApiError,
  type ContactStatus,
  type ContactType,
  type CrmContact,
} from "../../lib/api";
import { useAsyncAction } from "../../lib/useAsyncAction";

const { Text } = Typography;
const { RangePicker } = DatePicker;

const TYPE_TAG: Record<ContactType, string> = {
  primary: "success",
  technical: "blue",
  business: "gold",
  finance: "purple",
  other: "default",
};
const TYPE_LABEL: Record<ContactType, string> = {
  primary: "Primary",
  technical: "Technical",
  business: "Business",
  finance: "Finance",
  other: "Other",
};
const STATUS_TAG: Record<ContactStatus, string> = { active: "success", inactive: "error" };
const AVATAR_COLORS = ["#087f5b", "#1864ab", "#9c36b5", "#e8590c", "#5f3dc4", "#c2255c"];
function avatarColor(name: string): string {
  const idx = name.split("").reduce((a, c) => a + c.charCodeAt(0), 0) % AVATAR_COLORS.length;
  return AVATAR_COLORS[idx];
}
function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase();
}

interface SavedView {
  name: string;
  search: string;
  type: string;
  department: string;
  status: string;
  from?: string;
  to?: string;
}

const PAGE_SIZE = 8;

export default function ContactsTab({
  projectId, canDelete,
}: {
  projectId: string;
  canDelete: boolean;
}) {
  const [contacts, setContacts] = useState<CrmContact[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"list" | "grid">("list");
  const [page, setPage] = useState(1);

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [deptFilter, setDeptFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [dateRange, setDateRange] = useState<[string, string] | null>(null);

  const [savedViews, setSavedViews] = useState<SavedView[]>([]);
  const [saveViewOpen, setSaveViewOpen] = useState(false);
  const [viewName, setViewName] = useState("");

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CrmContact | null>(null);
  const [form] = Form.useForm();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const storageKey = `crm_saved_views_${projectId}`;

  const load = useCallback(() => {
    api.projectContacts(projectId).then(setContacts)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load contacts"));
  }, [projectId]);

  useEffect(load, [load]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      setSavedViews(raw ? JSON.parse(raw) : []);
    } catch {
      setSavedViews([]);
    }
  }, [storageKey]);

  useEffect(() => setPage(1), [search, typeFilter, deptFilter, statusFilter, dateRange]);

  const [runSave, savingContact] = useAsyncAction(async (values: {
    name: string; title?: string; department?: string; email?: string; phone?: string;
    contact_type: ContactType; status: ContactStatus; last_contact?: dayjs.Dayjs | null;
  }) => {
    const body = {
      name: values.name, title: values.title ?? "", department: values.department ?? "",
      email: values.email ?? "", phone: values.phone ?? "", contact_type: values.contact_type,
      status: values.status,
      last_contact: values.last_contact ? values.last_contact.format("YYYY-MM-DD") : null,
    };
    try {
      if (editing) await api.updateContact(projectId, editing.contact_id, body);
      else await api.createContact(projectId, body);
      message.success(editing ? "Contact updated" : "Contact added");
      setModalOpen(false);
      form.resetFields();
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Save failed");
    }
  });

  async function removeContact(c: CrmContact) {
    setDeletingId(c.contact_id);
    try {
      await api.deleteContact(projectId, c.contact_id);
      message.success("Contact deleted");
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  }

  function openAdd() {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ contact_type: "other", status: "active" });
    setModalOpen(true);
  }
  function openEdit(c: CrmContact) {
    setEditing(c);
    form.setFieldsValue({
      name: c.name, title: c.title, department: c.department, email: c.email, phone: c.phone,
      contact_type: c.contact_type, status: c.status,
      last_contact: c.last_contact ? dayjs(c.last_contact) : null,
    });
    setModalOpen(true);
  }

  function applyView(v: SavedView) {
    setSearch(v.search);
    setTypeFilter(v.type);
    setDeptFilter(v.department);
    setStatusFilter(v.status);
    setDateRange(v.from && v.to ? [v.from, v.to] : null);
  }
  function saveView() {
    if (!viewName.trim()) return;
    const v: SavedView = {
      name: viewName.trim(), search, type: typeFilter, department: deptFilter,
      status: statusFilter, from: dateRange?.[0], to: dateRange?.[1],
    };
    const next = [...savedViews.filter((s) => s.name !== v.name), v];
    setSavedViews(next);
    localStorage.setItem(storageKey, JSON.stringify(next));
    setSaveViewOpen(false);
    setViewName("");
    message.success("View saved");
  }

  const departments = useMemo(
    () => Array.from(new Set((contacts ?? []).map((c) => c.department).filter(Boolean))) as string[],
    [contacts]
  );

  const filtered = useMemo(() => {
    if (!contacts) return [];
    const q = search.trim().toLowerCase();
    return contacts.filter((c) => {
      const matchesQ = !q || c.name.toLowerCase().includes(q) ||
        (c.email ?? "").toLowerCase().includes(q) || (c.title ?? "").toLowerCase().includes(q);
      const matchesType = typeFilter === "all" || c.contact_type === typeFilter;
      const matchesDept = deptFilter === "all" || c.department === deptFilter;
      const matchesStatus = statusFilter === "all" || c.status === statusFilter;
      const matchesDate = !dateRange || !c.last_contact ||
        (c.last_contact >= dateRange[0] && c.last_contact <= dateRange[1]);
      return matchesQ && matchesType && matchesDept && matchesStatus && matchesDate;
    });
  }, [contacts, search, typeFilter, deptFilter, statusFilter, dateRange]);

  const pageStart = (page - 1) * PAGE_SIZE;
  const pageRows = filtered.slice(pageStart, pageStart + PAGE_SIZE);

  const columns = [
    {
      title: "Name", key: "name",
      render: (_: unknown, c: CrmContact) => (
        <Flex align="center" gap={8}>
          <Avatar size={28} style={{ backgroundColor: avatarColor(c.name) }} className="text-[11px]">
            {initials(c.name)}
          </Avatar>
          <Text className="text-[13px]">{c.name}</Text>
        </Flex>
      ),
    },
    { title: "Job Title", dataIndex: "title", key: "title", ellipsis: true,
      render: (t?: string) => t || "—" },
    { title: "Department", dataIndex: "department", key: "department", ellipsis: true,
      render: (d?: string) => d || "—" },
    { title: "Email", dataIndex: "email", key: "email", ellipsis: true,
      render: (e?: string) => e ? <a href={`mailto:${e}`}>{e}</a> : "—" },
    { title: "Phone", dataIndex: "phone", key: "phone", ellipsis: true,
      render: (p?: string) => p || "—" },
    {
      title: "Type", key: "type", width: 100,
      render: (_: unknown, c: CrmContact) => (
        <Tag color={TYPE_TAG[c.contact_type]}>{TYPE_LABEL[c.contact_type]}</Tag>
      ),
    },
    {
      title: "Status", key: "status", width: 90,
      render: (_: unknown, c: CrmContact) => (
        <Tag color={STATUS_TAG[c.status]} className="capitalize">{c.status}</Tag>
      ),
    },
    { title: "Last Contact", dataIndex: "last_contact", key: "last_contact", width: 110,
      render: (d?: string | null) => d ?? "—" },
    {
      title: "Actions", key: "actions", width: 110,
      render: (_: unknown, c: CrmContact) => (
        <Flex gap={4}>
          {c.phone && (
            <Button size="small" type="text" icon={<PhoneOutlined />}
              href={`tel:${c.phone}`} />
          )}
          {c.email && (
            <Button size="small" type="text" icon={<MailOutlined />}
              href={`mailto:${c.email}`} />
          )}
          <Dropdown
            disabled={deletingId === c.contact_id}
            menu={{
              items: [
                { key: "edit", label: "Edit" },
                ...(canDelete ? [{ key: "delete", label: "Delete", danger: true }] : []),
              ],
              onClick: ({ key }) => {
                if (key === "edit") openEdit(c);
                else if (key === "delete") {
                  Modal.confirm({
                    title: `Delete ${c.name}?`,
                    okText: "Delete",
                    okButtonProps: { danger: true },
                    onOk: () => removeContact(c),
                  });
                }
              },
            }}
          >
            <Button size="small" type="text" icon={<MoreOutlined />}
              loading={deletingId === c.contact_id} />
          </Dropdown>
        </Flex>
      ),
    },
  ];

  if (error) return <Text type="danger">{error}</Text>;
  if (!contacts) return <Flex justify="center" className="pt-16"><Spin /></Flex>;

  return (
    <div>
      <Card size="small" bordered={false} className="mb-3">
        <Flex gap={8} wrap align="center">
          <Input
            placeholder="Search contacts..."
            prefix={<SearchOutlined className="text-gray-400" />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full sm:w-56"
            allowClear
          />
          <Select
            value={typeFilter}
            onChange={setTypeFilter}
            className="w-full sm:w-40"
            options={[
              { value: "all", label: "All Contact Types" },
              ...(Object.keys(TYPE_LABEL) as ContactType[]).map((t) => ({ value: t, label: TYPE_LABEL[t] })),
            ]}
          />
          <Select
            value={deptFilter}
            onChange={setDeptFilter}
            className="w-full sm:w-44"
            options={[
              { value: "all", label: "All Departments" },
              ...departments.map((d) => ({ value: d, label: d })),
            ]}
          />
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            className="w-full sm:w-36"
            options={[
              { value: "all", label: "All Statuses" },
              { value: "active", label: "Active" },
              { value: "inactive", label: "Inactive" },
            ]}
          />
          <Popover
            trigger="click"
            title="Last contact date"
            content={
              <RangePicker
                onChange={(_, formatted) =>
                  setDateRange(formatted[0] && formatted[1] ? [formatted[0], formatted[1]] : null)
                }
              />
            }
          >
            <Button>More Filters</Button>
          </Popover>
          <Dropdown
            trigger={["click"]}
            menu={{
              items: [
                ...savedViews.map((v) => ({ key: v.name, label: v.name })),
                ...(savedViews.length ? [{ type: "divider" as const }] : []),
                { key: "__save", icon: <SaveOutlined />, label: "Save current view…" },
              ],
              onClick: ({ key }) => {
                if (key === "__save") setSaveViewOpen(true);
                else applyView(savedViews.find((v) => v.name === key)!);
              },
            }}
          >
            <Button>Saved Views <DownOutlined /></Button>
          </Dropdown>
          <div className="flex-1" />
          <Button type="primary" icon={<PlusOutlined />} onClick={openAdd}>
            Add Contact
          </Button>
        </Flex>
      </Card>

      <Card
        size="small"
        title={`Contacts (${filtered.length})`}
        extra={
          <Segmented
            value={view}
            onChange={(v) => setView(v as "list" | "grid")}
            options={[
              { value: "list", icon: <UnorderedListOutlined /> },
              { value: "grid", icon: <AppstoreOutlined /> },
            ]}
          />
        }
      >
        {filtered.length === 0 ? (
          <Empty description="No contacts match your filters." />
        ) : view === "list" ? (
          <>
            <Table
              size="small"
              rowKey="contact_id"
              rowSelection={{}}
              dataSource={pageRows}
              columns={columns}
              pagination={false}
              scroll={{ x: true }}
            />
            <Flex justify="space-between" align="center" className="mt-3">
              <Text type="secondary" className="text-[12px]">
                Showing {filtered.length === 0 ? 0 : pageStart + 1} to{" "}
                {Math.min(pageStart + PAGE_SIZE, filtered.length)} of {filtered.length} contacts
              </Text>
              <Flex gap={4}>
                <Button size="small" disabled={page <= 1} onClick={() => setPage(page - 1)}>
                  Prev
                </Button>
                <Button size="small" disabled={pageStart + PAGE_SIZE >= filtered.length}
                  onClick={() => setPage(page + 1)}>
                  Next
                </Button>
              </Flex>
            </Flex>
          </>
        ) : (
          <Flex wrap gap={12}>
            {pageRows.map((c) => (
              <Card key={c.contact_id} size="small" className="w-full sm:w-[calc(50%-6px)] lg:w-[calc(33.33%-8px)]">
                <Flex align="center" gap={10} className="mb-2">
                  <Avatar size={36} style={{ backgroundColor: avatarColor(c.name) }}>
                    {initials(c.name)}
                  </Avatar>
                  <div className="min-w-0">
                    <Text strong className="text-[13px]" ellipsis>{c.name}</Text>
                    <div><Text type="secondary" className="text-[11px]" ellipsis>{c.title || "—"}</Text></div>
                  </div>
                </Flex>
                <Flex gap={4} wrap className="mb-2">
                  <Tag color={TYPE_TAG[c.contact_type]}>{TYPE_LABEL[c.contact_type]}</Tag>
                  <Tag color={STATUS_TAG[c.status]} className="capitalize">{c.status}</Tag>
                </Flex>
                <div className="flex items-center gap-1 text-[12px] text-gray-500">
                  <BankOutlined /> {c.department || "—"}
                </div>
                {c.email && <div className="text-[12px]"><a href={`mailto:${c.email}`}>{c.email}</a></div>}
                {c.phone && <div className="text-[12px] text-gray-500">{c.phone}</div>}
                <Flex justify="end" className="mt-2">
                  <Button size="small" onClick={() => openEdit(c)}>Edit</Button>
                </Flex>
              </Card>
            ))}
          </Flex>
        )}
      </Card>

      <Modal
        title={editing ? "Edit Contact" : "Add Contact"}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={savingContact}
        okText={editing ? "Save" : "Add"}
      >
        <Form form={form} layout="vertical" onFinish={runSave}>
          <Form.Item name="name" label="Name" rules={[{ required: true, message: "Required" }]}>
            <Input maxLength={200} />
          </Form.Item>
          <Flex gap={12}>
            <Form.Item name="title" label="Job Title" className="flex-1">
              <Input maxLength={150} />
            </Form.Item>
            <Form.Item name="department" label="Department" className="flex-1">
              <Input maxLength={150} />
            </Form.Item>
          </Flex>
          <Flex gap={12}>
            <Form.Item name="email" label="Email" className="flex-1">
              <Input type="email" maxLength={200} />
            </Form.Item>
            <Form.Item name="phone" label="Phone" className="flex-1">
              <Input maxLength={40} />
            </Form.Item>
          </Flex>
          <Flex gap={12}>
            <Form.Item name="contact_type" label="Type" className="flex-1" initialValue="other">
              <Select options={(Object.keys(TYPE_LABEL) as ContactType[]).map((t) => ({ value: t, label: TYPE_LABEL[t] }))} />
            </Form.Item>
            <Form.Item name="status" label="Status" className="flex-1" initialValue="active">
              <Select options={[{ value: "active", label: "Active" }, { value: "inactive", label: "Inactive" }]} />
            </Form.Item>
          </Flex>
          <Form.Item name="last_contact" label="Last Contact">
            <DatePicker className="w-full" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Save current view"
        open={saveViewOpen}
        onCancel={() => setSaveViewOpen(false)}
        onOk={saveView}
        okText="Save"
      >
        <Input
          placeholder="View name"
          value={viewName}
          onChange={(e) => setViewName(e.target.value)}
          onPressEnter={saveView}
        />
      </Modal>
    </div>
  );
}
