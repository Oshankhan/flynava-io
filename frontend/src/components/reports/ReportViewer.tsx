import { useEffect, useState } from "react";
import {
  Alert, Button, Card, Col, Descriptions, Drawer, Dropdown, Empty, Flex, Form, Input,
  List, Modal, Row, Select, Spin, Table, Tag, Typography, message,
} from "antd";
import {
  AlignLeftOutlined, CalendarOutlined, DownloadOutlined, PlayCircleOutlined,
  RobotOutlined, ShareAltOutlined, SendOutlined,
} from "@ant-design/icons";
import {
  CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  API_BASE_URL, TOKEN_KEY, api, ApiError,
  type ReportDef, type ReportRun, type ReportSection, type UserLite,
} from "../../lib/api";
import { useAsyncAction } from "../../lib/useAsyncAction";
import ScheduleModal from "./ScheduleModal";

const { Text, Title, Paragraph } = Typography;
const CHART_COLORS = ["#157f52", "#2563eb", "#dc2626", "#d97706", "#7c3aed"];

function ChartSection({ section }: { section: ReportSection }) {
  const series = section.series ?? [];
  const merged: Record<string, Record<string, number | string>> = {};
  series.forEach((s) => {
    s.points.forEach((p) => {
      merged[p.t] = merged[p.t] ?? { t: p.t };
      merged[p.t][s.name] = p.v;
    });
  });
  const data = Object.values(merged).sort((a, b) => String(a.t).localeCompare(String(b.t)));
  if (data.length === 0) return <Empty description="No data for this section yet" />;
  return (
    <div className="w-full h-[220px]">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ left: 8, right: 8, top: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#dfeee6" />
          <XAxis dataKey="t" tick={{ fontSize: 10 }} minTickGap={24} />
          <YAxis tick={{ fontSize: 10 }} width={56} />
          <Tooltip />
          {series.length > 1 && <Legend />}
          {series.map((s, i) => (
            <Line key={s.name} type="monotone" dataKey={s.name}
              stroke={CHART_COLORS[i % CHART_COLORS.length]} strokeWidth={2} dot={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function StatsSection({ section }: { section: ReportSection }) {
  return (
    <Row gutter={[12, 12]}>
      {(section.stats ?? []).map((s, i) => (
        <Col key={i} xs={12} sm={8} md={6}>
          <Card size="small" bordered={false} className="bg-[#f7f8fa] dark:bg-white/[0.04]">
            <div className="text-lg font-bold">{String(s.value ?? "—")}{s.unit ?? ""}</div>
            <Text type="secondary" className="text-xs">{s.label}</Text>
            {s.delta != null && (
              <div>
                <Text className={`text-[11px] ${s.delta >= 0 ? "text-io-600" : "text-red-500"}`}>
                  {s.delta >= 0 ? "↑" : "↓"} {Math.abs(s.delta)}%
                </Text>
              </div>
            )}
          </Card>
        </Col>
      ))}
    </Row>
  );
}

function SectionRenderer({ section }: { section: ReportSection }) {
  return (
    <Card size="small" bordered={false} title={section.title} className="mb-3">
      {section.kind === "table" && (
        (section.rows?.length ?? 0) === 0 ? <Empty description="No rows" /> : (
          <Table
            size="small" rowKey={(_, i) => String(i)} pagination={{ pageSize: 10 }} scroll={{ x: true }}
            dataSource={section.rows}
            columns={(section.columns ?? Object.keys(section.rows?.[0] ?? {}).map((k) => ({ key: k, label: k })))
              .map((c) => ({ title: c.label, dataIndex: c.key, key: c.key }))}
          />
        )
      )}
      {section.kind === "chart" && <ChartSection section={section} />}
      {section.kind === "stats" && <StatsSection section={section} />}
      {section.kind === "text" && <Paragraph className="whitespace-pre-line mb-0">{section.text}</Paragraph>}
    </Card>
  );
}

async function fetchRunHtml(runId: string): Promise<string> {
  const token = localStorage.getItem(TOKEN_KEY);
  const res = await fetch(`${API_BASE_URL}/api/v1/reports/runs/${runId}/export?fmt=html`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new ApiError(res.status, "failed to load printable view");
  return res.text();
}

export default function ReportViewer({
  open, onClose, reportDef, level, onChanged,
}: {
  open: boolean;
  onClose: () => void;
  reportDef: ReportDef | null;
  level: number;
  onChanged: () => void;
}) {
  const [run, setRun] = useState<ReportRun | null>(null);
  const [history, setHistory] = useState<Omit<ReportRun, "sections">[]>([]);
  const [loading, setLoading] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [sendOpen, setSendOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [people, setPeople] = useState<UserLite[]>([]);
  const [sendForm] = Form.useForm();
  const [shareForm] = Form.useForm();

  useEffect(() => {
    if (!open || !reportDef) return;
    void loadLatest(reportDef.report_id);
  }, [open, reportDef?.report_id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (sendOpen || shareOpen) api.orgUsers().then(setPeople).catch(() => setPeople([]));
  }, [sendOpen, shareOpen]);

  async function loadLatest(reportId: string) {
    setLoading(true);
    try {
      const hist = await api.reportDefRuns(reportId, 10);
      if (hist.length > 0) {
        setHistory(hist);
        setRun(await api.reportRun(hist[0].run_id));
      } else {
        const fresh = await api.runReportDef(reportId);
        setRun(fresh);
        setHistory([fresh]);
      }
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Failed to load report");
    } finally {
      setLoading(false);
    }
  }

  const [runAgain, running] = useAsyncAction(async (withAi: boolean) => {
    if (!reportDef) return;
    try {
      const fresh = await api.runReportDef(reportDef.report_id, withAi);
      setRun(fresh);
      setHistory((h) => [fresh, ...h]);
      onChanged();
      message.success("Report generated");
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Run failed");
    }
  });

  async function viewVersion(runId: string) {
    setLoading(true);
    try {
      setRun(await api.reportRun(runId));
    } finally {
      setLoading(false);
    }
  }

  const [doSend, sending] = useAsyncAction(async (values: { recipients: string[]; message?: string }) => {
    if (!reportDef) return;
    try {
      const res = await api.sendReportDef(reportDef.report_id, {
        recipients: values.recipients, message: values.message, run_id: run?.run_id,
      });
      message.success(res.status === "sent" ? "Email sent" : "SMTP not configured — showing preview only");
      setSendOpen(false);
      onChanged();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Send failed");
    }
  });

  const [doShare, sharing] = useAsyncAction(async (values: { user_ids: string[] }) => {
    if (!reportDef) return;
    try {
      await api.shareReportDef(reportDef.report_id, values.user_ids);
      message.success("Report shared");
      setShareOpen(false);
      onChanged();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Share failed");
    }
  });

  async function exportAs(fmt: "csv" | "xls") {
    if (!run || !reportDef) return;
    try {
      await api.exportReportRun(run.run_id, fmt, `${reportDef.name}.${fmt}`);
      onChanged();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Export failed");
    }
  }

  async function exportPrint() {
    if (!run) return;
    try {
      const html = await fetchRunHtml(run.run_id);
      const win = window.open("", "_blank");
      if (!win) return;
      win.document.write(html);
      win.document.close();
      win.focus();
      win.print();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Print view failed");
    }
  }

  if (!reportDef) return null;

  return (
    <Drawer
      open={open}
      onClose={onClose}
      width="min(880px, 100vw)"
      title={
        <Flex justify="space-between" align="center" wrap gap={8}>
          <div>
            <Title level={4} className="m-0">{reportDef.name}</Title>
            <Text type="secondary" className="text-xs">{reportDef.description}</Text>
          </div>
          <Flex gap={6} wrap>
            <Button icon={<PlayCircleOutlined />} loading={running} onClick={() => runAgain(false)}>
              Run Again
            </Button>
            <Button icon={<RobotOutlined />} loading={running} onClick={() => runAgain(true)}>
              AI Summary
            </Button>
            {level >= 2 && (
              <Button icon={<SendOutlined />} onClick={() => { sendForm.setFieldsValue({ recipients: reportDef.recipients }); setSendOpen(true); }}>
                Send
              </Button>
            )}
            {level >= 2 && (
              <Button icon={<ShareAltOutlined />} onClick={() => setShareOpen(true)}>Share</Button>
            )}
            {level >= 2 && (
              <Button icon={<CalendarOutlined />} onClick={() => setScheduleOpen(true)}>Schedule</Button>
            )}
            <Dropdown menu={{
              items: [
                { key: "csv", label: "Export CSV" },
                { key: "xls", label: "Export Excel" },
                { key: "pdf", label: "Export PDF (print)" },
                { key: "ppt", label: "Export PowerPoint", disabled: true },
              ],
              onClick: ({ key }) => {
                if (key === "csv" || key === "xls") exportAs(key);
                else if (key === "pdf") exportPrint();
              },
            }}>
              <Button icon={<DownloadOutlined />}>Export</Button>
            </Dropdown>
          </Flex>
        </Flex>
      }
    >
      {loading || !run ? (
        <Flex justify="center" className="pt-16"><Spin /></Flex>
      ) : (
        <Row gutter={16}>
          <Col xs={24} lg={17}>
            {run.ai_summary && (
              <Alert type="info" showIcon icon={<RobotOutlined />} className="mb-4"
                message="AI Executive Summary" description={run.ai_summary} />
            )}
            {run.sections.map((s) => <SectionRenderer key={s.key} section={s} />)}
          </Col>
          <Col xs={24} lg={7}>
            <Card size="small" title={<Flex align="center" gap={6}><AlignLeftOutlined />Run Details</Flex>} className="mb-4">
              <Descriptions column={1} size="small">
                <Descriptions.Item label="Version">v{run.version}</Descriptions.Item>
                <Descriptions.Item label="Generated">{new Date(run.at).toLocaleString()}</Descriptions.Item>
                <Descriptions.Item label="Triggered by">{run.triggered_by}</Descriptions.Item>
                <Descriptions.Item label="Delivery">
                  <Tag color={run.delivery.status === "sent" ? "success" : run.delivery.status === "preview" ? "warning" : "default"}>
                    {run.delivery.status}
                  </Tag>
                </Descriptions.Item>
              </Descriptions>
            </Card>
            <Card size="small" title="Run History">
              <List
                size="small"
                dataSource={history}
                renderItem={(h) => (
                  <List.Item
                    className="cursor-pointer"
                    onClick={() => viewVersion(h.run_id)}
                    actions={[<Tag key="s" color={h.status === "ok" ? "success" : "error"}>{h.status}</Tag>]}
                  >
                    <List.Item.Meta
                      title={<Text className={h.run_id === run.run_id ? "text-io-600 font-semibold" : ""}>v{h.version}</Text>}
                      description={new Date(h.at).toLocaleString()}
                    />
                  </List.Item>
                )}
              />
            </Card>
          </Col>
        </Row>
      )}

      <Modal
        title="Send Report" open={sendOpen} onCancel={() => setSendOpen(false)}
        onOk={() => sendForm.submit()} confirmLoading={sending} okText="Send"
      >
        <Form form={sendForm} layout="vertical" onFinish={doSend}>
          <Form.Item name="recipients" label="Recipients" rules={[{ required: true, message: "Add at least one recipient" }]}>
            <Select mode="tags" placeholder="e.g. name@flynava.ai" tokenSeparators={[",", " "]} />
          </Form.Item>
          <Form.Item name="message" label="Message (optional)">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="Share Report" open={shareOpen} onCancel={() => setShareOpen(false)}
        onOk={() => shareForm.submit()} confirmLoading={sharing} okText="Share"
      >
        <Form form={shareForm} layout="vertical" onFinish={doShare}>
          <Form.Item name="user_ids" label="Share with" rules={[{ required: true, message: "Select at least one person" }]}>
            <Select mode="multiple" showSearch optionFilterProp="label"
              options={people.map((p) => ({ value: p.user_id, label: p.designation ? `${p.name} — ${p.designation}` : p.name }))} />
          </Form.Item>
        </Form>
      </Modal>

      <ScheduleModal
        open={scheduleOpen} onClose={() => setScheduleOpen(false)} reportDef={reportDef}
        onSaved={onChanged}
      />
    </Drawer>
  );
}
