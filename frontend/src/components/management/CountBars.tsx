import { Flex, Progress, Typography } from "antd";

const { Text } = Typography;

export interface CountRow {
  label: string;
  count: number;
  pct: number;
}

export default function CountBars({ rows }: { rows: CountRow[] }) {
  return (
    <Flex vertical gap={10}>
      {rows.map((r) => (
        <div key={r.label}>
          <Flex justify="space-between" className="mb-1">
            <Text className="text-xs">{r.label}</Text>
            <Text type="secondary" className="text-xs">
              {r.count} ({r.pct}%)
            </Text>
          </Flex>
          <Progress percent={r.pct} showInfo={false} strokeColor="#157f52" size="small" />
        </div>
      ))}
    </Flex>
  );
}
