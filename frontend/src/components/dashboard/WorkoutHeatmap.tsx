import { useMemo } from "react";
import type { WorkoutDay } from "../../api/dashboard";

interface Props {
  data: WorkoutDay[];
  weeks?: number;
}

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function toLocalIso(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function workoutClass(hasWorkout: boolean): string {
  return hasWorkout
    ? "bg-green-500 dark:bg-green-500"
    : "bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700";
}

type Cell = {
  date: Date;
  isoDate: string;
  workout: WorkoutDay | null;
  isFuture: boolean;
};

export default function WorkoutHeatmap({ data, weeks = 12 }: Props) {
  const { grid, streak, totalSessions, monthLabels } = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);


    // Monday of the current week
    const dow = today.getDay(); // 0=Sun
    const daysToMon = dow === 0 ? 6 : dow - 1;
    const thisMonday = new Date(today);
    thisMonday.setDate(today.getDate() - daysToMon);

    // Start date: Monday of (weeks-1) weeks ago
    const startDate = new Date(thisMonday);
    startDate.setDate(thisMonday.getDate() - (weeks - 1) * 7);

    // Build lookup map
    const dayMap = new Map<string, WorkoutDay>();
    for (const d of data) dayMap.set(d.date, d);


    // Build 12 × 7 grid
    const gridData: Cell[][] = [];
    for (let w = 0; w < weeks; w++) {
      const week: Cell[] = [];
      for (let d = 0; d < 7; d++) {
        const cellDate = new Date(startDate);
        cellDate.setDate(startDate.getDate() + w * 7 + d);
        const isoDate = toLocalIso(cellDate);
        week.push({
          date: cellDate,
          isoDate,
          workout: dayMap.get(isoDate) ?? null,
          isFuture: cellDate > today,
        });
      }
      gridData.push(week);
    }

    // Month label: show the month name above the column that contains the
    // 1st of that month. For the first column (which may start mid-month),
    // fall back to showing whatever month that column starts in.
    const mLabels = gridData.map((week, wi) => {
      for (const cell of week) {
        if (cell.date.getDate() === 1) return MONTHS[cell.date.getMonth()];
      }
      if (wi === 0) return MONTHS[week[0].date.getMonth()];
      return "";
    });

    // Streak: consecutive weeks (ending this week or last) with ≥3 workouts
    // Build a map of week-monday → session count
    const weekCounts = new Map<string, number>();
    for (const d of data) {
      const dt = new Date(d.date + "T00:00:00");
      const dow = dt.getDay();
      const daysToMon = dow === 0 ? 6 : dow - 1;
      const mon = new Date(dt);
      mon.setDate(dt.getDate() - daysToMon);
      const key = toLocalIso(mon);
      weekCounts.set(key, (weekCounts.get(key) ?? 0) + d.count);
    }

    // Walk back week by week from this week (or last week if this week not yet ≥3)
    const todayDow = today.getDay();
    const todayDaysToMon = todayDow === 0 ? 6 : todayDow - 1;
    const curMon = new Date(today);
    curMon.setDate(today.getDate() - todayDaysToMon);

    // If current week hasn't hit 3 yet, start counting from last week
    const thisWeekKey = toLocalIso(curMon);
    const startMon = new Date(curMon);
    if ((weekCounts.get(thisWeekKey) ?? 0) < 3) {
      startMon.setDate(curMon.getDate() - 7);
    }

    let streak = 0;
    const scanMon = new Date(startMon);
    while (true) {
      const key = toLocalIso(scanMon);
      if ((weekCounts.get(key) ?? 0) >= 3) {
        streak++;
        scanMon.setDate(scanMon.getDate() - 7);
      } else {
        break;
      }
    }

    const totalSessions = data.reduce((s, d) => s + d.count, 0);

    return { grid: gridData, streak, totalSessions, monthLabels: mLabels };
  }, [data, weeks]);

  function tooltip(cell: Cell): string {
    if (cell.isFuture) return toLocalIso(cell.date);
    const label = `${MONTHS[cell.date.getMonth()]} ${cell.date.getDate()}`;
    if (!cell.workout) return `${label} — Rest day`;
    const w = cell.workout;
    const parts: string[] = [];
    if (w.hevy_volume_lbs > 0) parts.push(`Strength: ${w.hevy_volume_lbs.toLocaleString()} lbs`);
    if (w.cardio_minutes > 0) parts.push(`Cardio: ${Math.round(w.cardio_minutes)} min`);
    const totalMin = Math.round(w.total_minutes);
    return `${label} — ${parts.join(" + ")} (${totalMin} min total)`;
  }

  function cellColor(cell: Cell): string {
    if (cell.isFuture) return "bg-gray-50 dark:bg-gray-900 border border-gray-100 dark:border-gray-800";
    return workoutClass(cell.workout !== null);
  }

  const LEGEND = [
    { cls: "bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700", label: "Rest" },
    { cls: "bg-green-500 dark:bg-green-500", label: "Workout" },
  ];

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">Workout Consistency</h3>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            Last {weeks} weeks · {totalSessions} sessions
          </p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{streak}</p>
          <p className="text-xs text-gray-500 dark:text-gray-400">week streak (3+ workouts)</p>
        </div>
      </div>

      {/* Grid */}
      <div className="flex gap-1 overflow-x-auto pb-1">
        {/* Day-of-week labels */}
        <div className="flex flex-col gap-1 mr-1 flex-shrink-0">
          <div className="h-4" />{/* spacer for month row */}
          {DAY_LABELS.map((d, i) => (
            <div key={i} className="h-3.5 flex items-center">
              <span className="text-[10px] text-gray-400 dark:text-gray-500 w-7 text-right pr-1 leading-none">
                {i % 2 === 0 ? d : ""}
              </span>
            </div>
          ))}
        </div>

        {/* Week columns */}
        {grid.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-1 flex-shrink-0">
            {/* Month label */}
            <div className="h-4 flex items-end">
              <span className="text-[10px] text-gray-400 dark:text-gray-500 leading-none whitespace-nowrap">
                {monthLabels[wi]}
              </span>
            </div>
            {/* Day cells */}
            {week.map((cell, di) => (
              <div
                key={di}
                title={tooltip(cell)}
                className={`w-3.5 h-3.5 rounded-sm cursor-default transition-opacity hover:opacity-80 ${cellColor(cell)}`}
              />
            ))}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-2 mt-3 justify-end">
        {LEGEND.map(({ cls, label }) => (
          <div key={label} className="flex items-center gap-1">
            <div className={`w-3 h-3 rounded-sm ${cls}`} />
            <span className="text-[10px] text-gray-400 dark:text-gray-500">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
