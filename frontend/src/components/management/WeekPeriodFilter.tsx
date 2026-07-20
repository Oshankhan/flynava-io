import { Button, DatePicker, Flex, Segmented, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { useAsyncAction } from "../../lib/useAsyncAction";

const { Text } = Typography;

export interface BugsPeriodValue {
  mode: "week" | "month" | "3m" | "custom";
  from?: string;
  to?: string;
}

export function periodToQuery(p: BugsPeriodValue): { preset?: string; from?: string; to?: string } {
  if (p.mode === "custom" && p.from && p.to) return { from: p.from, to: p.to };
  return { preset: p.mode === "custom" ? "month" : p.mode };
}

export default function WeekPeriodFilter({
  period,
  onChange,
  lastUpdated,
  onRefresh,
}: {
  period: BugsPeriodValue;
  onChange: (v: BugsPeriodValue) => void;
  lastUpdated?: string | null;
  onRefresh: () => Promise<void>;
}) {
  const [run, loading] = useAsyncAction(onRefresh);

  return (
    <Flex wrap align="center" justify="space-between" gap={12}>
      <Flex align="center" gap={10} wrap>
        <Segmented
          value={period.mode}
          onChange={(mode) => {
            if (mode === "custom") {
              onChange({
                mode: "custom",
                from: dayjs().subtract(29, "day").format("YYYY-MM-DD"),
                to: dayjs().format("YYYY-MM-DD"),
              });
            } else {
              onChange({ mode: mode as "week" | "month" | "3m" });
            }
          }}
          options={[
            { label: "Current Week", value: "week" },
            { label: "Current Month", value: "month" },
            { label: "Last 3 Months", value: "3m" },
            { label: "Custom Range", value: "custom" },
          ]}
        />
        {period.mode === "custom" && (
          <DatePicker.RangePicker
            value={period.from && period.to ? [dayjs(period.from), dayjs(period.to)] : null}
            onChange={(dates) => {
              if (dates?.[0] && dates?.[1])
                onChange({
                  mode: "custom",
                  from: dates[0].format("YYYY-MM-DD"),
                  to: dates[1].format("YYYY-MM-DD"),
                });
            }}
          />
        )}
      </Flex>
      <Flex align="center" gap={10}>
        {lastUpdated && (
          <Text type="secondary" className="text-xs hidden sm:inline">
            Last updated: {dayjs(lastUpdated).format("DD MMM YYYY, hh:mm A")}
          </Text>
        )}
        <Button icon={<ReloadOutlined />} loading={loading} onClick={() => run()}>
          Refresh
        </Button>
      </Flex>
    </Flex>
  );
}
