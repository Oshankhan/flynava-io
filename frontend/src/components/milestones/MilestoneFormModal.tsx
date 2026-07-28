import { useEffect, useState } from "react";
import { App, DatePicker, Form, Input, Modal, Select } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { api, ApiError, type MilestoneFilterOptions, type MilestoneRow } from "../../lib/api";
import { STATUS_OPTIONS } from "./MilestoneBadges";

interface FormValues {
  name: string;
  description?: string;
  project_id?: string;
  department?: string;
  team_id?: string;
  owner_id?: string;
  manager_id?: string;
  category?: string;
  priority?: string;
  status?: MilestoneRow["status"];
  range?: [Dayjs, Dayjs];
  criteria?: string;
}

/** Create/edit dialog. `milestone` present means edit — the same fields either
 * way, so the two paths can't drift apart. */
export default function MilestoneFormModal({
  open,
  milestone,
  onClose,
  onSaved,
}: {
  open: boolean;
  milestone?: MilestoneRow | null;
  onClose: () => void;
  onSaved: (row: MilestoneRow) => void;
}) {
  const [form] = Form.useForm<FormValues>();
  const { message } = App.useApp();
  const [options, setOptions] = useState<MilestoneFilterOptions | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    api
      .milestoneFilterOptions()
      .then(setOptions)
      .catch(() => setOptions(null));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    form.resetFields();
    if (milestone) {
      form.setFieldsValue({
        name: milestone.name,
        description: milestone.description,
        project_id: milestone.project_id ?? undefined,
        department: milestone.department ?? undefined,
        team_id: milestone.team_id ?? undefined,
        owner_id: milestone.owner_id ?? undefined,
        manager_id: milestone.manager_id ?? undefined,
        category: milestone.category,
        priority: milestone.priority,
        status: milestone.status,
        criteria: (milestone.completion_criteria ?? []).map((c) => c.label).join("\n"),
        range:
          milestone.start_date && milestone.due_date
            ? [dayjs(milestone.start_date), dayjs(milestone.due_date)]
            : undefined,
      });
    }
  }, [open, milestone, form]);

  const submit = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      const criteria = (values.criteria ?? "")
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((label) => ({
          label,
          // Preserve ticks already recorded against a criterion of the same name.
          done:
            milestone?.completion_criteria?.find((c) => c.label === label)?.done ?? false,
        }));
      const body = {
        name: values.name,
        description: values.description ?? "",
        project_id: values.project_id,
        department: values.department,
        team_id: values.team_id,
        owner_id: values.owner_id,
        manager_id: values.manager_id,
        category: values.category ?? "General",
        priority: values.priority ?? "Medium",
        status: values.status,
        start_date: values.range?.[0]?.format("YYYY-MM-DD"),
        due_date: values.range?.[1]?.format("YYYY-MM-DD"),
        completion_criteria: criteria,
      } as Partial<MilestoneRow>;
      const saved = milestone
        ? await api.updateMilestone(milestone.milestone_id, body)
        : await api.createMilestone(body);
      message.success(milestone ? "Milestone updated" : "Milestone created");
      onSaved(saved);
      onClose();
    } catch (err) {
      message.error(err instanceof ApiError ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      title={milestone ? `Edit ${milestone.milestone_id}` : "Create Milestone"}
      okText={milestone ? "Save changes" : "Create"}
      onOk={submit}
      confirmLoading={saving}
      onCancel={onClose}
      destroyOnClose
      width={720}
    >
      <Form form={form} layout="vertical" requiredMark={false} disabled={saving}>
        <Form.Item
          name="name"
          label="Milestone name"
          rules={[{ required: true, message: "Name is required" }]}
        >
          <Input placeholder="User Dashboard Enhancement" />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <Input.TextArea rows={2} placeholder="What does done look like?" />
        </Form.Item>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4">
          <Form.Item name="project_id" label="Project">
            <Select allowClear showSearch optionFilterProp="label" options={options?.projects} />
          </Form.Item>
          <Form.Item name="department" label="Department">
            <Select allowClear showSearch optionFilterProp="label" options={options?.departments} />
          </Form.Item>
          <Form.Item name="team_id" label="Team">
            <Select allowClear showSearch optionFilterProp="label" options={options?.teams} />
          </Form.Item>
          <Form.Item name="owner_id" label="Owner">
            <Select allowClear showSearch optionFilterProp="label" options={options?.owners} />
          </Form.Item>
          <Form.Item name="manager_id" label="Manager (approves daily entries)">
            <Select allowClear showSearch optionFilterProp="label" options={options?.managers} />
          </Form.Item>
          <Form.Item name="category" label="Category">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              options={options?.categories}
            />
          </Form.Item>
          <Form.Item name="priority" label="Priority" initialValue="Medium">
            <Select
              options={(options?.priorities ?? ["High", "Medium", "Low"]).map((p) => ({
                value: p,
                label: p,
              }))}
            />
          </Form.Item>
          <Form.Item name="status" label="Status" initialValue="not_started">
            <Select options={STATUS_OPTIONS} />
          </Form.Item>
        </div>
        <Form.Item
          name="range"
          label="Start & due date"
          rules={[{ required: true, message: "Health is measured against this window" }]}
        >
          <DatePicker.RangePicker className="w-full" />
        </Form.Item>
        <Form.Item
          name="criteria"
          label="Completion criteria"
          help="One per line. Ticked off as the milestone progresses."
        >
          <Input.TextArea rows={4} placeholder={"Design finalized\nAll items implemented"} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
