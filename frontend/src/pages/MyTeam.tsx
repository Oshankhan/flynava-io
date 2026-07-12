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
  Progress,
  Row,
  Spin,
  Statistic,
  Tag,
  Typography,
} from "antd";
import { RightOutlined, TeamOutlined } from "@ant-design/icons";
import { api, ApiError, type OrgReportRow } from "../lib/api";
import { useAuth } from "../lib/auth";

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
      <Flex justify="center" className="pt-20">
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
  const completionPct = totals.total > 0 ? Math.round((totals.completed / totals.total) * 100) : 0;

  const current = stack[stack.length - 1];

  return (
    <div>
      <Breadcrumb
        className="mb-3"
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

      <Card size="small" bordered={false} className="mb-4">
        <Flex justify="space-between" align="center" wrap gap={16}>
          <Flex align="center" gap={14}>
            <Avatar size={48} className="bg-io-600 text-lg">{current.name[0]}</Avatar>
            <div>
              <Title level={5} className="m-0">{current.name}'s Team</Title>
              <Text type="secondary" className="text-[13px]">
                {reports.length} direct report{reports.length === 1 ? "" : "s"}
                {current.designation ? ` · ${current.designation}` : ""}
              </Text>
            </div>
          </Flex>
          {reports.length > 0 && (
            <Flex gap={28} wrap>
              <Statistic title="Tasks" value={totals.total} />
              <Statistic
                title="Completion"
                value={completionPct}
                suffix="%"
                valueStyle={{ color: completionPct >= 70 ? "#3f8600" : undefined }}
              />
              <Statistic
                title="Overdue"
                value={totals.overdue}
                valueStyle={totals.overdue > 0 ? { color: "#cf1322" } : undefined}
              />
              {totals.reopened > 0 && (
                <Statistic title="Reopened bugs" value={totals.reopened} valueStyle={{ color: "#d46b08" }} />
              )}
            </Flex>
          )}
        </Flex>
      </Card>

      {reports.length === 0 ? (
        <Card size="small" bordered={false}>
          <Empty description="No direct reports here." />
        </Card>
      ) : (
        <Row gutter={[16, 16]}>
          {reports.map((m) => {
            const pct = m.buckets.total > 0
              ? Math.round((m.buckets.completed / m.buckets.total) * 100)
              : 0;
            return (
              <Col key={m.user_id} xs={24} sm={12} lg={8} xl={6}>
                <Card size="small" className="h-full">
                  <Flex align="center" gap={10} className="mb-2">
                    <Avatar className="bg-io-600">{m.name[0]}</Avatar>
                    <div className="min-w-0">
                      <Text strong className="text-[13px]" ellipsis>{m.name}</Text>
                      <div>
                        <Text type="secondary" className="text-[11px]" ellipsis>
                          {m.designation ?? "—"}
                        </Text>
                      </div>
                    </div>
                  </Flex>

                  <Flex gap={4} wrap className="mb-2">
                    {m.team_name && <Tag color="geekblue">{m.team_name}</Tag>}
                    {m.project_codes.map((code) => (
                      <Tag key={code} color="purple">{code}</Tag>
                    ))}
                  </Flex>

                  <Flex align="center" gap={8} className="mb-2">
                    <Progress
                      percent={pct}
                      size="small"
                      showInfo={false}
                      className="flex-1 mb-0"
                    />
                    <Text type="secondary" className="text-[11px] shrink-0">
                      {m.buckets.completed}/{m.buckets.total}
                    </Text>
                  </Flex>

                  <Flex gap={4} wrap className="mb-2.5">
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
                    <Button size="small" type="primary" onClick={() => navigate(`/member/${m.user_id}`)}>
                      Dashboard
                    </Button>
                  </Flex>
                </Card>
              </Col>
            );
          })}
        </Row>
      )}
    </div>
  );
}
