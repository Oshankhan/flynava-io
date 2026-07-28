import { useCallback, useEffect, useState } from "react";
import { Alert, Avatar, Button, Card, Col, Flex, Row, Spin, Statistic, Tabs, Typography } from "antd";
import { ReloadOutlined, UserOutlined } from "@ant-design/icons";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, type MilestoneEmployeePayload, type MilestoneRow } from "../../lib/api";
import { useAsyncAction } from "../../lib/useAsyncAction";
import { useAuth } from "../../lib/auth";
import MilestoneTable from "../../components/milestones/MilestoneTable";

const { Text, Title } = Typography;

/** Screen 4. `userId` falls back to the signed-in user, which is what the
 * nav entry resolves to for an employee whose scope is only themselves. */
export default function EmployeeMilestones({ userId }: { userId?: string }) {
  const params = useParams();
  const { user } = useAuth();
  const targetId = userId ?? params.userId ?? user?.user_id ?? "";
  const [data, setData] = useState<MilestoneEmployeePayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!targetId) return;
    try {
      setData(await api.employeeMilestones(targetId));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Load failed");
    }
  }, [targetId]);

  useEffect(() => {
    load();
  }, [load]);

  const [refresh, refreshing] = useAsyncAction(load);

  if (error)
    return (
      <Alert type="error" showIcon message="Cannot load employee milestones" description={error} />
    );
  if (!data)
    return (
      <Flex align="center" justify="center" className="min-h-[240px]">
        <Spin size="large" />
      </Flex>
    );

  const table = (rows: MilestoneRow[]) => (
    <MilestoneTable
      rows={rows}
      total={rows.length}
      page={1}
      pageSize={rows.length || 1}
      onPageChange={() => undefined}
      onChanged={load}
    />
  );

  return (
    <Flex vertical gap={16}>
      <Card size="small" bordered={false} className="shadow-sm">
        <Flex justify="space-between" align="center" wrap gap={16}>
          <Flex align="center" gap={12}>
            <Avatar size={48} icon={<UserOutlined />} className="bg-io-600" />
            <div>
              <Title level={5} className="!mb-0">
                {data.employee?.name}
              </Title>
              <Text type="secondary" className="text-xs">
                {data.employee?.designation ?? "—"}
                {data.employee?.department_name ? ` · ${data.employee.department_name}` : ""}
                {data.employee?.team_name ? ` · ${data.employee.team_name}` : ""}
              </Text>
            </div>
          </Flex>
          <Flex gap={8}>
            {data.employee?.department && (
              <Link to={`/milestones/department/${data.employee.department}`}>
                <Button>Department view</Button>
              </Link>
            )}
            <Button icon={<ReloadOutlined />} loading={refreshing} onClick={refresh}>
              Refresh
            </Button>
          </Flex>
        </Flex>

        <Row gutter={[16, 16]} className="mt-4">
          <Col xs={12} md={8} xl={4}>
            <Statistic title="Total Milestones" value={data.stats?.total ?? 0} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <Statistic title="Completed" value={data.stats?.completed ?? 0} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <Statistic title="In Progress" value={data.stats?.in_progress ?? 0} />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <Statistic
              title="Overdue"
              value={data.stats?.overdue ?? 0}
              valueStyle={{ color: (data.stats?.overdue ?? 0) > 0 ? "#cf1322" : undefined }}
            />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <Statistic
              title="Completion"
              value={data.stats?.completion_pct ?? 0}
              suffix="%"
              valueStyle={{ color: "#157f52" }}
            />
          </Col>
          <Col xs={12} md={8} xl={4}>
            <Statistic title="Avg Progress" value={data.stats?.avg_progress_pct ?? 0} suffix="%" />
          </Col>
        </Row>
      </Card>

      <Tabs
        defaultActiveKey="active"
        items={[
          {
            key: "active",
            label: `Active Milestones (${data.active?.length ?? 0})`,
            children: table(data.active ?? []),
          },
          {
            key: "completed",
            label: `Completed Milestones (${data.completed?.length ?? 0})`,
            children: table(data.completed ?? []),
          },
        ]}
      />
    </Flex>
  );
}
