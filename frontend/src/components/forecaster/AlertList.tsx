import { Card, Flex, Typography } from "antd";
import { ExclamationCircleFilled, InfoCircleFilled, WarningFilled } from "@ant-design/icons";
import type { ForecasterAlert } from "../../lib/api";

const { Text } = Typography;

const SEVERITY_ICON: Record<ForecasterAlert["severity"], React.ReactNode> = {
  high: <WarningFilled className="text-red-500" />,
  medium: <ExclamationCircleFilled className="text-amber-500" />,
  low: <InfoCircleFilled className="text-blue-500" />,
};

export default function AlertList({ alerts }: { alerts: ForecasterAlert[] }) {
  return (
    <Card title="Executive Alerts" size="small" bordered={false} className="h-full">
      <Flex vertical gap={10}>
        {alerts.length === 0 && (
          <Text type="secondary" className="text-xs">No alerts for this period.</Text>
        )}
        {alerts.map((a) => (
          <Flex key={a.title} align="flex-start" gap={8}>
            <span className="mt-0.5 text-xs shrink-0">{SEVERITY_ICON[a.severity]}</span>
            <div className="min-w-0">
              <Text strong className="text-xs block">{a.title}</Text>
              <Text type="secondary" className="text-xs leading-snug">{a.detail}</Text>
            </div>
          </Flex>
        ))}
      </Flex>
    </Card>
  );
}
