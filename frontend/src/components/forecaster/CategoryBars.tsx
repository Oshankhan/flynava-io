import { Flex, Progress, Typography } from "antd";
import { formatINR } from "../../lib/format";

const { Text } = Typography;

export interface CategoryRow {
  category: string;
  amount: number;
}

export default function CategoryBars({ rows }: { rows: CategoryRow[] }) {
  const total = rows.reduce((s, r) => s + r.amount, 0);
  return (
    <Flex vertical gap={10}>
      {rows.map((r) => {
        const pct = total ? Math.round((r.amount / total) * 100) : 0;
        return (
          <div key={r.category}>
            <Flex justify="space-between" className="mb-1">
              <Text className="text-xs">{r.category}</Text>
              <Text type="secondary" className="text-xs">
                {formatINR(r.amount)} ({pct}%)
              </Text>
            </Flex>
            <Progress percent={pct} showInfo={false} strokeColor="#157f52" size="small" />
          </div>
        );
      })}
    </Flex>
  );
}
