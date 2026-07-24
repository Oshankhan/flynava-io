import { Card, Progress, Table, Tag } from "antd";
import type { ResourcePersonRow } from "../../lib/api";
import { PERSON_STATUS_LABEL, PERSON_STATUS_RAG, ragHex, ragTagColor } from "./statusColors";

export default function WorkloadHeatmap({ rows }: { rows: ResourcePersonRow[] }) {
  return (
    <Card size="small" bordered={false} className="h-full shadow-sm" title="Resource Heatmap (By Workload)">
      <Table<ResourcePersonRow>
        dataSource={rows}
        rowKey="user_id"
        size="small"
        pagination={{ pageSize: 8 }}
        scroll={{ x: true }}
        columns={[
          { title: "Employee", dataIndex: "name", key: "name" },
          { title: "Role", dataIndex: "designation", key: "designation", render: (d) => d ?? "—" },
          {
            title: "Workload",
            key: "workload",
            width: 160,
            render: (_, r) => (
              <Progress
                percent={Math.min(r.workload_pct, 100)}
                size="small"
                format={() => `${r.workload_pct}%`}
                strokeColor={ragHex(PERSON_STATUS_RAG[r.status])}
              />
            ),
          },
          { title: "Tasks", dataIndex: "tasks", key: "tasks" },
          {
            title: "Completion",
            dataIndex: "completion_pct",
            key: "completion_pct",
            render: (v) => `${v}%`,
          },
          {
            title: "Status",
            key: "status",
            render: (_, r) => (
              <Tag color={ragTagColor(PERSON_STATUS_RAG[r.status])}>
                {PERSON_STATUS_LABEL[r.status]}
              </Tag>
            ),
          },
        ]}
      />
      <div className="mt-2 flex flex-wrap gap-4 text-xs text-gray-500 dark:text-gray-400">
        <span>🔴 &gt;100% Overloaded</span>
        <span>🟢 70%–100% Optimal</span>
        <span>🟠 &lt;70% Underutilized</span>
      </div>
    </Card>
  );
}
