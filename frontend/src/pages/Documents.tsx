import { useEffect, useState } from "react";
import {
  Button,
  Card,
  Col,
  Form,
  Input,
  message,
  Row,
  Select,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
  type UploadFile,
} from "antd";
import { InboxOutlined } from "@ant-design/icons";
import { api, ApiError, type IoDocument } from "../lib/api";
import { useAuth } from "../lib/auth";

const APPROVERS = ["super_admin", "leadership", "hr"];
const KINDS = [
  { value: "document", label: "Document" },
  { value: "mom", label: "MOM (Minutes of Meeting)" },
  { value: "policy", label: "Policy" },
];
const STATUS_COLOR: Record<string, string> = {
  pending: "warning",
  approved: "success",
  rejected: "error",
};

export default function Documents() {
  const { user } = useAuth();
  const [docs, setDocs] = useState<IoDocument[]>([]);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [form] = Form.useForm();
  const canApprove = user && APPROVERS.includes(user.role);

  const load = () => api.documents().then(setDocs).catch(() => setDocs([]));
  useEffect(() => {
    load();
  }, []);

  async function submit(v: { title: string; kind: string }) {
    const file = fileList[0]?.originFileObj;
    if (!file) return message.error("Choose a file");
    try {
      await api.uploadDocument(v.title, v.kind, file as File);
      message.success("Uploaded — routed for approval");
      form.resetFields();
      setFileList([]);
      load();
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Upload failed");
    }
  }

  async function decide(id: string, decision: "approve" | "reject") {
    await api.decideDocument(id, decision);
    message.success(`Document ${decision}d`);
    load();
  }

  return (
    <Space direction="vertical" size={20} style={{ width: "100%" }}>
      <Card title="Upload to FlyNava Archive — routed for approval" size="small">
        <Form form={form} layout="vertical" onFinish={submit} initialValues={{ kind: "document" }}>
          <Row gutter={12}>
            <Col xs={24} sm={12}>
              <Form.Item name="title" label="Title" rules={[{ required: true }]}>
                <Input placeholder="Document title" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12}>
              <Form.Item name="kind" label="Type">
                <Select options={KINDS} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label="File" required>
            <Upload.Dragger
              beforeUpload={() => false}
              maxCount={1}
              fileList={fileList}
              onChange={({ fileList: fl }) => setFileList(fl.slice(-1))}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">Click or drag a file to upload</p>
            </Upload.Dragger>
          </Form.Item>
          <Button type="primary" htmlType="submit">
            Upload for approval
          </Button>
        </Form>
      </Card>

      <Card size="small" title="Documents & Approvals">
        <Table<IoDocument>
          dataSource={docs}
          rowKey="doc_id"
          size="small"
          pagination={{ pageSize: 8 }}
          columns={[
            { title: "Title", dataIndex: "title", key: "title" },
            {
              title: "Type",
              dataIndex: "kind",
              key: "kind",
              render: (k: string) => <Tag>{k.toUpperCase()}</Tag>,
            },
            { title: "By", dataIndex: "uploaded_by", key: "by" },
            {
              title: "Status",
              dataIndex: "status",
              key: "status",
              render: (s: string) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
            },
            {
              title: "Date",
              dataIndex: "created_at",
              key: "date",
              render: (d: string) => new Date(d).toLocaleDateString(),
            },
            ...(canApprove
              ? [
                  {
                    title: "Actions",
                    key: "actions",
                    render: (_: unknown, d: IoDocument) =>
                      d.status === "pending" ? (
                        <Space>
                          <Button
                            size="small"
                            type="primary"
                            onClick={() => decide(d.doc_id, "approve")}
                          >
                            Approve
                          </Button>
                          <Button size="small" danger onClick={() => decide(d.doc_id, "reject")}>
                            Reject
                          </Button>
                        </Space>
                      ) : (
                        <Typography.Text type="secondary">—</Typography.Text>
                      ),
                  },
                ]
              : []),
          ]}
        />
      </Card>
    </Space>
  );
}
