import { Card, Empty } from "antd";

export default function ComingSoonTab({ title }: { title: string }) {
  return (
    <Card size="small" bordered={false} className="shadow-sm">
      <Empty description={`${title} is coming soon.`} />
    </Card>
  );
}
