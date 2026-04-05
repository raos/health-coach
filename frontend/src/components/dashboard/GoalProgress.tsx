import { Target } from "lucide-react";

interface Props {
  bfCurrent: number | null;
  bfGoal: number | null;
  bfPctComplete: number | null;
  vo2Current: number | null;
  vo2Goal: number | null;
  vo2PctComplete: number | null;
  goalDate?: string;
}

export default function GoalProgress({
  bfCurrent, bfGoal, bfPctComplete,
  vo2Current, vo2Goal, vo2PctComplete,
  goalDate,
}: Props) {
  const hasBf = bfCurrent !== null && bfGoal !== null;
  const hasVo2 = vo2Current !== null && vo2Goal !== null;

  if (!hasBf && !hasVo2) return null;

  const dateLabel = goalDate
    ? new Date(goalDate).toLocaleDateString("en-US", { month: "short", year: "numeric" })
    : "Goal";

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      <div className="flex items-center gap-2 mb-4">
        <Target className="w-4 h-4 text-blue-600" />
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Goal Progress</h3>
        <span className="text-xs text-gray-400 dark:text-gray-500 ml-auto">By {dateLabel}</span>
      </div>

      {hasBf && (
        <div className={hasVo2 ? "mb-4" : ""}>
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Body Fat %</span>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {bfCurrent}% → {bfGoal}%
            </span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div
              className="bg-orange-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${bfPctComplete ?? 0}%` }}
            />
          </div>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            {Math.round(bfPctComplete ?? 0)}% of the way there
          </p>
        </div>
      )}

      {hasVo2 && (
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-sm font-medium text-gray-700 dark:text-gray-300">VO₂ Max</span>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {vo2Current} → {vo2Goal}+
            </span>
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div
              className="bg-green-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${vo2PctComplete ?? 0}%` }}
            />
          </div>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            {Math.round(vo2PctComplete ?? 0)}% of the way there
          </p>
        </div>
      )}
    </div>
  );
}
