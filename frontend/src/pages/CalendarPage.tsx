import { useCallback, useEffect, useState } from "react";
import {
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
  Tag,
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
  const today = dayjs();

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} lg={16}>
        <Card size="small" bordered={false} styles={{ body: { paddingTop: 4 } }}>
          <Calendar
            value={selected}
            onSelect={setSelected}
            fullCellRender={(d, info) => {
              const day = d as Dayjs;
              if (info.type !== "date") return info.originNode;
              const isToday = day.isSame(today, "day");
              const isSelected = day.isSame(selected, "day");
              const inMonth = day.isSame(selected, "month");
              const ms = byDay(day);
              return (
                <div
                  style={{
                    minHeight: 78,
                    borderRadius: 8,
                    padding: "4px 6px",
                    margin: 2,
                    background: isSelected
                      ? `${BRAND.primary}1f`
                      : isToday
                      ? `${BRAND.primary}0d`
                      : "transparent",
                    border: isToday ? `1px solid ${BRAND.primary}66` : "1px solid transparent",
                    opacity: inMonth ? 1 : 0.4,
                  }}
                >
                  <Text
                    style={{
                      fontSize: 12,
                      fontWeight: isToday ? 700 : 400,
                      color: isToday ? BRAND.primaryStrong : undefined,
                    }}
                  >
                    {day.date()}
                  </Text>
                  <Flex vertical gap={2} style={{ marginTop: 2 }}>
                    {ms.slice(0, 2).map((m) => (
                      <div
                        key={m.meeting_id}
                        style={{
                          fontSize: 11,
                          lineHeight: "16px",
                          padding: "0 6px",
                          borderRadius: 6,
                          background: `${BRAND.primary}1a`,
                          color: BRAND.primaryStrong,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {m.title}
                      </div>
                    ))}
                    {ms.length > 2 && (
                      <Text type="secondary" style={{ fontSize: 10 }}>
                        +{ms.length - 2} more
                      </Text>
                    )}
                  </Flex>
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
            styles={{ body: { minHeight: 420 } }}
          >
            {dayList.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No meetings" />
            ) : (
              <List
                dataSource={dayList}
                renderItem={(m) => (
                  <List.Item
                    style={{ padding: "12px 4px" }}
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
                        <Flex align="center" gap={8} wrap>
                          <Tag color={BRAND.primary} style={{ marginInlineEnd: 0 }}>
                            {m.start.slice(11, 16)}–{m.end.slice(11, 16)}
                          </Tag>
                          <Text style={{ fontSize: 13 }}>{m.title}</Text>
                        </Flex>
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

