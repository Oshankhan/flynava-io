import { useCallback, useEffect, useState } from "react";
import {
  Badge,
  Button,
  Calendar,
  Card,
  Col,
  DatePicker,
  Empty,
  Flex,
  Form,
  Input,
  List,
  message,
  Modal,
  Row,
  Select,
  TimePicker,
  Typography,
} from "antd";
import type { Dayjs } from "dayjs";
import dayjs from "dayjs";
import { DeleteOutlined, PlusOutlined } from "@ant-design/icons";
import { api, ApiError, type Meeting, type UserLite } from "../lib/api";
import { useAuth } from "../lib/auth";
import { BRAND } from "../lib/brand";

const { Text } = Typography;

export default function CalendarPage() {
  const { user } = useAuth();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [selected, setSelected] = useState<Dayjs>(dayjs());
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [people, setPeople] = useState<UserLite[]>([]);
  const [form] = Form.useForm();

  const load = useCallback(() => {
    api.myMeetings().then(setMeetings).catch(() => setMeetings([]));
  }, []);

  useEffect(load, [load]);

  useEffect(() => {
    if (open) api.orgUsers().then(setPeople).catch(() => setPeople([]));
  }, [open]);

  const byDay = (d: Dayjs) => meetings.filter((m) => m.start.slice(0, 10) === d.format("YYYY-MM-DD"));

  async function create(values: {
    title: string;
    date: Dayjs;
    time: [Dayjs, Dayjs];
    attendee_ids?: string[];
    location?: string;
    agenda?: string;
  }) {
    setSaving(true);
    try {
      const day = values.date.format("YYYY-MM-DD");
      await api.createMeeting({
        title: values.title,
        start: `${day}T${values.time[0].format("HH:mm")}`,
        end: `${day}T${values.time[1].format("HH:mm")}`,
        attendee_ids: values.attendee_ids ?? [],
        location: values.location ?? "",
        agenda: values.agenda ?? "",
      });
      message.success("Meeting scheduled — invitees notified");
      setOpen(false);
      form.resetFields();
      load();
    } catch (e) {
      message.error(e instanceof ApiError ? e.message : "Could not schedule");
    } finally {
      setSaving(false);
    }
  }

  async function cancel(m: Meeting) {
    Modal.confirm({
      title: `Cancel “${m.title}”?`,
      onOk: async () => {
        try {
          await api.cancelMeeting(m.meeting_id);
          message.success("Meeting cancelled");
          load();
        } catch (e) {
          message.error(e instanceof ApiError ? e.message : "Cancel failed");
        }
      },
    });
  }

  const dayList = byDay(selected);

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={16}>
        <Card size="small" bordered={false}>
          <Calendar
            value={selected}
            onSelect={setSelected}
            cellRender={(d, info) => {
              if (info.type !== "date") return null;
              const ms = byDay(d as Dayjs);
              return (
                <div>
                  {ms.slice(0, 3).map((m) => (
                    <div key={m.meeting_id} style={{ fontSize: 11, lineHeight: 1.4 }}>
                      <Badge color={BRAND.primary} text={<span style={{ fontSize: 11 }}>{m.title}</span>} />
                    </div>
                  ))}
                  {ms.length > 3 && (
                    <Text type="secondary" style={{ fontSize: 10 }}>+{ms.length - 3} more</Text>
                  )}
                </div>
              );
            }}
          />
        </Card>
      </Col>
      <Col xs={24} lg={8}>
        <Flex vertical gap={16}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)} block>
            New Meeting
          </Button>
          <Card
            size="small"
            bordered={false}
            title={selected.format("dddd, D MMMM")}
          >
            {dayList.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No meetings" />
            ) : (
              <List
                size="small"
                dataSource={dayList}
                renderItem={(m) => (
                  <List.Item
                    actions={
                      m.organizer_id === user?.user_id
                        ? [
                            <Button
                              key="x"
                              type="text"
                              size="small"
                              danger
                              icon={<DeleteOutlined />}
                              onClick={() => cancel(m)}
                            />,
                          ]
                        : []
                    }
                  >
                    <List.Item.Meta
                      title={
                        <Text style={{ fontSize: 13 }}>
                          {m.start.slice(11, 16)}–{m.end.slice(11, 16)} · {m.title}
                        </Text>
                      }
                      description={
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {[m.location, `by ${m.organizer_name}`, `${m.attendee_ids.length} attendees`]
                            .filter(Boolean)
                            .join(" · ")}
                        </Text>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Flex>
      </Col>

      <Modal
        title="New Meeting"
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={saving}
        okText="Schedule"
      >
        <Form form={form} layout="vertical" onFinish={create} initialValues={{ date: selected }}>
          <Form.Item name="title" label="Title" rules={[{ required: true, message: "Title required" }]}>
            <Input maxLength={200} />
          </Form.Item>
          <Flex gap={12}>
            <Form.Item name="date" label="Date" rules={[{ required: true }]} style={{ flex: 1 }}>
              <DatePicker style={{ width: "100%" }} />
            </Form.Item>
            <Form.Item name="time" label="Time" rules={[{ required: true, message: "Pick a time" }]} style={{ flex: 1 }}>
              <TimePicker.RangePicker format="HH:mm" minuteStep={15} style={{ width: "100%" }} />
            </Form.Item>
          </Flex>
          <Form.Item name="attendee_ids" label="Invite">
            <Select
              mode="multiple"
              showSearch
              optionFilterProp="label"
              placeholder="Pick attendees"
              options={people
                .filter((p) => p.user_id !== user?.user_id)
                .map((p) => ({
                  value: p.user_id,
                  label: `${p.name}${p.designation ? ` — ${p.designation}` : ""}`,
                }))}
            />
          </Form.Item>
          <Form.Item name="location" label="Location / Link">
            <Input placeholder="Meet, Board Room…" />
          </Form.Item>
          <Form.Item name="agenda" label="Agenda">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </Row>
  );
}

