import type { ReactNode } from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface Props {
  title: string;
  value: string | number;
  unit?: string;
  subtitle?: string;
  trend?: "up" | "down" | "flat";
  trendLabel?: string;
  icon?: ReactNode;
  accentColor?: "blue" | "green" | "orange" | "red" | "purple";
}

const colors = {
  blue: "bg-blue-50 border-blue-200 dark:bg-blue-900/30 dark:border-blue-700",
  green: "bg-green-50 border-green-200 dark:bg-green-900/30 dark:border-green-700",
  orange: "bg-orange-50 border-orange-200 dark:bg-orange-900/30 dark:border-orange-700",
  red: "bg-red-50 border-red-200 dark:bg-red-900/30 dark:border-red-700",
  purple: "bg-purple-50 border-purple-200 dark:bg-purple-900/30 dark:border-purple-700",
};

const iconColors = {
  blue: "text-blue-600",
  green: "text-green-600",
  orange: "text-orange-600",
  red: "text-red-600",
  purple: "text-purple-600",
};

export default function MetricCard({
  title,
  value,
  unit,
  subtitle,
  trend,
  trendLabel,
  icon,
  accentColor = "blue",
}: Props) {
  const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;
  const trendColor =
    trend === "up" ? "text-green-600" : trend === "down" ? "text-red-600" : "text-gray-400";

  return (
    <div className={`rounded-xl border p-5 ${colors[accentColor]}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium text-gray-600 dark:text-gray-400">{title}</span>
        {icon && <span className={iconColors[accentColor]}>{icon}</span>}
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-3xl font-bold text-gray-900 dark:text-gray-100">{value}</span>
        {unit && <span className="text-sm text-gray-500 dark:text-gray-400 ml-1">{unit}</span>}
      </div>
      <div className="mt-2 flex items-center gap-1.5">
        {trend && (
          <TrendIcon className={`w-3.5 h-3.5 ${trendColor}`} />
        )}
        {(trendLabel || subtitle) && (
          <span className={`text-xs ${trendLabel ? trendColor : "text-gray-500"}`}>
            {trendLabel || subtitle}
          </span>
        )}
      </div>
    </div>
  );
}
