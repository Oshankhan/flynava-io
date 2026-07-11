import { useEffect, useState } from "react";
import {
  Alert,
  Avatar,
  Card,
  Col,
  Empty,
  Flex,
  Progress,
  Row,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import { api, ApiError, type OrgMe, type TeamTasks } from "../lib/api";
import { BRAND } from "../lib/brand";

const { Text, Title } = Typography;

export default function MyTeam() {
  const [org, setOrg] = useState<OrgMe | null>(null);
  const [tasks, setTasks] = useState<TeamTasks | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.orgMe().then(setOrg).catch((e) =>
      setError(e instanceof ApiError ? e.message : "Failed to load team"));
    api.teamTasks().then(setTasks).catch(() => setTasks(null));
  }, []);

  if (error) return <Alert type="error" message={error} showIcon />;
  if (!org)
    return (
      <Flex justify="center" style={{ paddingTop: 80 }}>
        <Spin size="large" />
      </Flex>
    );

  const members = org.reports;
  const load = tasks?.members ?? [];
  const loadFor = (uid: string) => load.find((m) => m.user_id === uid);

  const columns = [
    {
      title: "Member",
      key: "name",
      render: (_: unknown, r: (typeof members)[number]) => (
        <Flex gap={10} align="center">
          <Avatar style={{ background: BRAND.primary }}>{r.name[0]}</Avatar>
          <div>
            <Text strong style={{ fontSize: 13 }}>{r.name}</Text>
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>{r.designation ?? "—"}</Text>
            </div>
          </div>
        </Flex>
      ),
    },
    {
      title: "Tasks",
      key: "tasks",
      width: 110,
      render: (_: unknown, r: (typeof members)[number]) => {
        const l = loadFor(r.user_id);
        return l ? `${l.completed} / ${l.total}` : "—";
      },
    },
    {
      title: "Open workload",
      key: "load",
      width: 220,
      render: (_: unknown, r: (typeof members)[number]) => {
        const l = loadFor(r.user_id);
        if (!l || l.total === 0) return <Text type="secondary">no tasks</Text>;
        const openPct = Math.round(((l.total - l.completed) / l.total) * 100);
        return (
          <Progress
            percent={openPct}
            size="small"
            strokeColor={openPct > 80 ? "#ef4444" : openPct > 50 ? "#f59e0b" : BRAND.primary}
          />
        );
      },
    },
    {
      title: "Overdue",
      key: "overdue",
      width: 100,
      render: (_: unknown, r: (typeof members)[number]) => {
        const l = loadFor(r.user_id);
        return l && l.overdue > 0 ? <Tag color="error">{l.overdue}</Tag> : <Tag>0</Tag>;
      },
    },
  ];

  return (
    <div>
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} md={12}>
          <Card size="small" bordered={false}>
            <Title level={5} style={{ marginTop: 0 }}>
              {org.team?.name ?? "My Team"}
            </Title>
            <Text type="secondary">
              {members.length} member(s)
              {org.lead ? ` · You report to ${org.lead.name}` : ""}
            </Text>
          </Card>
        </Col>
        {tasks && (
          <Col xs={24} md={12}>
            <Card size="small" bordered={false}>
              <Flex gap={8} wrap>
                <Tag>{tasks.buckets.total} team tasks</Tag>
                <Tag color="success">{tasks.buckets.completed} done</Tag>
                <Tag color="processing">{tasks.buckets.in_progress} in progress</Tag>
                <Tag color="error">{tasks.buckets.overdue} overdue</Tag>
                {tasks.reopened.length > 0 && (
                  <Tag color="orange">{tasks.reopened.length} reopened bugs</Tag>
                )}
              </Flex>
            </Card>
          </Col>
        )}
      </Row>

      <Card size="small" bordered={false} title="Members">
        {members.length === 0 ? (
          <Empty description="No direct reports — this view fills in once people report to you." />
        ) : (
          <Table
            size="small"
            rowKey="user_id"
            dataSource={members}
            columns={columns}
            pagination={false}
          />
        )}
      </Card>
    </div>
  );
}
