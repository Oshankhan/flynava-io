import { Card, Tag, Timeline, Typography } from "antd";
import dayjs from "dayjs";
import type { CentralPayload } from "../../lib/api";

const { Text } = Typography;

type Milestone = CentralPayload["tables"]["timeline"][number];

const STATUS_COLOR: Record<Milestone["status"], string> = {
  Completed: "success",
  "In Progress": "processing",
  Upcoming: "default",
};
const DOT_COLOR: Record<Milestone["status"], string> = {
  Completed: "green",
  "In Progress": "blue",
  Upcoming: "gray",
};

export default function TimelineTracker({ items }: { items: Milestone[] }) {
  return (
    <Card title="Timeline Tracker" size="small" bordered={false} className="h-full">
      <Timeline
        items={items.map((m) => ({
          color: DOT_COLOR[m.status],
          children: (
            <div className="pb-1">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-sm">{m.name}</span>
                <Tag color={STATUS_COLOR[m.status]} className="m-0">
                  {m.status}
                </Tag>
              </div>
              <Text type="secondary" className="text-xs block">
                {m.sublabel}
              </Text>
              <Text type="secondary" className="text-[11px]">
                {dayjs(m.date).format("DD MMM YYYY")}
              </Text>
            </div>
          ),
        }))}
      />
    </Card>
  );
}
