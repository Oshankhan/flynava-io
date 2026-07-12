import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Alert,
  Avatar,
  Breadcrumb,
  Button,
  Card,
  Col,
  Empty,
  Flex,
  Row,
  Spin,
  Tag,
  Typography,
} from "antd";
import { RightOutlined, TeamOutlined } from "@ant-design/icons";
import { api, ApiError, type OrgReportRow } from "../lib/api";
import { useAuth } from "../lib/auth";
import { BRAND } from "../lib/brand";

const { Text, Title } = Typography;

interface Crumb {
  user_id: string;
  name: string;
  designation?: string | null;
}

export default function MyTeam() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();

  const [stack, setStack] = useState<Crumb[] | null>(null);
  const [reports, setReports] = useState<OrgReportRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Initialize the root of the drill (either ?root=<user_id> from a
  // dashboard's department card, or the viewer's own direct reports).
  useEffect(() => {
    if (!user) return;
    const rootId = params.get("root") || user.user_id;
    api
      .userOverview(rootId)
      .then((o) =>
        setStack([{ user_id: rootId, name: o.user.name, designation: o.user.designation }])
      )
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load team"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, params]);

  const currentId = stack?.[stack.length - 1]?.user_id;

  useEffect(() => {
    if (!currentId) return;
    setReports(null);
    api
      .orgReports(currentId)
      .then(setReports)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load reports"));
  }, [currentId]);

  if (error) return <Alert type="error" message={error} showIcon />;
  if (!stack || !reports)
    return (
      <Flex justify="center" style={{ paddingTop: 80 }}>
        <Spin />
      </Flex>
    );

  const totals = reports.reduce(
    (acc, r) => ({
      total: acc.total + r.buckets.total,
      completed: acc.completed + r.buckets.completed,
      overdue: acc.overdue + r.buckets.overdue,
      reopened: acc.reopened + r.reopened_count,
    }),
    { total: 0, completed: 0, overdue: 0, reopened: 0 }
  );

  const current = stack[stack.length - 1];

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 12 }}
        items={stack.map((c, i) => ({
          key: c.user_id,
          title:
            i === stack.length - 1 ? (
              <Text strong>{c.name}</Text>
            ) : (
              <a onClick={() => setStack(stack.slice(0, i + 1))}>{c.name}</a>
            ),
        }))}
      />

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} md={12}>
          <Card size="small" bordered={false}>
            <Title level={5} style={{ marginTop: 0 }}>
              {current.name}'s Team
            </Title>
            <Text type="secondary">
              {reports.length} direct report{reports.length === 1 ? "" : "s"}
              {current.designation ? ` · ${current.designation}` : ""}
            </Text>
          </Card>
        </Col>
        {reports.length > 0 && (
          <Col xs={24} md={12}>
            <Card size="small" bordered={false}>
              <Flex gap={8} wrap>
                <Tag>{totals.total} tasks</Tag>
                <Tag color="success">{totals.completed} done</Tag>
                <Tag color="error">{totals.overdue} overdue</Tag>
                {totals.reopened > 0 && <Tag color="orange">{totals.reopened} reopened bugs</Tag>}
              </Flex>
            </Card>
          </Col>
        )}
      </Row>

      {reports.length === 0 ? (
        <Card size="small" bordered={false}>
          <Empty description="No direct reports here." />
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {reports.map((m) => (
            <Col key={m.user_id} xs={24} sm={12} lg={8} xl={6}>
              <Card size="small" style={{ height: "100%" }}>
                <Flex align="center" gap={10} style={{ marginBottom: 8 }}>
                  <Avatar style={{ background: BRAND.primary }}>{m.name[0]}</Avatar>
                  <div style={{ minWidth: 0 }}>
                    <Text strong style={{ fontSize: 13 }} ellipsis>{m.name}</Text>
                    <div>
                      <Text type="secondary" style={{ fontSize: 11 }} ellipsis>
                        {m.designation ?? "—"}{m.team_name ? ` · ${m.team_name}` : ""}
                      </Text>
                    </div>
                  </div>
                </Flex>
                <Flex gap={4} wrap style={{ marginBottom: 10 }}>
                  <Tag>{m.buckets.completed}/{m.buckets.total} tasks</Tag>
                  {m.buckets.overdue > 0 && <Tag color="error">{m.buckets.overdue} overdue</Tag>}
                  {m.reopened_count > 0 && <Tag color="orange">{m.reopened_count} reopened</Tag>}
                  {m.late_7d > 0 && <Tag color="gold">{m.late_7d} late (7d)</Tag>}
                  {m.absent_7d > 0 && <Tag color="red">{m.absent_7d} absent (7d)</Tag>}
                  {m.pending_requests > 0 && <Tag color="blue">{m.pending_requests} pending req</Tag>}
                </Flex>
                <Flex gap={8}>
                  {m.has_reports && (
                    <Button
                      size="small"
                      icon={<TeamOutlined />}
                      onClick={() => setStack([...stack, { user_id: m.user_id, name: m.name, designation: m.designation }])}
                    >
                      View Team <RightOutlined />
                    </Button>
                  )}
                  <Button size="small" type="primary" onClick={() => navigate(`/people/${m.user_id}`)}>
                    Dashboard
                  </Button>
                </Flex>
              </Card>
            </Col>
          ))}
        </Row>
      )}
    </div>
  );
}
