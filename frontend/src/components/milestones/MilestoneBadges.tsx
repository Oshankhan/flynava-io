import { Progress, Tag, Tooltip, Typography } from "antd";
import type { MilestoneHealth, MilestoneStatus } from "../../lib/api";

const { Text } = Typography;

const HEALTH: Record<MilestoneHealth, { label: string; color: string }> = {
  good: { label: "Good", color: "success" },
  needs_attention: { label: "Needs Attention", color: "warning" },
  at_risk: { label: "At Risk", color: "error" },
};

const STATUS: Record<MilestoneStatus, { label: string; color: string }> = {
  not_started: { label: "Not Started", color: "default" },
  pending: { label: "Pending", color: "default" },
  in_progress: { label: "In Progress", color: "processing" },
  pending_review: { label: "Pending Review", color: "gold" },
  completed: { label: "Completed", color: "success" },
  blocked: { label: "Blocked", color: "error" },
};

const PRIORITY: Record<string, string> = {
  High: "red",
  Medium: "orange",
  Low: "green",
};

const RISK: Record<string, string> = { High: "red", Medium: "orange", Low: "green" };

/** Health is progress vs time elapsed, so the tooltip spells the comparison
 * out — a bare "At Risk" chip next to a healthy-looking 70% otherwise reads
 * as a bug. */
export function HealthBadge({
  health,
  actual,
  planned,
}: {
  health: MilestoneHealth;
  actual?: number;
  planned?: number;
}) {
  const meta = HEALTH[health] ?? HEALTH.good;
  const chip = <Tag color={meta.color}>{meta.label}</Tag>;
  if (actual == null || planned == null) return chip;
  return (
    <Tooltip title={`${actual}% done vs ${planned}% of the schedule elapsed`}>{chip}</Tooltip>
  );
}

export function StatusTag({ status }: { status: MilestoneStatus }) {
  const meta = STATUS[status] ?? STATUS.pending;
  return <Tag color={meta.color}>{meta.label}</Tag>;
}

export function PriorityTag({ priority }: { priority?: string | null }) {
  if (!priority) return <Tag>—</Tag>;
  return <Tag color={PRIORITY[priority] ?? "default"}>{priority}</Tag>;
}

export function RiskTag({ risk }: { risk?: string | null }) {
  if (!risk) return <Tag>—</Tag>;
  return <Tag color={RISK[risk] ?? "default"}>{risk}</Tag>;
}

export function ProgressCell({
  value,
  status,
}: {
  value?: number | null;
  status?: MilestoneStatus;
}) {
  const pct = Math.round(value ?? 0);
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <Progress
        percent={pct}
        showInfo={false}
        size="small"
        status={status === "blocked" ? "exception" : pct >= 100 ? "success" : "active"}
        className="flex-1 !mb-0"
      />
      <Text className="text-xs tabular-nums w-9 text-right">{pct}%</Text>
    </div>
  );
}

export function DueCell({
  due,
  overdue,
  overdueDays,
}: {
  due?: string | null;
  overdue?: boolean;
  overdueDays?: number;
}) {
  if (!due) return <Text type="secondary">—</Text>;
  if (!overdue) return <span className="whitespace-nowrap">{due}</span>;
  return (
    <Tooltip title={`${overdueDays ?? 0} day(s) overdue`}>
      <span className="whitespace-nowrap text-red-600 font-medium">{due}</span>
    </Tooltip>
  );
}

export const HEALTH_OPTIONS = (Object.keys(HEALTH) as MilestoneHealth[]).map((k) => ({
  value: k,
  label: HEALTH[k].label,
}));

export const STATUS_OPTIONS = (Object.keys(STATUS) as MilestoneStatus[]).map((k) => ({
  value: k,
  label: STATUS[k].label,
}));
