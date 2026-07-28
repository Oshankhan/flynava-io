import { useState } from "react";
import {
  App,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Modal,
  Progress,
  Select,
  Table,
  Tag,
  Typography,
} from "antd";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { api, ApiError, type MilestoneTask } from "../../../lib/api";

const { Text } = Typography;

const TASK_STATUS = [
  { value: "todo", label: "To Do" },
  { value: "in_progress", label: "In Progress" },
  { value: "done", label: "Done" },
];

/** Weightage is what makes progress mean anything, so it's surfaced as its own
 * column with the share it represents — an unweighted task list would let a
 * one-hour chore count the same as a two-week build. */
export default function TasksTab({
  milestoneId,
  tasks,
  canManage,
  onChanged,
}: {
  milestoneId: string;
  tasks: MilestoneTask[];
  canManage: boolean;
  onChanged: () => void | Promise<void>;
}) {
  const { message } = App.useApp();
  const [form] = Form.useForm();
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [busy, setBusy] = useState<Record<string, boolean>>({});

  const weightTotal = (tasks ?? []).reduce((sum, t) => sum + (t?.weightage ?? 0), 0);

  const add = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      await api.addMilestoneTask(milestoneId, values);
      message.success("Task added");
      setAdding(false);
      form.resetFields();
      await onChanged();
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Could not add task");
    } finally {
      setSaving(false);
    }
  };

  const patch = async (task: MilestoneTask, body: Partial<MilestoneTask>) => {
    setBusy((b) => ({ ...b, [task.task_id]: true }));
    try {
      await api.updateMilestoneTask(milestoneId, task.task_id, body);
      await onChanged();
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Update failed");
    } finally {
      setBusy((b) => ({ ...b, [task.task_id]: false }));
    }
  };

  const remove = (task: MilestoneTask) => {
    Modal.confirm({
      title: `Delete "${task.title}"?`,
      content: "Its daily entries go with it and the milestone progress is recalculated.",
      okText: "Delete",
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await api.deleteMilestoneTask(milestoneId, task.task_id);
          message.success("Task deleted");
          await onChanged();
        } catch (err) {
          message.error(err instanceof ApiError ? err.message : "Delete failed");
          throw err;
        }
      },
    });
  };

  return (
    <Card
      size="small"
      bordered={false}
      title={
        <span>
          Tasks <Text type="secondary" className="text-xs">({tasks?.length ?? 0} · {weightTotal} weight)</Text>
        </span>
      }
      extra={
        canManage && (
          <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setAdding(true)}>
            Add Task
          </Button>
        )
      }
    >
      <Table<MilestoneTask>
        rowKey="task_id"
        size="small"
        dataSource={tasks ?? []}
        pagination={false}
        scroll={{ x: "max-content" }}
        locale={{ emptyText: "No tasks yet — add one to start tracking weighted progress." }}
        columns={[
          { title: "Task", dataIndex: "title", render: (t: string) => <span className="min-w-[180px] inline-block">{t}</span> },
          { title: "Assignee", dataIndex: "assignee_name", responsive: ["md"] },
          {
            title: "Weightage",
            dataIndex: "weightage",
            width: 130,
            render: (w: number) => (
              <span className="whitespace-nowrap">
                <Tag>{w}</Tag>
                <Text type="secondary" className="text-[11px]">
                  {weightTotal ? Math.round((w / weightTotal) * 100) : 0}%
                </Text>
              </span>
            ),
          },
          {
            title: "Completion",
            dataIndex: "completion_pct",
            width: 150,
            render: (pct: number) => (
              <Progress percent={Math.round(pct ?? 0)} size="small" className="!mb-0" />
            ),
          },
          { title: "Due", dataIndex: "due_date", width: 120, responsive: ["lg"] },
          {
            title: "Status",
            dataIndex: "status",
            width: 150,
            render: (status: string, row) =>
              canManage ? (
                <Select
                  size="small"
                  className="w-full"
                  value={status}
                  loading={busy[row.task_id]}
                  disabled={busy[row.task_id]}
                  options={TASK_STATUS}
                  onChange={(v) => patch(row, { status: v })}
                />
              ) : (
                <Tag color={status === "done" ? "success" : "default"}>{status}</Tag>
              ),
          },
          ...(canManage
            ? [
                {
                  title: "",
                  key: "actions",
                  width: 50,
                  render: (_: unknown, row: MilestoneTask) => (
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      loading={busy[row.task_id]}
                      onClick={() => remove(row)}
                    />
                  ),
                },
              ]
            : []),
        ]}
      />

      <Modal
        open={adding}
        title="Add task"
        okText="Add task"
        onOk={add}
        confirmLoading={saving}
        onCancel={() => setAdding(false)}
        destroyOnClose
      >
        <Form form={form} layout="vertical" requiredMark={false} disabled={saving}>
          <Form.Item name="title" label="Title" rules={[{ required: true, message: "Required" }]}>
            <Input placeholder="Integration testing" />
          </Form.Item>
          <Form.Item
            name="weightage"
            label="Weightage"
            initialValue={1}
            help="Relative size against the milestone's other tasks."
          >
            <InputNumber min={0} max={1000} className="w-full" />
          </Form.Item>
          <Form.Item name="status" label="Status" initialValue="todo">
            <Select options={TASK_STATUS} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
