import { Card, Flex, Typography } from "antd";
import { ArrowDownOutlined, ArrowUpOutlined } from "@ant-design/icons";
import type { Kpi } from "../lib/api";
import { formatValue } from "../lib/format";
import RagBadge from "./RagBadge";

const { Text } = Typography;

export default function KpiCard({ kpi }: { kpi: Kpi }) {
  const change = kpi.change_pct;
  const good = change != null && (change > 0) === (kpi.direction === "higher");

  return (
    <Card size="small" bordered={false} className="h-full shadow-sm">
      <Flex justify="space-between" align="flex-start" gap={8}>
        <Text type="secondary" className="text-[13px] font-medium">
          {kpi.name}
        </Text>
        <RagBadge rag={kpi.rag} />
      </Flex>
      <Flex align="baseline" gap={8} className="mt-1.5">
        <span className="text-3xl font-bold text-io-900">
          {formatValue(kpi.value, kpi.unit)}
        </span>
        {change != null && change !== 0 && (
          <span
            data-testid="kpi-change"
            className={`text-[13px] font-semibold ${good ? "text-io-600" : "text-red-600"}`}
          >
            {change > 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {Math.abs(change)}%
          </span>
        )}
      </Flex>
      {kpi.target != null && (
        <Text type="secondary" className="text-xs">
          Target {formatValue(kpi.target, kpi.unit)} ·{" "}
          {kpi.direction === "higher" ? "higher is better" : "lower is better"}
        </Text>
      )}
    </Card>
  );
}
