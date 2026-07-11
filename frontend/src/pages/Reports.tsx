import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Col,
  Flex,
  Input,
  message,
  Modal,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import { MailOutlined, SendOutlined } from "@ant-design/icons";
import {
  api,
  ApiError,
  type BugReportRow,
  type ReportProject,
  type SendResult,
} from "../lib/api";

const { Text, Title } = Typography;

const PRIORITY_COLOR: Record<string, string> = {
  Immediate: "red",
  High: "volcano",
  Normal: "blue",
  Low: "default",
};

export default function Reports() {
  const [projects, setProjects] = useState<ReportProject[]>([]);
  const [project, setProject] = useState<string>();
  const [bugs, setBugs] = useState<BugReportRow[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>();
  const [priorityFilter, setPriorityFilter] = useState<string>();
  const [selected, setSelected] = useState<string[]>([]);
  const [title, setTitle] = useState("Bug Status Summary");
  const [intro, setIntro] = useState("");
  const [aiIntro, setAiIntro] = useState(true);
  const [recipients, setRecipients] = useState<string[]>([]);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SendResult | null>(null);

  useEffect(() => {
    api.reportProjects().then(setProjects).catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    if (!project) return;
    setSelected([]);
    api.reportBugs(project, statusFilter, priorityFilter).then(setBugs).catch(() => setBugs([]));
  }, [project, statusFilter, priorityFilter]);

  const statuses = useMemo(
    () => [...new Set(bugs.map((b) => b.status).filter(Boolean))],
    [bugs]
  );
  const priorities = useMemo(
    () => [...new Set(bugs.map((b) => b.priority).filter(Boolean))],
    [bugs]
  );

  async function preview() {
    if (!selected.length) return message.warning("Select at least one bug");
    setBusy(true);
    try {
      const g = await api.generateReport({ bug_ids: selected, title, ai_intro: aiIntro });
      setIntro(g.intro);
      setPreviewHtml(g.html);
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Generate failed");
    } finally {
      setBusy(false);
    }
  }

  async function send() {
    if (!selected.length) return message.warning("Select at least one bug");
    if (!recipients.length) return message.warning("Add at least one recipient");
    setBusy(true);
    try {
      const r = await api.sendReport({ bug_ids: selected, recipients, title, intro });
      setResult(r);
      setPreviewHtml(r.preview_html);
      if (r.status === "sent") message.success(r.detail);
      else message.info(r.detail);
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Send failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Space direction="vertical" size={16} style={{ width: "100%" }}>
      <Title level={4} style={{ margin: 0 }}>
        Bug Report Builder <Text type="secondary" style={{ fontSize: 14 }}>· from OpenProject</Text>
      </Title>

      <Card size="small">
        <Row gutter={[12, 12]} align="bottom">
          <Col xs={24} md={9}>
            <Text type="secondary">Project</Text>
            <Select
              placeholder="Select an OpenProject project"
              style={{ width: "100%" }}
              value={project}
              onChange={setProject}
              options={projects.map((p) => ({
                value: p.source_id,
                label: `${p.name} (${p.bug_count} bugs)`,
              }))}
            />
          </Col>
          <Col xs={12} md={5}>
            <Text type="secondary">Status</Text>
            <Select
              allowClear
              placeholder="All"
              style={{ width: "100%" }}
              value={statusFilter}
              onChange={setStatusFilter}
              options={statuses.map((s) => ({ value: s, label: s }))}
            />
          </Col>
          <Col xs={12} md={5}>
            <Text type="secondary">Priority</Text>
            <Select
              allowClear
              placeholder="All"
              style={{ width: "100%" }}
              value={priorityFilter}
              onChange={setPriorityFilter}
              options={priorities.map((p) => ({ value: p, label: p }))}
            />
          </Col>
          <Col xs={24} md={5}>
            <Text type="secondary">{selected.length} selected</Text>
          </Col>
        </Row>
      </Card>

      <Card size="small" title={`Bugs${project ? "" : " — select a project first"}`}>
        <Table<BugReportRow>
          dataSource={bugs}
          rowKey="op_id"
          size="small"
          pagination={{ pageSize: 10 }}
          rowSelection={{
            selectedRowKeys: selected,
            onChange: (keys) => setSelected(keys as string[]),
          }}
          columns={[
            {
              title: "OP ID",
              dataIndex: "op_id",
              key: "op_id",
              render: (id: string, r) => (
                <a href={r.url} target="_blank" rel="noreferrer">
                  {id}
                </a>
              ),
            },
            {
              title: "Bug Type",
              dataIndex: "bug_type",
              key: "bug_type",
              render: (t: string) => <Tag color="green">{t}</Tag>,
            },
            { title: "Bug Name", dataIndex: "bug_name", key: "bug_name", ellipsis: true },
            { title: "Status", dataIndex: "status", key: "status" },
            {
              title: "Priority",
              dataIndex: "priority",
              key: "priority",
              render: (p: string) => <Tag color={PRIORITY_COLOR[p] ?? "default"}>{p}</Tag>,
            },
            { title: "Assignee", dataIndex: "assignee", key: "assignee" },
            { title: "Accountable", dataIndex: "accountable", key: "accountable" },
          ]}
        />
      </Card>

      <Card size="small" title="Compose & Send">
        <Row gutter={[12, 12]}>
          <Col xs={24} md={12}>
            <Text type="secondary">Subject</Text>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          </Col>
          <Col xs={24} md={12}>
            <Text type="secondary">Recipients</Text>
            <Select
              mode="tags"
              style={{ width: "100%" }}
              placeholder="type an email and press Enter"
              value={recipients}
              onChange={setRecipients}
              tokenSeparators={[",", " "]}
            />
          </Col>
          <Col span={24}>
            <Flex justify="space-between" align="center">
              <Text type="secondary">Intro</Text>
              <Checkbox checked={aiIntro} onChange={(e) => setAiIntro(e.target.checked)}>
                Draft intro with AI
              </Checkbox>
            </Flex>
            <Input.TextArea
              rows={2}
              value={intro}
              onChange={(e) => setIntro(e.target.value)}
              placeholder="Leave blank + 'Draft with AI' to auto-generate, or write your own."
            />
          </Col>
        </Row>
        <Flex gap={12} style={{ marginTop: 12 }}>
          <Button icon={<MailOutlined />} loading={busy} onClick={preview}>
            Preview & draft
          </Button>
          <Button type="primary" icon={<SendOutlined />} loading={busy} onClick={send}>
            Send email
          </Button>
        </Flex>
        {result && (
          <Alert
            style={{ marginTop: 12 }}
            type={result.status === "sent" ? "success" : "info"}
            showIcon
            message={
              result.status === "sent"
                ? `Sent to ${result.recipients.join(", ")}`
                : "Preview mode — configure SMTP in backend/.env to actually send."
            }
          />
        )}
      </Card>

      <Modal
        open={!!previewHtml}
        onCancel={() => setPreviewHtml(null)}
        title="Email preview"
        width={760}
        footer={<Button onClick={() => setPreviewHtml(null)}>Close</Button>}
      >
        {previewHtml && (
          <div
            style={{ border: "1px solid #eee", padding: 16, borderRadius: 8 }}
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: previewHtml }}
          />
        )}
      </Modal>
    </Space>
  );
}
