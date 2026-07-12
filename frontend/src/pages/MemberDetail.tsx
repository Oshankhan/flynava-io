import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  Avatar,
  Button,
  Card,
  Col,
  Empty,
  Flex,
  List,
  Row,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import { ArrowLeftOutlined, ScheduleOutlined } from "@ant-design/icons";
import { api, ApiError, type TaskRow, type UserOverview } from "../lib/api";

const { Text, Title } = Typography;

const BUCKET_TAG: Record<string, string> = {
  completed: "success",
  in_progress: "processing",
  pending: "default",
  overdue: "error",
};

const TILE_TINT = {
  primary: "text-io-600",
  amber: "text-amber-500",
  sky: "text-sky-400",
  red: "text-red-500",
} as const;

function StatTile({ label, value, tint }: { label: string; value: number; tint: keyof typeof TILE_TINT }) {
  return (
    <Card size="small" bordered={false} className="h-full">
      <Text type="secondary" className="text-xs">{label}</Text>
      <div className={`text-[22px] font-bold ${TILE_TINT[tint]}`}>{value}</div>
    </Card>
  );
}

export default function MemberDetail() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<UserOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) return;
    setData(null);
    setError(null);
    api
      .userOverview(userId)
      .then(setData)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load this person's dashboard"));
  }, [userId]);

  if (error) return <Alert type="error" message={error} showIcon />;
  if (!data)
    return (
      <Flex justify="center" className="pt-20">
        <Spin />
      </Flex>
    );

  const { user: u, buckets: b } = data;

  const taskCols = [
    { title: "Task", dataIndex: "title", key: "title", ellipsis: true },
    {
      title: "Status", key: "status", width: 120,
      render: (_: unknown, r: TaskRow) => <Tag color={BUCKET_TAG[r.bucket]}>{r.status ?? "—"}</Tag>,
    },
    { title: "Priority", dataIndex: "priority", key: "priority", width: 90,
      render: (p: string | null) => p ?? "—" },
    { title: "Due", dataIndex: "due_date", key: "due", width: 110,
      render: (d: string | null) => d ?? "—" },
  ];

  const attendanceCols = [
    { title: "Date", dataIndex: "date", key: "date", width: 110 },
    { title: "In", dataIndex: "in_time", key: "in", width: 80, render: (v: string) => v || "—" },
    { title: "Out", dataIndex: "out_time", key: "out", width: 80, render: (v: string) => v || "—" },
    {
      title: "Status", dataIndex: "status", key: "status", width: 90,
      render: (s: string) => (
        <Tag color={s === "Late" ? "gold" : s === "Absent" ? "red" : "success"}>{s}</Tag>
      ),
    },
  ];

  return (
    <div>
      <Button
        type="link"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate(-1)}
        className="px-0 mb-2"
      >
        Back
      </Button>

      <Card size="small" bordered={false} className="mb-4">
        <Flex align="center" gap={16} wrap>
          <Avatar size={56} className="bg-io-600 text-[22px]">
            {u.name[0]}
          </Avatar>
          <div>
            <Title level={4} className="m-0">{u.name}</Title>
            <Text type="secondary">
              {u.designation ?? "—"}
              {data.team ? ` · ${data.team.name}` : ""}
              {data.lead ? ` · Reports to ${data.lead.name}` : ""}
            </Text>
          </div>
        </Flex>
      </Card>

      <Row gutter={[16, 16]}>
        <Col flex="1 1 140px"><StatTile label="Total Tasks" value={b.total} tint="primary" /></Col>
        <Col flex="1 1 140px"><StatTile label="Completed" value={b.completed} tint="primary" /></Col>
        <Col flex="1 1 140px"><StatTile label="In Progress" value={b.in_progress} tint="amber" /></Col>
        <Col flex="1 1 140px"><StatTile label="Pending" value={b.pending} tint="sky" /></Col>
        <Col flex="1 1 140px"><StatTile label="Overdue" value={b.overdue} tint="red" /></Col>
      </Row>

      <Row gutter={[16, 16]} className="mt-4">
        <Col xs={24} lg={14}>
          <Card size="small" bordered={false} title="Tasks" className="h-full">
            {data.tasks.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No tasks" />
            ) : (
              <Table size="small" rowKey="task_id" dataSource={data.tasks} columns={taskCols}
                pagination={{ pageSize: 8, showSizeChanger: false }} scroll={{ x: true }} />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Card size="small" bordered={false} title="Reopened Bugs">
                {data.reopened.length === 0 ? (
                  <Text type="secondary" className="text-xs">None. 🎉</Text>
                ) : (
                  <List size="small" dataSource={data.reopened}
                    renderItem={(t) => (
                      <List.Item actions={[<Tag key="p" color="orange">{t.priority ?? "—"}</Tag>]}>
                        <Text className="text-[13px]">{t.title}</Text>
                      </List.Item>
                    )} />
                )}
              </Card>
            </Col>
            <Col span={24}>
              <Card size="small" bordered={false} title="Bugs Authored">
                {data.authored.length === 0 ? (
                  <Text type="secondary" className="text-xs">None.</Text>
                ) : (
                  <List size="small" dataSource={data.authored}
                    renderItem={(t) => (
                      <List.Item actions={[<Tag key="s">{t.status ?? "—"}</Tag>]}>
                        <Text className="text-[13px]">{t.title}</Text>
                      </List.Item>
                    )} />
                )}
              </Card>
            </Col>
          </Row>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            size="small"
            bordered={false}
            title={
              <Flex align="center" gap={6}>
                <ScheduleOutlined className="text-io-600" /> Attendance (last 7 days)
              </Flex>
            }
          >
            <Flex gap={16} className="mb-2.5">
              <Text><b>{data.attendance.present_count}</b> present</Text>
              <Text><b className="text-amber-500">{data.attendance.late_count}</b> late</Text>
              <Text><b className="text-red-500">{data.attendance.absent_count}</b> absent</Text>
              {data.attendance.avg_hours != null && (
                <Text type="secondary">avg {data.attendance.avg_hours}h/day</Text>
              )}
            </Flex>
            {data.attendance.rows.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No attendance data" />
            ) : (
              <Table size="small" rowKey="date" dataSource={data.attendance.rows}
                columns={attendanceCols} pagination={false} scroll={{ x: true }}
                rowClassName={(r) => (r.status === "Late" ? "attendance-late-row" : "")} />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" bordered={false} title="Leave Balance & History">
            {data.leave_balance ? (
              <Flex gap={20} className="mb-2.5">
                {Object.entries(data.leave_balance).map(([type, days]) => (
                  <div key={type} className="text-center">
                    <div className="text-lg font-bold text-io-900">{days}</div>
                    <Text type="secondary" className="text-[11px]">{type}</Text>
                  </div>
                ))}
              </Flex>
            ) : (
              <Text type="secondary" className="text-xs">No HR record linked.</Text>
            )}
            {data.recent_leaves.length > 0 && (
              <List size="small" dataSource={data.recent_leaves}
                renderItem={(l) => (
                  <List.Item actions={[<Tag key="s" color={l.status === "Approved" ? "success" : "processing"}>{l.status}</Tag>]}>
                    <Text className="text-xs">{l.type} · {l.from} → {l.to} · {l.days}d</Text>
                  </List.Item>
                )} />
            )}
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card size="small" bordered={false} title="Pending Documents">
            {data.pending_docs.length === 0 ? (
              <Text type="secondary" className="text-xs">Nothing pending.</Text>
            ) : (
              <List size="small" dataSource={data.pending_docs}
                renderItem={(d) => (
                  <List.Item actions={[<Tag key="k">{d.kind}</Tag>]}>
                    <Text className="text-[13px]">{d.title}</Text>
                  </List.Item>
                )} />
            )}
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card size="small" bordered={false} title="Recent Activity">
            {data.activity.length === 0 ? (
              <Text type="secondary" className="text-xs">Nothing yet.</Text>
            ) : (
              <List size="small" dataSource={data.activity}
                renderItem={(a) => (
                  <List.Item>
                    <List.Item.Meta
                      title={<Text className="text-[13px]">{a.text}</Text>}
                      description={<Text type="secondary" className="text-[11px]">
                        {new Date(a.at).toLocaleString()}
                      </Text>}
                    />
                  </List.Item>
                )} />
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
