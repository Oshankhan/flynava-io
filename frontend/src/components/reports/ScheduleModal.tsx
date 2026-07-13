import { useEffect, useState } from "react";
import { Button, Flex, Form, InputNumber, Modal, Select, Switch, TimePicker, message } from "antd";
import dayjs, { type Dayjs } from "dayjs";
import { api, ApiError, type ReportDef, type ReportFrequency } from "../../lib/api";
import { useAsyncAction } from "../../lib/useAsyncAction";

const FREQ_OPTIONS: { value: ReportFrequency; label: string }[] = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "yearly", label: "Yearly" },
  { value: "custom", label: "Custom (every N days)" },
];
const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
  .map((label, value) => ({ value, label }));

export default function ScheduleModal({
  open, onClose, reportDef, onSaved,
}: {
  open: boolean;
  onClose: () => void;
  reportDef: ReportDef | null;
  onSaved: () => void;
}) {
  const [form] = Form.useForm();
  const frequency = Form.useWatch("frequency", form);
  const [removing, setRemoving] = useState(false);

  useEffect(() => {
    if (!open || !reportDef) return;
    const sched = reportDef.schedule;
    form.setFieldsValue({
      frequency: sched?.frequency ?? "monthly",
      time: dayjs(sched?.time ?? "09:00", "HH:mm"),
      weekday: sched?.weekday ?? 0,
      day_of_month: sched?.day_of_month ?? 1,
      every_n_days: sched?.every_n_days ?? 7,
      recipients: sched?.recipients ?? reportDef.recipients ?? [],
      active: sched?.active ?? true,
    });
  }, [open, reportDef, form]);

  const [save, saving] = useAsyncAction(async (values: {
    frequency: ReportFrequency; time: Dayjs; weekday: number; day_of_month: number;
    every_n_days: number; recipients: string[]; active: boolean;
  }) => {
    if (!reportDef) return;
    try {
      await api.setReportSchedule(reportDef.report_id, {
        frequency: values.frequency, time: values.time.format("HH:mm"),
        weekday: values.weekday, day_of_month: values.day_of_month,
        every_n_days: values.every_n_days, recipients: values.recipients, active: values.active,
      });
      message.success("Schedule saved");
      onSaved();
      onClose();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Failed to save schedule");
    }
  });

  async function removeSchedule() {
    if (!reportDef) return;
    setRemoving(true);
    try {
      await api.deleteReportSchedule(reportDef.report_id);
      message.success("Schedule removed");
      onSaved();
      onClose();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Failed to remove schedule");
    } finally {
      setRemoving(false);
    }
  }

  return (
    <Modal
      title={`Schedule "${reportDef?.name ?? ""}"`}
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={saving}
      okText="Save Schedule"
      footer={(originalNode) => (
        <Flex justify="space-between">
          {reportDef?.schedule ? (
            <Button danger loading={removing} onClick={removeSchedule}>Remove Schedule</Button>
          ) : <span />}
          <Flex gap={8}>{originalNode}</Flex>
        </Flex>
      )}
    >
      <Form form={form} layout="vertical" onFinish={save}>
        <Form.Item name="frequency" label="Frequency" rules={[{ required: true }]}>
          <Select options={FREQ_OPTIONS} />
        </Form.Item>
        <Form.Item name="time" label="Time (UTC)" rules={[{ required: true }]}>
          <TimePicker format="HH:mm" className="w-full" />
        </Form.Item>
        {frequency === "weekly" && (
          <Form.Item name="weekday" label="Day of week">
            <Select options={WEEKDAYS} />
          </Form.Item>
        )}
        {(frequency === "monthly" || frequency === "quarterly" || frequency === "yearly") && (
          <Form.Item name="day_of_month" label="Day of month">
            <InputNumber min={1} max={31} className="w-full" />
          </Form.Item>
        )}
        {frequency === "custom" && (
          <Form.Item name="every_n_days" label="Every N days">
            <InputNumber min={1} max={365} className="w-full" />
          </Form.Item>
        )}
        <Form.Item name="recipients" label="Recipients" extra="Email addresses to notify when this report runs">
          <Select mode="tags" placeholder="e.g. name@flynava.ai" tokenSeparators={[",", " "]} />
        </Form.Item>
        <Form.Item name="active" label="Active" valuePropName="checked">
          <Switch />
        </Form.Item>
      </Form>
    </Modal>
  );
}
