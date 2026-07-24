import { Card, Progress, Table, Tag } from "antd";
import type { ResourceTeamCapacity } from "../../lib/api";
import { ragHex, ragTagColor, TEAM_STATUS_LABEL, TEAM_STATUS_RAG } from "./statusColors";

export default function TeamCapacityCard({ rows }: { rows: ResourceTeamCapacity[] }) {
  return (
    <Card size="small" bordered={false} className="h-full shadow-sm" title="Team Capacity Overview">
      <Table<ResourceTeamCapacity>
        dataSource={rows}
        rowKey="team_id"
        size="small"
        pagination={false}
        scroll={{ x: true }}
        columns={[
          { title: "Team", dataIndex: "name", key: "name" },
          {
            title: "Utilization",
            key: "utilization",
            width: 160,
            render: (_, r) => (
              <Progress
                percent={Math.min(r.utilization_pct, 100)}
                size="small"
                showInfo
                format={() => `${r.utilization_pct}%`}
                strokeColor={ragHex(TEAM_STATUS_RAG[r.status])}
              />
            ),
          },
          {
            title: "Status",
            key: "status",
            render: (_, r) => (
              <Tag color={ragTagColor(TEAM_STATUS_RAG[r.status])}>{TEAM_STATUS_LABEL[r.status]}</Tag>
            ),
          },
          { title: "Members", dataIndex: "member_count", key: "member_count" },
          { title: "Tasks", dataIndex: "tasks", key: "tasks" },
        ]}
      />
    </Card>
  );
}
