import { Target } from "lucide-react";

interface Props {
  bfCurrent: number;
  bfGoal: number;
  vo2Current: number;
  vo2Goal: number;
}

export default function GoalProgress({ bfCurrent, bfGoal, vo2Current, vo2Goal }: Props) {
  const bfProgress = Math.max(0, Math.min(100, ((28.4 - bfCurrent) / (28.4 - bfGoal)) * 100));
  const vo2Progress = Math.max(0, Math.min(100, ((vo2Current - 45) / (vo2Goal - 45)) * 100));

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      <div className="flex items-center gap-2 mb-4">
        <Target className="w-4 h-4 text-blue-600" />
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Goal Progress</h3>
        <span className="text-xs text-gray-400 dark:text-gray-500 ml-auto">By Dec 2026</span>
      </div>

      <div className="mb-4">
        <div className="flex justify-between items-center mb-1.5">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Body Fat %</span>
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {bfCurrent}% → {bfGoal}%
          </span>
        </div>
        <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
          <div
            className="bg-orange-500 h-2 rounded-full transition-all duration-500"
            style={{ width: `${bfProgress}%` }}
          />
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{Math.round(bfProgress)}% of the way there</p>
      </div>

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
            style={{ width: `${vo2Progress}%` }}
          />
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">{Math.round(vo2Progress)}% of the way there</p>
      </div>
    </div>
  );
}
