import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  Descriptions,
  Drawer,
  Flex,
  Input,
  message,
  Modal,
  Select,
  Space,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  Upload,
  type UploadFile,
} from "antd";
import { DownloadOutlined, InboxOutlined, SendOutlined } from "@ant-design/icons";
import {
  api,
  ApiError,
  type AttendanceRow,
  type Employee,
  type EmployeeDetail,
} from "../lib/api";

const { Text } = Typography;
const inr = (n: number) => `₹${n.toLocaleString("en-IN")}`;
const STATUS_COLOR: Record<string, string> = {
  Present: "success",
  Late: "warning",
  Absent: "error",
  "Half Day": "processing",
};

function Directory() {
  const [rows, setRows] = useState<Employee[]>([]);
  const [detail, setDetail] = useState<EmployeeDetail | null>(null);

  useEffect(() => {
    api.hrEmployees().then(setRows).catch(() => setRows([]));
  }, []);

  return (
    <>
      <Table<Employee>
        dataSource={rows}
        rowKey="emp_id"
        size="small"
        pagination={{ pageSize: 12 }}
        onRow={(r) => ({
          style: { cursor: "pointer" },
          onClick: () => api.hrEmployee(r.emp_id).then(setDetail),
        })}
        columns={[
          { title: "ID", dataIndex: "emp_id", key: "emp_id", width: 90 },
          { title: "Name", dataIndex: "name", key: "name" },
          { title: "Designation", dataIndex: "designation", key: "designation" },
          {
            title: "Dept",
            dataIndex: "department",
            key: "department",
            render: (d: string) => <Tag>{d.toUpperCase()}</Tag>,
          },
          {
            title: "Net Pay",
            key: "net",
            render: (_, r) => inr(r.salary.net),
          },
          {
            title: "Leave left",
            key: "leave",
            render: (_, r) =>
              Object.values(r.leave_balance).reduce((a, b) => a + b, 0) + " days",
          },
        ]}
      />
      <Drawer
        open={!!detail}
        onClose={() => setDetail(null)}
        width={560}
        title={detail?.name}
      >
        {detail && (
          <Flex vertical gap={16}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="Designation">{detail.designation}</Descriptions.Item>
              <Descriptions.Item label="Email">{detail.email}</Descriptions.Item>
              <Descriptions.Item label="Joined">{detail.doj}</Descriptions.Item>
              <Descriptions.Item label="Gross / Net">
                {inr(detail.salary.gross)} / <Text strong>{inr(detail.salary.net)}</Text>
              </Descriptions.Item>
            </Descriptions>
            <Flex gap={12}>
              {Object.entries(detail.leave_balance).map(([t, d]) => (
                <Statistic key={t} title={t} value={d} suffix="d" />
              ))}
            </Flex>
            <Card size="small" title="Recent Payslips">
              <Table
                dataSource={detail.payslips}
                rowKey="month"
                size="small"
                pagination={false}
                columns={[
                  { title: "Month", dataIndex: "month", key: "month" },
                  { title: "Gross", key: "g", render: (_, p) => inr(p.gross) },
                  { title: "Net", key: "n", render: (_, p) => inr(p.net) },
                ]}
              />
            </Card>
          </Flex>
        )}
      </Drawer>
    </>
  );
}

function Attendance() {
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [preview, setPreview] = useState<AttendanceRow[]>([]);
  const [summary, setSummary] = useState<Record<string, number>>({});
  const [uploadId, setUploadId] = useState<string>();
  const [recipients, setRecipients] = useState<string[]>([]);
  const [title, setTitle] = useState("Daily Attendance Report");
  const [emailHtml, setEmailHtml] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function downloadSample() {
    const csv = await api.hrSampleCsv();
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "biometric_sample.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function onUpload(file: File) {
    setBusy(true);
    try {
      const res = await api.hrUploadAttendance(file);
      setPreview(res.preview);
      setSummary(res.summary.by_status);
      setUploadId(res.upload_id);
      message.success(`Parsed ${res.rows} attendance records`);
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
    return false; // prevent antd auto-upload
  }

  async function send() {
    if (!uploadId) return message.warning("Upload a report first");
    if (!recipients.length) return message.warning("Add at least one recipient");
    setBusy(true);
    try {
      const res = await api.hrSendAttendance({ upload_id: uploadId, recipients, title });
      setEmailHtml(res.preview_html);
      if (res.status === "sent") message.success(res.detail);
      else message.info(res.detail);
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Send failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Flex vertical gap={16}>
      <Card size="small" title="1 · Upload biometric attendance export (CSV)">
        <Flex vertical gap={12}>
          <Button icon={<DownloadOutlined />} onClick={downloadSample}>
            Download sample biometric CSV
          </Button>
          <Upload.Dragger
            beforeUpload={(f) => onUpload(f as unknown as File)}
            maxCount={1}
            fileList={fileList}
            onChange={({ fileList: fl }) => setFileList(fl.slice(-1))}
            accept=".csv"
          >
            <p className="ant-upload-drag-icon"><InboxOutlined /></p>
            <p className="ant-upload-text">Click or drag the biometric CSV here</p>
            <p className="ant-upload-hint">
              Columns: Emp Code, Employee Name, Date, In Time, Out Time, Status
            </p>
          </Upload.Dragger>
        </Flex>
      </Card>

      {preview.length > 0 && (
        <Card size="small" title={`2 · Parsed ${preview.length} record(s)`}>
          <Space wrap style={{ marginBottom: 12 }}>
            {Object.entries(summary).map(([s, n]) => (
              <Tag key={s} color={STATUS_COLOR[s] ?? "default"}>
                {s}: {n}
              </Tag>
            ))}
          </Space>
          <Table<AttendanceRow>
            dataSource={preview}
            rowKey={(r) => `${r.emp_code}-${r.name}-${r.date}`}
            size="small"
            pagination={{ pageSize: 8 }}
            columns={[
              { title: "Employee", dataIndex: "name", key: "name" },
              { title: "Date", dataIndex: "date", key: "date" },
              { title: "In", dataIndex: "in_time", key: "in" },
              { title: "Out", dataIndex: "out_time", key: "out" },
              { title: "Hours", dataIndex: "hours", key: "hours", render: (h) => h ?? "—" },
              {
                title: "Status",
                dataIndex: "status",
                key: "status",
                render: (s: string) => <Tag color={STATUS_COLOR[s] ?? "default"}>{s}</Tag>,
              },
            ]}
          />
        </Card>
      )}

      {uploadId && (
        <Card size="small" title="3 · Email the report">
          <Flex vertical gap={12}>
            <Input
              addonBefore="Subject"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <Select
              mode="tags"
              style={{ width: "100%" }}
              placeholder="recipient emails — type and press Enter"
              value={recipients}
              onChange={setRecipients}
              tokenSeparators={[",", " "]}
            />
            <Flex gap={12}>
              <Button type="primary" icon={<SendOutlined />} loading={busy} onClick={send}>
                Send attendance email
              </Button>
              {emailHtml && <Button onClick={() => setEmailHtml(emailHtml)}>Preview</Button>}
            </Flex>
          </Flex>
        </Card>
      )}

      <Modal
        open={!!emailHtml}
        onCancel={() => setEmailHtml(null)}
        title="Attendance email preview"
        width={780}
        footer={<Button onClick={() => setEmailHtml(null)}>Close</Button>}
      >
        {emailHtml && (
          <div
            style={{ border: "1px solid #eee", padding: 16, borderRadius: 8 }}
            dangerouslySetInnerHTML={{ __html: emailHtml }}
          />
        )}
      </Modal>
    </Flex>
  );
}

export default function People() {
  return (
    <>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="People & Attendance ERP — employee directory, payslips, and biometric attendance upload → email."
      />
      <Tabs
        items={[
          { key: "dir", label: "Employee Directory", children: <Directory /> },
          { key: "att", label: "Attendance (Biometric)", children: <Attendance /> },
        ]}
      />
    </>
  );
}
