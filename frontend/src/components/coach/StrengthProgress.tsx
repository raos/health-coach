import { useEffect, useRef, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Dot,
} from "recharts";
import { TrendingUp } from "lucide-react";
import { listExercises, getExerciseProgress } from "../../api/hevy";
import type { ExerciseDataPoint } from "../../api/hevy";
import { format, parseISO } from "date-fns";

function PRDot(props: any) {
  const { cx, cy, payload } = props;
  if (!payload?.is_pr) return <Dot {...props} r={3} fill="#3b82f6" stroke="none" />;
  return (
    <g>
      <circle cx={cx} cy={cy} r={6} fill="#f59e0b" stroke="#fff" strokeWidth={2} />
      <text x={cx} y={cy - 10} textAnchor="middle" fontSize={9} fill="#f59e0b" fontWeight="bold">PR</text>
    </g>
  );
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as ExerciseDataPoint;
  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-3 shadow-lg text-xs">
      <p className="font-semibold text-gray-900 dark:text-gray-100 mb-1">
        Week of {format(parseISO(label), "MMM d, yyyy")}
        {d.is_pr && <span className="ml-2 text-amber-500 font-bold">🏆 PR</span>}
      </p>
      <p className="text-blue-600 dark:text-blue-400">Heaviest set: <span className="font-bold">{d.max_weight_lbs} lbs</span></p>
      <p className="text-gray-500 dark:text-gray-400">Est. 1RM: {d.est_1rm} lbs</p>
    </div>
  );
}

export default function StrengthProgress() {
  const [exercises, setExercises] = useState<string[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [data, setData] = useState<ExerciseDataPoint[]>([]);
  const [loading, setLoading] = useState(false);

  // Combobox state
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const comboRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listExercises().then((list) => {
      setExercises(list);
      if (list.length > 0) {
        setSelected(list[0]);
        setQuery(list[0]);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    getExerciseProgress(selected, 13)
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [selected]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (comboRef.current && !comboRef.current.contains(e.target as Node)) {
        setOpen(false);
        // Reset query to current selection if user typed but didn't pick
        setQuery(selected);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [selected]);

  const filtered = exercises.filter((e) =>
    e.toLowerCase().includes(query.toLowerCase())
  );

  function pickExercise(ex: string) {
    setSelected(ex);
    setQuery(ex);
    setOpen(false);
  }

  const maxPR = data.reduce((m, d) => (d.est_1rm > m ? d.est_1rm : m), 0);

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <TrendingUp className="w-4 h-4 text-blue-600" />
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Strength Progress</h3>
        {maxPR > 0 && (
          <span className="ml-auto text-xs text-amber-600 dark:text-amber-400 font-medium">
            PR: {maxPR} lbs est. 1RM
          </span>
        )}
      </div>

      {/* Filterable combobox */}
      <div ref={comboRef} className="relative mb-4 max-w-xs">
        <input
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder="Type to filter exercises..."
          className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-1.5 text-sm bg-white dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {open && filtered.length > 0 && (
          <ul className="absolute z-20 mt-1 w-full max-h-56 overflow-y-auto bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg shadow-lg text-sm">
            {filtered.map((ex) => (
              <li
                key={ex}
                onMouseDown={() => pickExercise(ex)}
                className={`px-3 py-2 cursor-pointer hover:bg-blue-50 dark:hover:bg-gray-600 ${
                  ex === selected ? "bg-blue-50 dark:bg-gray-600 font-medium" : "text-gray-700 dark:text-gray-200"
                }`}
              >
                {ex}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Chart */}
      {loading ? (
        <div className="h-48 flex items-center justify-center text-sm text-gray-400">Loading...</div>
      ) : data.length === 0 ? (
        <div className="h-48 flex items-center justify-center text-sm text-gray-400 dark:text-gray-500">
          No data for this exercise yet. Try syncing data.
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={data} margin={{ top: 16, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="date"
              tickFormatter={(v) => format(parseISO(v), "MMM d")}
              tick={{ fontSize: 10, fill: "#9ca3af" }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#9ca3af" }}
              tickLine={false}
              axisLine={false}
              width={40}
              label={{ value: "lbs", angle: -90, position: "insideLeft", offset: 8, style: { fontSize: 10, fill: "#9ca3af" } }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="max_weight_lbs"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={<PRDot />}
              activeDot={{ r: 5 }}
              name="Est. 1RM"
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      <p className="text-[10px] text-gray-400 dark:text-gray-500 mt-2 text-right">
        Heaviest set per week · 🏆 = weight PR week · est. 1RM (Epley) shown in header
      </p>
    </div>
  );
}
