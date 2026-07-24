import { Card, Typography } from "antd";
import { BulbOutlined, WarningOutlined, ThunderboltOutlined, CheckCircleOutlined } from "@ant-design/icons";
import type { ResourceInsight } from "../../lib/api";
import { openInayaWithAnswer } from "../InayaChat";

const { Text } = Typography;

const SEVERITY_ICON: Record<ResourceInsight["severity"], React.ReactNode> = {
  high: <WarningOutlined className="text-red-500" />,
  medium: <ThunderboltOutlined className="text-amber-500" />,
  low: <CheckCircleOutlined className="text-io-600" />,
};

export default function ResourceInsights({ insights }: { insights: ResourceInsight[] }) {
  function open(insight: ResourceInsight) {
    openInayaWithAnswer(insight.text, {
      answer: insight.text,
      reason: "Derived from current team workload, task, and project data on the Resource Dashboard.",
      evidence: [],
      recommended_action: "Review the Resource Dashboard's capacity and heatmap views for detail.",
      confidence: "Medium",
      last_updated: new Date().toISOString(),
    });
  }

  return (
    <Card size="small" bordered={false} className="shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <BulbOutlined className="text-io-600" />
        <Text strong className="text-[13px]">AI Resource Insights</Text>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3">
        {insights?.map((insight, i) => (
          <button
            key={i}
            type="button"
            onClick={() => open(insight)}
            className="text-left rounded-lg border border-gray-100 dark:border-white/10 p-3 hover:border-io-600 transition-colors"
          >
            <div className="text-base mb-1">{SEVERITY_ICON[insight.severity]}</div>
            <Text className="text-xs leading-snug">{insight.text}</Text>
          </button>
        ))}
      </div>
    </Card>
  );
}
