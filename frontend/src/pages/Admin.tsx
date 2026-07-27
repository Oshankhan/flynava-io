import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  List,
  message,
  Row,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import { SyncOutlined } from "@ant-design/icons";
import {
  api,
  ApiError,
  type AuditRow,
  type KpiDef,
  type NotificationItem,
  type User,
} from "../lib/api";
import { ROLES } from "../lib/rbac";
import RequireModule from "../components/RequireModule";

const { Text } = Typography;

export default function Admin() {
  return (
    <RequireModule module="admin_panel">
      <AdminPanel />
    </RequireModule>
  );
}

function AdminPanel() {
  const [defs, setDefs] = useState<KpiDef[]>([]);
  const [log, setLog] = useState<NotificationItem[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [busyUserId, setBusyUserId] = useState<string | null>(null);
  const [form] = Form.useForm();

  function loadAll() {
    api.kpiDefs().then(setDefs);
    api.notificationLog().then(setLog);
    api.listUsers().then(setUsers);
    api.auditLog().then(setAudit);
  }
  useEffect(() => {
    loadAll();
  }, []);

  async function sync() {
    setSyncing(true);
    try {
      const res = await api.syncIntegration("openproject");
      message.success(
        `OpenProject synced: ${res.records_processed ?? 0} records in ${res.duration_ms}ms`
      );
    } catch {
      message.error("Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  async function createUser(v: { name: string; email: string; role: string; password: string }) {
    setCreating(true);
    try {
      await api.createUser(v);
      message.success(`Created ${v.email}`);
      form.resetFields();
      loadAll();
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Create failed");
    } finally {
      setCreating(false);
    }
  }

  async function changeRole(u: User, role: string) {
    setBusyUserId(u.user_id);
    try {
      await api.updateUser(u.user_id, { role });
      message.success(`${u.name} → ${role}`);
      loadAll();
    } finally {
      setBusyUserId(null);
    }
  }

  async function toggleStatus(u: User) {
    const next = u.status === "inactive" ? "active" : "inactive";
    setBusyUserId(u.user_id);
    try {
      await api.updateUser(u.user_id, { status: next });
      message.success(`${u.name} ${next}`);
      loadAll();
    } finally {
      setBusyUserId(null);
    }
  }

  const usersTab = (
    <Space direction="vertical" size={16} className="w-full">
      <Card size="small" title="Create user">
        <Form form={form} layout="inline" onFinish={createUser} initialValues={{ role: "employee" }}>
          <Form.Item name="name" rules={[{ required: true }]}>
            <Input placeholder="Name" />
          </Form.Item>
          <Form.Item name="email" rules={[{ required: true, type: "email" }]}>
            <Input placeholder="Email" />
          </Form.Item>
          <Form.Item name="role">
            <Select className="w-[140px]" options={ROLES.map((r) => ({ value: r, label: r }))} />
          </Form.Item>
          <Form.Item name="password" rules={[{ required: true }]}>
            <Input.Password placeholder="Password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={creating}>
            Create
          </Button>
        </Form>
      </Card>
      <Table<User>
        dataSource={users}
        rowKey="user_id"
        size="small"
        pagination={false}
        scroll={{ x: true }}
        columns={[
          { title: "Name", dataIndex: "name", key: "name" },
          { title: "Email", dataIndex: "email", key: "email" },
          {
            title: "Role",
            key: "role",
            render: (_, u) => (
              <Select
                size="small"
                value={u.role}
                className="w-[130px]"
                loading={busyUserId === u.user_id}
                disabled={busyUserId === u.user_id}
                onChange={(v) => changeRole(u, v)}
                options={ROLES.map((r) => ({ value: r, label: r }))}
              />
            ),
          },
          {
            title: "Status",
            key: "status",
            render: (_, u) => (
              <Tag color={u.status === "inactive" ? "default" : "success"}>
                {u.status ?? "active"}
              </Tag>
            ),
          },
          {
            title: "Action",
            key: "action",
            render: (_, u) => (
              <Button size="small" loading={busyUserId === u.user_id} onClick={() => toggleStatus(u)}>
                {u.status === "inactive" ? "Activate" : "Deactivate"}
              </Button>
            ),
          },
        ]}
      />
    </Space>
  );

  return (
    <Tabs
      defaultActiveKey="users"
      items={[
        { key: "users", label: `Users (${users.length})`, children: usersTab },
        {
          key: "integrations",
          label: "Integrations",
          children: (
            <Card size="small">
              <Button type="primary" icon={<SyncOutlined />} loading={syncing} onClick={sync}>
                Sync OpenProject now
              </Button>
            </Card>
          ),
        },
        {
          key: "kpis",
          label: `KPI Definitions (${defs.length})`,
          children: (
            <Table<KpiDef>
              dataSource={defs}
              rowKey="kpi_id"
              size="small"
              pagination={{ pageSize: 10 }}
              scroll={{ x: true }}
              columns={[
                { title: "KPI", dataIndex: "name", key: "name" },
                { title: "Module", dataIndex: "module", key: "module" },
                {
                  title: "Formula",
                  dataIndex: "formula",
                  key: "formula",
                  render: (f: string) => <code className="text-xs">{f}</code>,
                },
                { title: "Target", dataIndex: "target", key: "target", render: (t) => t ?? "—" },
              ]}
            />
          ),
        },
        {
          key: "logs",
          label: "Logs",
          children: (
            <Row gutter={[16, 16]}>
              <Col xs={24} lg={12}>
                <Card size="small" title="Audit Trail">
                  <List
                    size="small"
                    dataSource={audit.slice(0, 20)}
                    renderItem={(a) => (
                      <List.Item>
                        <code className="text-xs">{a.action}</code>
                        <Text type="secondary" className="text-xs">
                          {a.actor_id ?? "system"} · {new Date(a.created_at).toLocaleString()}
                        </Text>
                      </List.Item>
                    )}
                  />
                </Card>
              </Col>
              <Col xs={24} lg={12}>
                <Card size="small" title={`Notification Log (${log.length})`}>
                  <List
                    size="small"
                    dataSource={log.slice(0, 20)}
                    renderItem={(n) => (
                      <List.Item>
                        <Text className="text-[13px]">{n.title}</Text>
                        <Tag color={n.status === "unread" ? "processing" : "default"}>
                          {n.status}
                        </Tag>
                      </List.Item>
                    )}
                  />
                </Card>
              </Col>
            </Row>
          ),
        },
      ]}
    />
  );
}
