import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Dot,
} from "recharts";
import type { Vo2MaxLog } from "../../types";

interface Props {
  data: Vo2MaxLog[];
  goal: number;
}

function formatDate(iso: string): string {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomDot(props: any) {
  const { cx, cy, payload } = props;
  return (
    <g>
      <circle cx={cx} cy={cy} r={4} fill="#3b82f6" stroke="#fff" strokeWidth={2} />
      <text x={cx} y={cy - 10} textAnchor="middle" fontSize={10} fill="#6b7280">
        {payload.vo2max.toFixed(1)}
      </text>
    </g>
  );
}

export default function Vo2TrendCard({ data, goal }: Props) {
  const latest = data.length > 0 ? data[data.length - 1] : null;
  const baseline = data.length > 0 ? data[0] : null;
  const change = latest && baseline ? latest.vo2max - baseline.vo2max : null;

  // Determine y-axis domain with some padding
  const values = data.map((d) => d.vo2max);
  const minVal = Math.min(...values, goal) - 2;
  const maxVal = Math.max(...values, goal) + 2;

  const chartData = data.map((d) => ({ date: d.date, vo2max: d.vo2max }));

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">VO₂ Max Trend</h3>
          <p className="text-xs text-gray-400 mt-0.5">Aerobic fitness over time</p>
        </div>
        {latest && (
          <div className="text-right">
            <span className="text-2xl font-bold text-gray-900 dark:text-white">
              {latest.vo2max.toFixed(1)}
            </span>
            <p className="text-xs text-gray-400">
              Goal: <span className="text-green-500 font-medium">{goal}+</span>
            </p>
          </div>
        )}
      </div>

      {/* Stats row */}
      {latest && baseline && (
        <div className="flex gap-4 mb-4 text-sm">
          <div>
            <p className="text-xs text-gray-400">Baseline</p>
            <p className="font-semibold text-gray-700 dark:text-gray-300">{baseline.vo2max.toFixed(1)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Current</p>
            <p className="font-semibold text-gray-700 dark:text-gray-300">{latest.vo2max.toFixed(1)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-400">Change</p>
            <p className={`font-semibold ${change !== null && change >= 0 ? "text-green-600" : "text-red-500"}`}>
              {change !== null ? `${change >= 0 ? "+" : ""}${change.toFixed(1)}` : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-400">To Goal</p>
            <p className="font-semibold text-blue-600">
              +{(goal - (latest?.vo2max ?? 0)).toFixed(1)}
            </p>
          </div>
        </div>
      )}

      {data.length < 2 ? (
        <div className="h-32 flex items-center justify-center text-sm text-gray-400">
          {data.length === 0
            ? "No data yet — sync Garmin to start tracking"
            : "One reading so far — more data needed for trend"}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={chartData} margin={{ top: 16, right: 8, left: -20, bottom: 0 }}>
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              tick={{ fontSize: 10, fill: "#9ca3af" }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[minVal, maxVal]}
              tick={{ fontSize: 10, fill: "#9ca3af" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              formatter={(v: number) => [v.toFixed(1), "VO₂ Max"]}
              labelFormatter={formatDate}
              contentStyle={{
                fontSize: 12,
                border: "1px solid #e5e7eb",
                borderRadius: 8,
                backgroundColor: "white",
              }}
            />
            <ReferenceLine
              y={goal}
              stroke="#22c55e"
              strokeDasharray="4 3"
              label={{ value: `Goal ${goal}`, position: "right", fontSize: 10, fill: "#22c55e" }}
            />
            <Line
              type="monotone"
              dataKey="vo2max"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={<CustomDot />}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      <p className="text-xs text-gray-400 mt-2">
        {data.length > 0
          ? `${data.length} reading${data.length > 1 ? "s" : ""} · last from ${latest?.source ?? "garmin"} on ${formatDate(latest!.date)}`
          : "Sync Garmin to fetch VO₂ max readings"}
      </p>
    </div>
  );
}
