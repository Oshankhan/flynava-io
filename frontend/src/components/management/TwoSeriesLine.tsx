import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export default function TwoSeriesLine({
  points,
  aKey,
  aName,
  aColor,
  bKey,
  bName,
  bColor,
  height = 220,
}: {
  points: Record<string, string | number>[];
  aKey: string;
  aName: string;
  aColor: string;
  bKey: string;
  bName: string;
  bColor: string;
  height?: number;
}) {
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <LineChart data={points} margin={{ left: 4, right: 8, top: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#dfeee6" />
          <XAxis dataKey="t" tick={{ fontSize: 10 }} minTickGap={24} />
          <YAxis tick={{ fontSize: 10 }} width={40} allowDecimals={false} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey={aKey} name={aName} stroke={aColor} strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey={bKey} name={bName} stroke={bColor} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
