import { Card, Checkbox, Col, Descriptions, Progress, Row, Statistic, Typography } from "antd";
import { Link } from "react-router-dom";
import type { MilestoneDetailPayload } from "../../../lib/api";
import { HealthBadge, PriorityTag, StatusTag } from "../MilestoneBadges";
import ProgressTrendChart from "../ProgressTrendChart";

const { Paragraph, Text } = Typography;

export default function OverviewTab({ data }: { data: MilestoneDetailPayload }) {
  const m = data.milestone;
  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} xl={10}>
        <Card title="General Information" size="small" bordered={false} className="h-full">
          <Descriptions column={1} size="small" colon={false} labelStyle={{ width: 140 }}>
            <Descriptions.Item label="Milestone ID">{m.milestone_id}</Descriptions.Item>
            <Descriptions.Item label="Milestone Name">{m.name}</Descriptions.Item>
            <Descriptions.Item label="Project">{m.project_name ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="Owner">
              {m.owner_id ? (
                <Link to={`/milestones/employee/${m.owner_id}`}>{m.owner_name ?? m.owner_id}</Link>
              ) : (
                "—"
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Department">
              {m.department ? (
                <Link to={`/milestones/department/${m.department}`}>
                  {m.department_name ?? m.department}
                </Link>
              ) : (
                "—"
              )}
            </Descriptions.Item>
            <Descriptions.Item label="Team">{m.team_name ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="Manager">{m.manager_name ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="Category">{m.category}</Descriptions.Item>
            <Descriptions.Item label="Priority">
              <PriorityTag priority={m.priority} />
            </Descriptions.Item>
            <Descriptions.Item label="Status">
              <StatusTag status={m.status} />
            </Descriptions.Item>
            <Descriptions.Item label="Start Date">{m.start_date ?? "—"}</Descriptions.Item>
            <Descriptions.Item label="Due Date">
              <span className={m.overdue ? "text-red-600 font-medium" : undefined}>
                {m.due_date ?? "—"}
                {m.overdue ? ` (${m.overdue_days}d overdue)` : ""}
              </span>
            </Descriptions.Item>
            <Descriptions.Item label="Health">
              <HealthBadge health={m.health} actual={m.actual_pct} planned={m.planned_pct} />
            </Descriptions.Item>
          </Descriptions>
        </Card>
      </Col>

      <Col xs={24} xl={14}>
        <div className="flex flex-col gap-4">
          <Card title="Progress Overview" size="small" bordered={false}>
            <Progress percent={Math.round(m.progress_pct)} strokeColor="#157f52" />
            <Row gutter={[16, 8]} className="mt-2">
              <Col xs={8}>
                <Statistic
                  title="Planned Progress"
                  value={m.planned_pct}
                  suffix="%"
                  valueStyle={{ fontSize: 18 }}
                />
              </Col>
              <Col xs={8}>
                <Statistic
                  title="Actual Progress"
                  value={m.actual_pct}
                  suffix="%"
                  valueStyle={{ fontSize: 18, color: "#157f52" }}
                />
              </Col>
              <Col xs={8}>
                <Statistic
                  title="Delayed Progress"
                  value={m.delayed_pct}
                  suffix="%"
                  valueStyle={{ fontSize: 18, color: m.delayed_pct > 0 ? "#cf1322" : undefined }}
                />
              </Col>
            </Row>
            <Text type="secondary" className="text-[11px]">
              Actual is the weightage-weighted completion of this milestone's tasks, derived from
              approved Daily Success entries.
            </Text>
          </Card>
          <ProgressTrendChart title="Progress Trend" points={data.trend?.points ?? []} height={220} />
        </div>
      </Col>

      <Col xs={24} xl={12}>
        <Card title="Description" size="small" bordered={false} className="h-full">
          <Paragraph className="!mb-0">{m.description || "No description provided."}</Paragraph>
        </Card>
      </Col>

      <Col xs={24} xl={12}>
        <Card title="Completion Criteria" size="small" bordered={false} className="h-full">
          {m.completion_criteria?.length ? (
            <div className="flex flex-col gap-2">
              {m.completion_criteria.map((c) => (
                <Checkbox key={c.label} checked={c.done} disabled>
                  <span className={c.done ? "" : "opacity-70"}>{c.label}</span>
                </Checkbox>
              ))}
            </div>
          ) : (
            <Text type="secondary">No completion criteria defined.</Text>
          )}
        </Card>
      </Col>
    </Row>
  );
}
