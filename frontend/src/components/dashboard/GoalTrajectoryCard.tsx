import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer,
} from "recharts";
import type { GoalProjection, MetricTrajectory } from "../../types";

interface Props {
  data: GoalProjection;
}

function badgeClass(weeks: number): string {
  if (weeks >= 2) return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
  if (weeks >= 0) return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200";
  return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
}

function badgeLabel(weeks: number): string {
  if (weeks === 0) return "on track";
  const abs = Math.abs(weeks);
  return weeks > 0 ? `${abs} wk${abs === 1 ? "" : "s"} ahead` : `${abs} wk${abs === 1 ? "" : "s"} behind`;
}

// Merge actual + required + projected arrays into Recharts-compatible data by date
function buildChartData(metric: MetricTrajectory): Array<Record<string, number | string>> {
  const map = new Map<string, Record<string, number | string>>();

  for (const p of metric.actual) {
    map.set(p.date, { date: p.date, actual: p.value });
  }
  for (const p of metric.required) {
    const existing = map.get(p.date) ?? { date: p.date };
    map.set(p.date, { ...existing, required: p.value });
  }
  if (metric.projected) {
    for (const p of metric.projected) {
      const existing = map.get(p.date) ?? { date: p.date };
      map.set(p.date, { ...existing, projected: p.value });
    }
  }

  return Array.from(map.values()).sort((a, b) =>
    (a.date as string).localeCompare(b.date as string)
  );
}

function StatBox({
  label,
  current,
  goal,
  unit,
  weeksDelta,
}: {
  label: string;
  current: number;
  goal: number;
  unit: string;
  weeksDelta: number;
}) {
  return (
    <div className="flex-1 border border-gray-200 dark:border-gray-700 rounded-lg p-3 text-center">
      <div className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1">
        {label}
      </div>
      <div className="text-xl font-bold text-gray-900 dark:text-gray-100">
        {current.toFixed(1)}
        <span className="text-sm font-normal text-gray-500 dark:text-gray-400 ml-1">{unit}</span>
      </div>
      <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
        goal {goal.toFixed(1)}{unit}
      </div>
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badgeClass(weeksDelta)}`}>
        {badgeLabel(weeksDelta)}
      </span>
    </div>
  );
}

function TrajectoryChart({
  metric,
  color,
  unit,
  today,
}: {
  metric: MetricTrajectory;
  color: string;
  unit: string;
  today: string;
}) {
  const chartData = buildChartData(metric);

  return (
    <div>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10 }}
            tickFormatter={(v: string) => v.slice(5)}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 10 }}
            width={38}
            tickFormatter={(v: number) => `${v.toFixed(0)}${unit}`}
            domain={["auto", "auto"]}
          />
          <Tooltip
            formatter={(v) => [`${Number(v).toFixed(1)}${unit}`]}
            labelFormatter={(l) => String(l)}
          />
          <ReferenceLine x={today} stroke="#94a3b8" strokeDasharray="4 2" label={{ value: "Today", fontSize: 9, fill: "#94a3b8" }} />
          <Line dataKey="actual" stroke={color} strokeWidth={2} dot={false} name="Actual" connectNulls={false} />
          <Line dataKey="required" stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="5 3" dot={false} name="Required" connectNulls />
          {metric.projected && (
            <Line dataKey="projected" stroke={color} strokeWidth={1.5} strokeDasharray="5 3" dot={false} name="Projected" connectNulls />
          )}
        </LineChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-4 text-xs text-gray-400 mt-1">
        <span className="flex items-center gap-1">
          <span className="inline-block w-4 h-0.5" style={{ backgroundColor: color }}></span> Actual
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-4 h-0.5 border-t-2 border-dashed border-gray-400"></span> Required
        </span>
        {metric.projected && (
          <span className="flex items-center gap-1">
            <span className="inline-block w-4 h-0.5 border-t-2 border-dashed" style={{ borderColor: color }}></span> Projected
          </span>
        )}
      </div>
    </div>
  );
}

export default function GoalTrajectoryCard({ data }: Props) {
  const [expanded, setExpanded] = useState(false);

  const hasWeight = data.weight !== null;
  const hasBf = data.bf_pct !== null;

  if (!hasWeight && !hasBf) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Goal Trajectory</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Set your weight goal and goal date in{" "}
          <a href="/settings" className="text-blue-600 hover:underline">Settings → Goals</a> to see your trajectory.
        </p>
      </div>
    );
  }

  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Goal Trajectory</h3>
        {data.goal_date && (
          <span className="text-xs text-gray-500 dark:text-gray-400">by {data.goal_date}</span>
        )}
      </div>

      {/* Compact stat boxes */}
      <div className="flex gap-3 mb-3">
        {hasWeight && (
          <StatBox
            label="Weight"
            current={data.weight!.current}
            goal={data.weight!.goal}
            unit="lbs"
            weeksDelta={data.weight!.weeks_delta}
          />
        )}
        {hasBf && (
          <StatBox
            label="Body Fat"
            current={data.bf_pct!.current}
            goal={data.bf_pct!.goal}
            unit="%"
            weeksDelta={data.bf_pct!.weeks_delta}
          />
        )}
      </div>

      {/* Expand toggle */}
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center justify-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline py-1"
      >
        {expanded ? <><ChevronUp className="w-3 h-3" /> Hide charts</> : <><ChevronDown className="w-3 h-3" /> Show charts</>}
      </button>

      {/* Expanded charts */}
      {expanded && (
        <div className="mt-3 space-y-4">
          {hasWeight && (
            <div>
              <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Weight (lbs)</div>
              <TrajectoryChart metric={data.weight!} color="#3b82f6" unit="lbs" today={today} />
            </div>
          )}
          {hasBf && (
            <div>
              <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Body Fat (%)</div>
              <TrajectoryChart metric={data.bf_pct!} color="#f97316" unit="%" today={today} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
