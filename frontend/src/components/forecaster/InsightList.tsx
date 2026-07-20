import { Card, Flex, Typography } from "antd";
import { CheckCircleFilled } from "@ant-design/icons";

const { Text } = Typography;

export default function InsightList({ items }: { items: string[] }) {
  return (
    <Card title="AI Executive Insights" size="small" bordered={false} className="h-full">
      <Flex vertical gap={10}>
        {items.length === 0 && (
          <Text type="secondary" className="text-xs">No insights available for this period.</Text>
        )}
        {items.map((text) => (
          <Flex key={text} align="flex-start" gap={8}>
            <CheckCircleFilled className="text-io-600 mt-0.5 text-xs shrink-0" />
            <Text className="text-xs leading-snug">{text}</Text>
          </Flex>
        ))}
      </Flex>
    </Card>
  );
}
