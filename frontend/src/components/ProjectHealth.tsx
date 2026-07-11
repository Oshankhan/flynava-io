import { Card, Progress, Table } from "antd";
import type { ProjectRow } from "../lib/api";
import { RAG } from "../lib/brand";
import RagBadge from "./RagBadge";

export default function ProjectHealth({ projects }: { projects: ProjectRow[] }) {
  if (!projects.length) return null;
  return (
    <Card title="Project Health" size="small" bordered={false}>
      <Table<ProjectRow>
        dataSource={projects}
        rowKey="project_id"
        pagination={false}
        size="small"
        columns={[
          { title: "Project", dataIndex: "name", key: "name" },
          {
            title: "Progress",
            dataIndex: "progress",
            key: "progress",
            render: (v: number, r) => (
              <Progress
                percent={Math.min(v, 100)}
                size="small"
                strokeColor={RAG[r.rag].hex}
                style={{ maxWidth: 180 }}
              />
            ),
          },
          {
            title: "Expected",
            dataIndex: "expected_progress",
            key: "expected",
            render: (v: number | null) => (v != null ? `${v}%` : "—"),
          },
          {
            title: "Status",
            dataIndex: "rag",
            key: "rag",
            render: (_: unknown, r) => <RagBadge rag={r.rag} />,
          },
        ]}
      />
    </Card>
  );
}
