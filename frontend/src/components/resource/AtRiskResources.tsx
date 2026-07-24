import { Avatar, Button, Card, Flex, message, Progress, Typography } from "antd";
import { UserOutlined } from "@ant-design/icons";
import type { ResourceAtRisk } from "../../lib/api";
import { ragHex, PERSON_STATUS_RAG } from "./statusColors";

const { Text } = Typography;

export default function AtRiskResources({ rows }: { rows: ResourceAtRisk[] }) {
  return (
    <Card size="small" bordered={false} className="h-full shadow-sm" title="At Risk Resources">
      <Flex vertical gap={12}>
        {rows.map((r) => (
          <div key={r.user_id} className="rounded-lg border border-gray-100 dark:border-white/10 p-3">
            <Flex justify="space-between" align="start" gap={8} wrap>
              <Flex gap={8} align="center">
                <Avatar icon={<UserOutlined />} size="small" />
                <div>
                  <Text strong className="text-[13px]">{r.name}</Text>
                  <div>
                    <Text type="secondary" className="text-xs">{r.designation ?? "—"}</Text>
                  </div>
                </div>
              </Flex>
              <Text className="text-xs">
                Tasks {r.tasks} · Pending {r.pending} · Overdue {r.overdue}
              </Text>
            </Flex>

            <Progress
              className="mt-2"
              percent={Math.min(r.workload_pct, 100)}
              size="small"
              format={() => `${r.workload_pct}%`}
              strokeColor={ragHex(PERSON_STATUS_RAG[r.status])}
            />

            <Flex justify="space-between" align="center" className="mt-2" wrap gap={8}>
              <Text type="secondary" className="text-xs">Recommendation: {r.recommendation}</Text>
              <Button
                size="small"
                type={r.reassign_count > 0 ? "primary" : "default"}
                onClick={() =>
                  message.info(
                    "Task reassignment isn't wired up yet — this is a recommendation only."
                  )
                }
              >
                {r.reassign_count > 0 ? "Reassign Work" : "View Plan"}
              </Button>
            </Flex>
          </div>
        ))}
      </Flex>
    </Card>
  );
}
