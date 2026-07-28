import { Avatar, Button, Card, Empty, Progress, Table, Tag, Typography } from "antd";
import { UserOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import type {
  MilestoneAttentionRow,
  MilestoneDeadlineRow,
  MilestoneDepartmentRow,
  MilestoneTopPerformer,
} from "../../lib/api";
import { HealthBadge, PriorityTag, RiskTag } from "./MilestoneBadges";

const { Text } = Typography;

const CARD_BODY = { body: { paddingTop: 8 } };

function ViewAll({ to }: { to: string }) {
  return (
    <Link to={to}>
      <Button type="link" size="small" className="px-0">
        View All
      </Button>
    </Link>
  );
}

/** Per-department progress with the health band beside it — the bar alone
 * can't say whether 71% is ahead of or behind schedule. */
export function DepartmentProgressCard({ rows }: { rows: MilestoneDepartmentRow[] }) {
  return (
    <Card title="Department Progress Overview" size="small" bordered={false} className="h-full">
      {rows?.length ? (
        <div className="flex flex-col gap-3">
          {rows.map((row) => (
            <div key={row.dept_id} className="flex items-center gap-3">
              <Link
                to={`/milestones/department/${row.dept_id}`}
                className="w-28 sm:w-32 shrink-0 truncate text-sm"
              >
                {row.name}
              </Link>
              <Progress
                percent={Math.round(row.progress_pct)}
                size="small"
                className="flex-1 !mb-0"
                strokeColor={
                  row.health === "at_risk"
                    ? "#cf1322"
                    : row.health === "needs_attention"
                      ? "#d48806"
                      : "#157f52"
                }
              />
              <div className="w-[110px] shrink-0 text-right">
                <HealthBadge
                  health={row.health}
                  actual={row.progress_pct}
                  planned={row.planned_pct}
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="No departments in scope" />
      )}
    </Card>
  );
}

export function TopPerformersCard({
  rows,
  viewAllTo = "/milestones/reports?report=employee_performance",
}: {
  rows: MilestoneTopPerformer[];
  viewAllTo?: string;
}) {
  return (
    <Card
      title="Top Performers (This Month)"
      size="small"
      bordered={false}
      className="h-full"
      styles={CARD_BODY}
      extra={<ViewAll to={viewAllTo} />}
    >
      <Table
        size="small"
        rowKey="user_id"
        dataSource={rows ?? []}
        pagination={false}
        scroll={{ x: "max-content" }}
        columns={[
          { title: "Rank", dataIndex: "rank", width: 60 },
          {
            title: "Employee",
            dataIndex: "name",
            render: (name: string, row) => (
              <Link to={`/milestones/employee/${row.user_id}`} className="whitespace-nowrap">
                {name}
              </Link>
            ),
          },
          { title: "Department", dataIndex: "department", responsive: ["md"] },
          { title: "Completed", dataIndex: "completed", width: 100 },
          {
            title: "Completion %",
            dataIndex: "completion_pct",
            width: 120,
            render: (v: number) => `${v}%`,
          },
          {
            title: "Score",
            dataIndex: "score",
            width: 80,
            render: (v: number) => <Tag color="green">{v}</Tag>,
          },
        ]}
      />
    </Card>
  );
}

export function NeedsAttentionCard({
  rows,
  viewAllTo = "/milestones/reports?report=overdue_milestones",
}: {
  rows: MilestoneAttentionRow[];
  viewAllTo?: string;
}) {
  return (
    <Card
      title="Employees Needing Attention"
      size="small"
      bordered={false}
      className="h-full"
      styles={CARD_BODY}
      extra={<ViewAll to={viewAllTo} />}
    >
      <Table
        size="small"
        rowKey="user_id"
        dataSource={rows ?? []}
        pagination={false}
        scroll={{ x: "max-content" }}
        locale={{ emptyText: "Nobody is behind — nothing to flag." }}
        columns={[
          {
            title: "Employee",
            dataIndex: "name",
            render: (name: string, row) => (
              <div className="flex items-center gap-2 whitespace-nowrap">
                <Avatar size="small" icon={<UserOutlined />} />
                <Link to={`/milestones/employee/${row.user_id}`}>{name}</Link>
              </div>
            ),
          },
          { title: "Department", dataIndex: "department", responsive: ["md"] },
          { title: "Overdue", dataIndex: "overdue_milestones", width: 90 },
          { title: "Overdue Days", dataIndex: "overdue_days", width: 120 },
          {
            title: "Risk",
            dataIndex: "risk",
            width: 90,
            render: (risk: string) => <RiskTag risk={risk} />,
          },
        ]}
      />
    </Card>
  );
}

export function UpcomingDeadlinesCard({
  rows,
  viewAllTo = "/milestones/reports?report=upcoming_deadlines",
}: {
  rows: MilestoneDeadlineRow[];
  viewAllTo?: string;
}) {
  return (
    <Card
      title="Upcoming Deadlines"
      size="small"
      bordered={false}
      className="h-full"
      styles={CARD_BODY}
      extra={<ViewAll to={viewAllTo} />}
    >
      <Table
        size="small"
        rowKey="milestone_id"
        dataSource={rows ?? []}
        pagination={false}
        scroll={{ x: "max-content" }}
        locale={{ emptyText: "No deadlines ahead in this scope." }}
        columns={[
          {
            title: "Milestone",
            dataIndex: "name",
            render: (name: string, row) => (
              <div className="min-w-[160px]">
                <Link to={`/milestones/detail/${row.milestone_id}`}>{name}</Link>
                {row.owner_name && (
                  <div>
                    <Text type="secondary" className="text-[11px]">
                      {row.owner_name}
                    </Text>
                  </div>
                )}
              </div>
            ),
          },
          {
            title: "Due Date",
            dataIndex: "due_date",
            width: 130,
            render: (due: string, row) => (
              <div className="whitespace-nowrap">
                {due}
                <div>
                  <Text type="secondary" className="text-[11px]">
                    {row.days_left === 0 ? "today" : `in ${row.days_left}d`}
                  </Text>
                </div>
              </div>
            ),
          },
          {
            title: "Priority",
            dataIndex: "priority",
            width: 100,
            render: (p: string) => <PriorityTag priority={p} />,
          },
        ]}
      />
    </Card>
  );
}
