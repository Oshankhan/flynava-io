import { Card, Progress, Table, Tag } from "antd";
import type { ResourceProjectStatus } from "../../lib/api";
import { PROJECT_HEALTH_LABEL, PROJECT_HEALTH_RAG, ragTagColor } from "./statusColors";

export default function ProjectResourceStatusCard({ rows }: { rows: ResourceProjectStatus[] }) {
  return (
    <Card size="small" bordered={false} className="h-full shadow-sm" title="Project Resource Status">
      <Table<ResourceProjectStatus>
        dataSource={rows}
        rowKey="project_id"
        size="small"
        pagination={false}
        scroll={{ x: true }}
        columns={[
          { title: "Project", dataIndex: "name", key: "name" },
          {
            title: "Progress",
            key: "progress",
            width: 140,
            render: (_, r) => (
              <Progress percent={r.progress} size="small" format={() => `${r.progress}%`} />
            ),
          },
          { title: "Resources", dataIndex: "resources", key: "resources" },
          {
            title: "Health",
            key: "health",
            render: (_, r) => (
              <Tag color={ragTagColor(PROJECT_HEALTH_RAG[r.health])}>
                {PROJECT_HEALTH_LABEL[r.health]}
              </Tag>
            ),
          },
          {
            title: "Completion Date",
            dataIndex: "due_date",
            key: "due_date",
            render: (v) => v ?? "—",
          },
        ]}
      />
    </Card>
  );
}
