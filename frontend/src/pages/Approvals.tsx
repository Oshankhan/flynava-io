import { useCallback, useEffect, useState } from "react";
import {
  Button,
  Card,
  DatePicker,
  Empty,
  Flex,
  Form,
  Input,
  message,
  Modal,
  Select,
  Space,
  Table,
  Tabs,
  Tag,
  Timeline,
  Typography,
} from "antd";
import type { Dayjs } from "dayjs";
import { PlusOutlined } from "@ant-design/icons";
import { api, ApiError, type IoRequest } from "../lib/api";
import { useAuth } from "../lib/auth";
import { levelOf } from "../components/Layout";

const { Text } = Typography;
const { RangePicker } = DatePicker;

const TYPES = [
  { value: "general", label: "General Request" },
  { value: "hr_grievance", label: "Report to HR (Grievance)" },
  { value: "leave", label: "Leave Request" },
  { value: "reimbursement", label: "Reimbursement" },
  { value: "document", label: "Document Approval" },
];

const LEAVE_TYPES = ["Casual", "Sick", "Earned"];

const STATUS_TAG: Record<string, string> = {
  pending: "processing",
  approved: "success",
  rejected: "error",
};

function History({ req }: { req: IoRequest }) {
  return (
    <Timeline
      style={{ marginTop: 8 }}
      items={req.history.map((h) => ({
        color: h.action === "approved" ? "green" : h.action === "rejected" ? "red" : "blue",
        children: (
          <Text style={{ fontSize: 12 }}>
            <b>{h.by_name ?? h.by}</b> {h.action}
            {h.comment ? ` — “${h.comment}”` : ""}
            <Text type="secondary" style={{ fontSize: 11 }}>
              {" "}
              {h.at ? new Date(h.at).toLocaleString() : ""}
            </Text>
          </Text>
        ),
      }))}
    />
  );
}

export default function Approvals() {
  const { user } = useAuth();
  const isApprover = levelOf(user) >= 2;
  const [mine, setMine] = useState<IoRequest[]>([]);
  const [inbox, setInbox] = useState<IoRequest[]>([]);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const selectedType = Form.useWatch("type", form);

  const load = useCallback(() => {
    api.myRequests().then(setMine).catch(() => setMine([]));
    if (isApprover) api.requestInbox().then(setInbox).catch(() => setInbox([]));
  }, [isApprover]);

  useEffect(load, [load]);

  async function submit(values: {
    type: string;
    title: string;
    body?: string;
    leave_type?: string;
    leave_range?: [Dayjs, Dayjs];
  }) {
    setSaving(true);
    try {
      await api.submitRequest({
        type: values.type,
        title: values.title,
        body: values.body ?? "",
        leave_type: values.type === "leave" ? values.leave_type : null,
        from_date: values.type === "leave" ? values.leave_range?.[0].format("YYYY-MM-DD") : null,
        to_date: values.type === "leave" ? values.leave_range?.[1].format("YYYY-MM-DD") : null,
      });
      message.success(
        values.type === "leave"
          ? "Leave request submitted — sent to your lead for approval"
          : "Request submitted — sent to your lead for approval"
      );
      setOpen(false);
      form.resetFields();
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Submit failed");
    } finally {
      setSaving(false);
    }
  }

  async function act(id: string, action: "approve" | "reject" | "forward") {
    let comment = "";
    Modal.confirm({
      title: `${action[0].toUpperCase()}${action.slice(1)} this request?`,
      content: (
        <Input.TextArea
          placeholder="Comment (optional)"
          rows={2}
          onChange={(e) => {
            comment = e.target.value;
          }}
        />
      ),
      okText: action[0].toUpperCase() + action.slice(1),
      onOk: async () => {
        try {
          await api.actRequest(id, action, comment);
          message.success(`Request ${action === "forward" ? "forwarded" : action + "d"}`);
          load();
        } catch (e) {
          message.error(e instanceof ApiError ? e.message : "Action failed");
        }
      },
    });
  }

  const typeLabel = (t: string) => TYPES.find((x) => x.value === t)?.label ?? t;

  const typeCell = (t: string) => (
    <Flex gap={4} align="center">
      <Text style={{ fontSize: 13 }}>{typeLabel(t)}</Text>
      {t === "hr_grievance" && (
        <Tag color="purple" style={{ marginInlineStart: 4 }}>
          Confidential
        </Tag>
      )}
    </Flex>
  );

  const titleCell = (title: string, r: IoRequest) => (
    <div>
      <Text style={{ fontSize: 13 }}>{title}</Text>
      {r.type === "leave" && r.from_date && (
        <div>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {r.leave_type} · {r.from_date} → {r.to_date} · {r.days} day{r.days === 1 ? "" : "s"}
          </Text>
        </div>
      )}
    </div>
  );

  const myCols = [
    {
      title: "Title",
      dataIndex: "title",
      key: "title",
      ellipsis: true,
      render: (t: string, r: IoRequest) => titleCell(t, r),
    },
    {
      title: "Type",
      dataIndex: "type",
      key: "type",
      width: 190,
      render: (t: string) => typeCell(t),
    },
    {
      title: "Submitted",
      dataIndex: "created_at",
      key: "created",
      width: 170,
      render: (d: string) => (d ? new Date(d).toLocaleString() : "—"),
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      width: 110,
      render: (s: string) => <Tag color={STATUS_TAG[s]}>{s}</Tag>,
    },
  ];

  const inboxCols = [
    {
      title: "Title",
      dataIndex: "title",
      key: "title",
      ellipsis: true,
      render: (t: string, r: IoRequest) => titleCell(t, r),
    },
    { title: "From", dataIndex: "requester_name", key: "from", width: 150 },
    {
      title: "Type",
      dataIndex: "type",
      key: "type",
      width: 180,
      render: (t: string) => typeCell(t),
    },
    {
      title: "Actions",
      key: "actions",
      width: 240,
      render: (_: unknown, r: IoRequest) => (
        <Space size={4}>
          <Button size="small" type="primary" onClick={() => act(r.req_id, "approve")}>
            Approve
          </Button>
          <Button size="small" danger onClick={() => act(r.req_id, "reject")}>
            Reject
          </Button>
          <Button size="small" onClick={() => act(r.req_id, "forward")}>
            Forward
          </Button>
        </Space>
      ),
    },
  ];

  const expandable = {
    expandedRowRender: (r: IoRequest) => (
      <div style={{ paddingLeft: 8 }}>
        {r.body && <Text style={{ fontSize: 13 }}>{r.body}</Text>}
        <History req={r} />
      </div>
    ),
  };

  const myTab = (
    <Card size="small" bordered={false}>
      {mine.length === 0 ? (
        <Empty description="No requests yet — use “New Request” to report something to HR, request leave, or ask for an approval." />
      ) : (
        <Table
          size="small"
          rowKey="req_id"
          dataSource={mine}
          columns={myCols}
          expandable={expandable}
          pagination={{ pageSize: 10, showSizeChanger: false }}
        />
      )}
    </Card>
  );

  const inboxTab = (
    <Card size="small" bordered={false}>
      {inbox.length === 0 ? (
        <Empty description="Nothing waiting on you. 🎉" />
      ) : (
        <Table
          size="small"
          rowKey="req_id"
          dataSource={inbox}
          columns={inboxCols}
          expandable={expandable}
          pagination={{ pageSize: 10, showSizeChanger: false }}
        />
      )}
    </Card>
  );

  return (
    <div>
      <Flex justify="flex-end" style={{ marginBottom: 12 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          New Request
        </Button>
      </Flex>

      {isApprover ? (
        <Tabs
          defaultActiveKey="inbox"
          items={[
            { key: "inbox", label: `Approval Inbox (${inbox.length})`, children: inboxTab },
            { key: "mine", label: "My Requests", children: myTab },
          ]}
        />
      ) : (
        myTab
      )}

      <Modal
        title="New Request"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={saving}
        okText="Submit"
      >
        <Form form={form} layout="vertical" onFinish={submit}>
          <Form.Item
            name="type"
            label="Type"
            initialValue="general"
            rules={[{ required: true }]}
          >
            <Select options={TYPES} />
          </Form.Item>
          <Form.Item name="title" label="Title" rules={[{ required: true, message: "Title required" }]}>
            <Input placeholder="Short summary" maxLength={300} />
          </Form.Item>
          {selectedType === "leave" && (
            <Flex gap={12}>
              <Form.Item
                name="leave_type"
                label="Leave type"
                rules={[{ required: true, message: "Pick a leave type" }]}
                style={{ flex: 1 }}
              >
                <Select options={LEAVE_TYPES.map((v) => ({ value: v, label: v }))} />
              </Form.Item>
              <Form.Item
                name="leave_range"
                label="Dates"
                rules={[{ required: true, message: "Pick your leave dates" }]}
                style={{ flex: 2 }}
              >
                <RangePicker style={{ width: "100%" }} />
              </Form.Item>
            </Flex>
          )}
          <Form.Item name="body" label="Details">
            <Input.TextArea rows={4} placeholder="Describe your request — it goes to your direct lead first." />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
