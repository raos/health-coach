import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { format, subDays, parseISO } from "date-fns";
import type { WeightLog } from "../../types";

interface Props {
  data: WeightLog[];
}

const PERIODS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
  { label: "All", days: 0 },
];

export default function WeightChart({ data }: Props) {
  const [period, setPeriod] = useState(30);

  const cutoff = period > 0 ? subDays(new Date(), period) : new Date("2020-01-01");
  const filtered = data
    .filter((d) => parseISO(d.date) >= cutoff)
    .map((d) => ({
      date: format(parseISO(d.date), "MMM d"),
      weight: d.weight_lbs,
    }));

  const min = Math.min(...filtered.map((d) => d.weight)) - 2;
  const max = Math.max(...filtered.map((d) => d.weight)) + 2;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900">Weight Trend</h3>
        <div className="flex gap-1">
          {PERIODS.map(({ label, days }) => (
            <button
              key={label}
              onClick={() => setPeriod(days)}
              className={`px-3 py-1 text-xs rounded-full font-medium transition-colors ${
                period === days
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
          No weight data for this period. Log your weight to see trends.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={filtered}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis domain={[min, max]} tick={{ fontSize: 11 }} unit=" lbs" width={60} />
            <Tooltip
              formatter={(value) => [`${value} lbs`, "Weight"]}
              contentStyle={{ fontSize: 12 }}
            />
            <Line
              type="monotone"
              dataKey="weight"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ r: 3, fill: "#3b82f6" }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
