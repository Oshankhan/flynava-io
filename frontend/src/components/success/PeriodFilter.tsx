import { Button, DatePicker, Flex, Segmented, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { useAsyncAction } from "../../lib/useAsyncAction";

const { Text } = Typography;

export interface SuccessPeriodValue {
  mode: "current" | "last" | "custom";
  month?: string;
  from?: string;
  to?: string;
}

export function periodToParams(
  p: SuccessPeriodValue
): { month?: string; from?: string; to?: string } {
  if (p.mode === "current") return {};
  if (p.mode === "last") return { month: dayjs().subtract(1, "month").format("YYYY-MM") };
  if (p.from && p.to) return { from: p.from, to: p.to };
  if (p.month) return { month: p.month };
  return {};
}

export default function PeriodFilter({
  period,
  onChange,
  lastUpdated,
  onRefresh,
  dailyCustomRange = false,
}: {
  period: SuccessPeriodValue;
  onChange: (v: SuccessPeriodValue) => void;
  lastUpdated?: string | null;
  onRefresh: () => Promise<void>;
  dailyCustomRange?: boolean;
}) {
  const [run, loading] = useAsyncAction(onRefresh);

  return (
    <Flex wrap align="center" justify="space-between" gap={12}>
      <Flex align="center" gap={10} wrap>
        <Segmented
          value={period.mode}
          onChange={(mode) => {
            if (mode === "custom") {
              onChange({ mode: "custom", month: dayjs().format("YYYY-MM") });
            } else {
              onChange({ mode: mode as "current" | "last" });
            }
          }}
          options={[
            { label: "Current Month", value: "current" },
            { label: "Last Month", value: "last" },
            { label: "Custom Range", value: "custom" },
          ]}
        />
        {period.mode === "custom" &&
          (dailyCustomRange ? (
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
          ) : (
            <DatePicker
              picker="month"
              value={period.month ? dayjs(period.month) : null}
              onChange={(date) => {
                if (date) onChange({ mode: "custom", month: date.format("YYYY-MM") });
              }}
            />
          ))}
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
