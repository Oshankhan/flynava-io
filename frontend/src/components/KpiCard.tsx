import { Card, Flex, Typography } from "antd";
import { ArrowDownOutlined, ArrowUpOutlined } from "@ant-design/icons";
import type { Kpi } from "../lib/api";
import { formatValue } from "../lib/format";
import { BRAND } from "../lib/brand";
import RagBadge from "./RagBadge";

const { Text } = Typography;

export default function KpiCard({ kpi }: { kpi: Kpi }) {
  const change = kpi.change_pct;
  const good = change != null && (change > 0) === (kpi.direction === "higher");

  return (
    <Card size="small" bordered={false} style={{ height: "100%", boxShadow: "0 1px 2px rgba(0,0,0,0.06)" }}>
      <Flex justify="space-between" align="flex-start" gap={8}>
        <Text type="secondary" style={{ fontSize: 13, fontWeight: 500 }}>
          {kpi.name}
        </Text>
        <RagBadge rag={kpi.rag} />
      </Flex>
      <Flex align="baseline" gap={8} style={{ marginTop: 6 }}>
        <span style={{ fontSize: 30, fontWeight: 700, color: BRAND.primaryStrong }}>
          {formatValue(kpi.value, kpi.unit)}
        </span>
        {change != null && change !== 0 && (
          <span
            data-testid="kpi-change"
            style={{ fontSize: 13, fontWeight: 600, color: good ? BRAND.primary : "#cf1322" }}
          >
            {change > 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {Math.abs(change)}%
          </span>
        )}
      </Flex>
      {kpi.target != null && (
        <Text type="secondary" style={{ fontSize: 12 }}>
          Target {formatValue(kpi.target, kpi.unit)} ·{" "}
          {kpi.direction === "higher" ? "higher is better" : "lower is better"}
        </Text>
      )}
    </Card>
  );
}
