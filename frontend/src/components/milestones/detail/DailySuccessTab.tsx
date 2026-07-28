import { useState } from "react";
import {
  Alert,
  App,
  Button,
  Card,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Table,
  Tag,
  Typography,
} from "antd";
import { CheckOutlined, CloseOutlined, PlusOutlined } from "@ant-design/icons";
import type { Dayjs } from "dayjs";
import { api, ApiError, type MilestoneDailyEntry, type MilestoneTask } from "../../../lib/api";

const { Text } = Typography;

const STATUS_COLOR: Record<string, string> = {
  approved: "success",
  pending: "gold",
  rejected: "error",
};

/** The Daily Success Tracker log. Only approved entries move the milestone's
 * progress, which is why the pending ones are called out at the top rather
 * than buried in the table. */
export default function DailySuccessTab({
  milestoneId,
  entries,
  tasks,
  canApprove,
  onChanged,
}: {
  milestoneId: string;
  entries: MilestoneDailyEntry[];
  tasks: MilestoneTask[];
  canApprove: boolean;
  onChanged: () => void | Promise<void>;
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm<{
    task_id?: string;
    date?: Dayjs;
    hours?: number;
    progress_delta?: number;
    note?: string;
  }>();
  const [logging, setLogging] = useState(false);
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState<Record<string, boolean>>({});

  const pending = (entries ?? []).filter((e) => e?.status === "pending");

  const submit = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      await api.addMilestoneDailyEntry(milestoneId, {
        task_id: values.task_id,
        date: values.date?.format("YYYY-MM-DD"),
        hours: values.hours,
        progress_delta: values.progress_delta,
        note: values.note,
      });
      message.success("Entry submitted for approval");
      setLogging(false);
      form.resetFields();
      await onChanged();
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Could not log entry");
    } finally {
      setSaving(false);
    }
  };

  const decide = async (entry: MilestoneDailyEntry, decision: "approve" | "reject") => {
    setBusy((b) => ({ ...b, [entry.entry_id]: true }));
    try {
      await api.decideMilestoneDailyEntry(milestoneId, entry.entry_id, decision);
      message.success(`Entry ${decision === "approve" ? "approved" : "rejected"}`);
      await onChanged();
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Action failed");
    } finally {
      setBusy((b) => ({ ...b, [entry.entry_id]: false }));
    }
  };

  return (
    <Card
      size="small"
      bordered={false}
      title="Daily Success Entries"
      extra={
        <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setLogging(true)}>
          Log Progress
        </Button>
      }
    >
      {pending.length > 0 && (
        <Alert
          type="warning"
          showIcon
          className="mb-3"
          message={`${pending.length} entry(s) awaiting approval`}
          description="Pending entries contribute nothing to progress until approved."
        />
      )}
      <Table<MilestoneDailyEntry>
        rowKey="entry_id"
        size="small"
        dataSource={entries ?? []}
        pagination={{ pageSize: 10, hideOnSinglePage: true }}
        scroll={{ x: "max-content" }}
        locale={{ emptyText: "No daily entries logged yet." }}
        columns={[
          { title: "Date", dataIndex: "date", width: 110 },
          { title: "By", dataIndex: "user_name", width: 150 },
          {
            title: "Task",
            dataIndex: "task_title",
            render: (title: string | null) => title ?? <Text type="secondary">Milestone-level</Text>,
          },
          {
            title: "Progress",
            dataIndex: "progress_delta",
            width: 100,
            render: (v: number) => <Tag color="blue">+{v}%</Tag>,
          },
          { title: "Hours", dataIndex: "hours", width: 80, responsive: ["md"] },
          { title: "Note", dataIndex: "note", responsive: ["xl"] },
          {
            title: "Status",
            dataIndex: "status",
            width: 110,
            render: (s: string) => <Tag color={STATUS_COLOR[s] ?? "default"}>{s}</Tag>,
          },
          {
            title: "Approval",
            key: "approval",
            width: 150,
            render: (_: unknown, row) => {
              if (row.status !== "pending")
                return (
                  <Text type="secondary" className="text-[11px]">
                    {row.approver_name ? `by ${row.approver_name}` : "—"}
                  </Text>
                );
              if (!canApprove) return <Text type="secondary" className="text-[11px]">Awaiting manager</Text>;
              return (
                <div className="flex gap-1">
                  <Button
                    size="small"
                    type="primary"
                    icon={<CheckOutlined />}
                    loading={busy[row.entry_id]}
                    onClick={() => decide(row, "approve")}
                  >
                    Approve
                  </Button>
                  <Button
                    size="small"
                    danger
                    icon={<CloseOutlined />}
                    loading={busy[row.entry_id]}
                    onClick={() => decide(row, "reject")}
                  />
                </div>
              );
            },
          },
        ]}
      />

      <Modal
        open={logging}
        title="Log daily progress"
        okText="Submit for approval"
        onOk={submit}
        confirmLoading={saving}
        onCancel={() => setLogging(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical" requiredMark={false} disabled={saving}>
          <Form.Item name="task_id" label="Task" help="Leave blank to log against the milestone.">
            <Select
              allowClear
              options={(tasks ?? []).map((t) => ({ value: t.task_id, label: t.title }))}
            />
          </Form.Item>
          <Form.Item name="date" label="Date">
            <DatePicker className="w-full" />
          </Form.Item>
          <Form.Item
            name="progress_delta"
            label="Progress added (%)"
            rules={[{ required: true, message: "Required" }]}
          >
            <InputNumber min={0} max={100} className="w-full" />
          </Form.Item>
          <Form.Item name="hours" label="Hours">
            <InputNumber min={0} max={24} step={0.5} className="w-full" />
          </Form.Item>
          <Form.Item name="note" label="Note">
            <Input.TextArea rows={3} placeholder="What moved forward today?" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
