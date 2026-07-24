import { Card, Tag, Tooltip, Typography } from "antd";
import { InfoCircleOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import type { ResourceLifecycle } from "../../lib/api";

const { Text } = Typography;

const SOURCE_TAG: Record<ResourceLifecycle["source"], { color: string; label: string }> = {
  live: { color: "success", label: "Live" },
  partial: { color: "processing", label: "Partial" },
  demo: { color: "default", label: "Demo" },
};

function DeptStrip({ dept }: { dept: ResourceLifecycle }) {
  const tag = SOURCE_TAG[dept.source];
  return (
    <Card size="small" bordered={false} className="h-full shadow-sm">
      <div className="flex items-center justify-between gap-2 mb-2">
        <Text strong className="text-[13px]">{dept.department}</Text>
        <Tag color={tag.color} className="me-0">
          {tag.label}
          {dept.note && (
            <Tooltip title={dept.note}>
              <InfoCircleOutlined className="ms-1" />
            </Tooltip>
          )}
        </Tag>
      </div>

      <div className="flex items-stretch gap-1 overflow-x-auto pb-1">
        {dept.stages?.map((s, i) => (
          <div key={s.name} className="flex items-center shrink-0">
            <div className="flex flex-col items-center min-w-[64px]">
              <div className="w-9 h-9 rounded-full bg-io-600/10 text-io-700 dark:text-io-300 flex items-center justify-center font-semibold text-sm">
                {s.count}
              </div>
              <Text type="secondary" className="text-[10px] text-center mt-1 leading-tight">
                {s.name}
              </Text>
            </div>
            {i < (dept.stages?.length ?? 0) - 1 && (
              <span className="text-gray-300 dark:text-gray-600 mx-1">→</span>
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between mt-2">
        <Text type="secondary" className="text-[11px]">
          Avg Cycle Time: {dept.avg_cycle_days != null ? `${dept.avg_cycle_days} Days` : "—"}
        </Text>
        <Link to="/resource/lifecycle" className="text-[11px] text-io-600 hover:underline">
          View Details →
        </Link>
      </div>
    </Card>
  );
}

export default function WorkLifecycleOverview({ departments }: { departments: ResourceLifecycle[] }) {
  return (
    <Card size="small" bordered={false} className="shadow-sm" title="Work Lifecycle Overview (Department Wise)">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3">
        {departments?.map((d) => (
          <DeptStrip key={d.department} dept={d} />
        ))}
      </div>
    </Card>
  );
}
