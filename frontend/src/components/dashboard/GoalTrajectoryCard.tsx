import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { format, parseISO } from "date-fns";
import type { GoalProjection } from "../../types";

interface Props {
  data: GoalProjection;
}

function StatusBadge({ status, weeksOff }: { status: string; weeksOff: number | null }) {
  if (status === "insufficient_data") {
    return (
      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400">
        Insufficient data
      </span>
    );
  }
  if (status === "no_trend") {
    return (
      <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300">
        Not trending
      </span>
    );
  }
  const weeks = Math.abs(weeksOff ?? 0);
  const isAhead = status === "ahead";
  const isOnTrack = status === "on_track";
  const color = isAhead || isOnTrack
    ? "bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300"
    : weeks <= 8
    ? "bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300"
    : "bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300";

  const label = isOnTrack
    ? "On track"
    : isAhead
    ? `${weeks}w ahead`
    : `${weeks}w behind`;

  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>{label}</span>
  );
}

export default function GoalTrajectoryCard({ data }: Props) {
  const { chart, weight, body_fat, vo2max, goal_date } = data;

  // Build a unified date-keyed map for the chart
  const dateMap: Record<string, { actual?: number; required?: number; projected?: number }> = {};

  for (const pt of chart.actual) {
    dateMap[pt.date] = { ...dateMap[pt.date], actual: pt.weight };
  }
  for (const pt of chart.required) {
    dateMap[pt.date] = { ...dateMap[pt.date], required: pt.weight };
  }
  for (const pt of chart.projected) {
    dateMap[pt.date] = { ...dateMap[pt.date], projected: pt.weight };
  }

  const chartPoints = Object.entries(dateMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, vals]) => ({ date, ...vals }));

  const allWeights = chartPoints.flatMap((p) =>
    [p.actual, p.required, p.projected].filter((v): v is number => v !== undefined)
  );
  const yMin = allWeights.length ? Math.floor(Math.min(...allWeights) - 5) : 140;
  const yMax = allWeights.length ? Math.ceil(Math.max(...allWeights) + 5) : 200;

  const formatDate = (d: string) => {
    try { return format(parseISO(d), "MMM d"); } catch { return d; }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      <div className="flex items-center justify-between mb-1">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Goal Trajectory</h3>
        <span className="text-xs text-gray-400 dark:text-gray-500">
          {data.days_remaining} days to {format(parseISO(goal_date), "MMM d, yyyy")}
        </span>
      </div>

      {/* Status badges */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        {/* Body Fat */}
        <div className="rounded-lg bg-gray-50 dark:bg-gray-700/50 p-3 flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Body Fat</span>
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            {body_fat.current_pct?.toFixed(1)}% → {body_fat.goal_pct}%
          </span>
          <StatusBadge status={body_fat.status} weeksOff={body_fat.weeks_diff} />
          {body_fat.projected_goal_date && (
            <span className="text-xs text-gray-400">
              ETA {format(parseISO(body_fat.projected_goal_date), "MMM yyyy")}
            </span>
          )}
        </div>

        {/* Weight */}
        <div className="rounded-lg bg-gray-50 dark:bg-gray-700/50 p-3 flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Weight</span>
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            {weight.current_lbs} → {weight.goal_lbs?.toFixed(0)} lbs
          </span>
          <StatusBadge status={weight.status} weeksOff={weight.weeks_diff} />
          {weight.projected_goal_date && (
            <span className="text-xs text-gray-400">
              ETA {format(parseISO(weight.projected_goal_date), "MMM yyyy")}
            </span>
          )}
        </div>

        {/* VO2 Max */}
        <div className="rounded-lg bg-gray-50 dark:bg-gray-700/50 p-3 flex flex-col gap-1">
          <span className="text-xs font-medium text-gray-500 dark:text-gray-400">VO2 Max</span>
          <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
            {vo2max.current} → {vo2max.goal}
          </span>
          <StatusBadge status={vo2max.status} weeksOff={vo2max.weeks_diff} />
          {vo2max.projected_goal_date && (
            <span className="text-xs text-gray-400">
              ETA {format(parseISO(vo2max.projected_goal_date), "MMM yyyy")}
            </span>
          )}
        </div>
      </div>

      {/* Chart */}
      {chartPoints.length >= 2 ? (
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={chartPoints} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              tick={{ fontSize: 11 }}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={[yMin, yMax]}
              tick={{ fontSize: 11 }}
              tickFormatter={(v) => `${v}`}
              width={36}
            />
            <Tooltip
              labelFormatter={(l) => formatDate(String(l))}
              formatter={(value, name) => {
                const labels: Record<string, string> = {
                  actual: "Actual",
                  required: "Required rate",
                  projected: "Projected rate",
                };
                return [`${Number(value).toFixed(1)} lbs`, labels[name as string] ?? name];
              }}
            />
            <Legend
              formatter={(value) => {
                const labels: Record<string, string> = { actual: "Actual", required: "Required rate", projected: "Projected rate" };
                return labels[value as string] ?? value;
              }}
              wrapperStyle={{ fontSize: 11 }}
            />
            <ReferenceLine
              x={goal_date}
              stroke="#f59e0b"
              strokeDasharray="4 2"
              label={{ value: "Goal date", position: "insideTopRight", fontSize: 10, fill: "#f59e0b" }}
            />
            <Line
              dataKey="actual"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              connectNulls={false}
            />
            <Line
              dataKey="required"
              stroke="#f97316"
              strokeWidth={1.5}
              strokeDasharray="6 3"
              dot={false}
              connectNulls
            />
            <Line
              dataKey="projected"
              stroke="#9ca3af"
              strokeWidth={1.5}
              strokeDasharray="3 3"
              dot={false}
              connectNulls
            />
          </ComposedChart>
        </ResponsiveContainer>
      ) : (
        <div className="h-[220px] flex items-center justify-center text-sm text-gray-400 dark:text-gray-500">
          Log at least 2 weight entries to see projections
        </div>
      )}

      {/* Calibration note */}
      {body_fat.calibration_factor && (
        <p className="mt-2 text-xs text-gray-400 dark:text-gray-500">
          Scale BF% calibrated ×{body_fat.calibration_factor.toFixed(2)} from DEXA
          {body_fat.calibration_date && ` (${body_fat.calibration_date})`}
        </p>
      )}

      <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
        Lean mass {body_fat.lean_mass_lbs} lbs · goal weight {weight.goal_lbs?.toFixed(1)} lbs @ {body_fat.goal_pct}% BF
      </p>
    </div>
  );
}
