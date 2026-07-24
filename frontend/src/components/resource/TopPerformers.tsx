import { Card, Rate, Table, Tooltip, Typography } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";
import type { ResourceTopPerformer } from "../../lib/api";

const { Text } = Typography;

export default function TopPerformers({ rows }: { rows: ResourceTopPerformer[] }) {
  return (
    <Card size="small" bordered={false} className="h-full shadow-sm" title="Top Performers">
      <Table<ResourceTopPerformer>
        dataSource={rows}
        rowKey="user_id"
        size="small"
        pagination={false}
        scroll={{ x: true }}
        columns={[
          { title: "Employee", dataIndex: "name", key: "name" },
          {
            title: "Task Completion",
            dataIndex: "completion_pct",
            key: "completion_pct",
            render: (v) => <Text className="text-io-600 font-medium">{v}%</Text>,
          },
          { title: "SLA Compliance", dataIndex: "sla_pct", key: "sla_pct", render: (v) => `${v}%` },
          {
            title: (
              <span>
                Rating{" "}
                <Tooltip title="Derived from completion rate and SLA compliance — not a performance review score.">
                  <InfoCircleOutlined className="text-gray-400" />
                </Tooltip>
              </span>
            ),
            dataIndex: "rating",
            key: "rating",
            render: (v) => <Rate disabled allowHalf value={v} className="text-sm" />,
          },
        ]}
      />
    </Card>
  );
}
