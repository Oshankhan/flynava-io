import type { ReactNode } from "react";
import { Card, Flex, Typography } from "antd";
import { ArrowDownOutlined, ArrowRightOutlined, ArrowUpOutlined } from "@ant-design/icons";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { Link } from "react-router-dom";
import type { SeriesPoint } from "../../lib/api";
import { formatSuccessValue } from "../../lib/format";
import { BRAND } from "../../lib/brand";

const { Text } = Typography;

export default function SummaryPanel({
  title,
  value,
  unit,
  momPct,
  trend,
  link,
  children,
}: {
  title: string;
  value?: number | null;
  unit?: string;
  momPct?: number | null;
  trend?: SeriesPoint[];
  link: string;
  children?: ReactNode;
}) {
  return (
    <Card size="small" bordered={false} className="h-full shadow-sm">
      <Flex justify="space-between" align="center" className="mb-2">
        <Text strong className="text-sm">{title}</Text>
        <Link to={link} className="text-xs text-io-600 inline-flex items-center gap-1">
          View Details <ArrowRightOutlined className="text-[10px]" />
        </Link>
      </Flex>

      {value !== undefined && (
        <Flex align="baseline" gap={8} wrap className="mb-2">
          <span className="text-xl font-bold text-io-900 leading-none">
            {formatSuccessValue(value, unit ?? "inr")}
          </span>
          {momPct != null && momPct !== 0 && (
            <span className={`text-xs font-semibold ${momPct > 0 ? "text-io-600" : "text-red-600"}`}>
              {momPct > 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />} {Math.abs(momPct)}%
            </span>
          )}
        </Flex>
      )}

      {trend && trend.length >= 3 && (
        <div className="w-full h-12 -mx-1 mb-2">
          <ResponsiveContainer>
            <AreaChart data={trend} margin={{ top: 2, bottom: 0, left: 0, right: 0 }}>
              <defs>
                <linearGradient id="forecaster-panel-spark" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={BRAND.primary} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={BRAND.primary} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="v"
                stroke={BRAND.primary}
                strokeWidth={2}
                fill="url(#forecaster-panel-spark)"
                isAnimationActive={false}
                dot={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {children}
    </Card>
  );
}
