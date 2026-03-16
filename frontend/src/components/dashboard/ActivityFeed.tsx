import { format, parseISO } from "date-fns";
import { Dumbbell, Footprints, Bike, Activity, Timer, Heart } from "lucide-react";
import type { ActivityFeedItem } from "../../types";

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const h = Math.floor(m / 60);
  if (h > 0) return `${h}h ${m % 60}m`;
  return `${m}m`;
}

function formatDistance(meters: number): string {
  const miles = meters / 1609.34;
  return `${miles.toFixed(2)} mi`;
}

function ActivityIcon({ item }: { item: ActivityFeedItem }) {
  if (item.type === "hevy" || item.is_tonal) return <Dumbbell className="w-4 h-4" />;
  const t = item.activity_type?.toLowerCase() || "";
  if (t.includes("run")) return <Footprints className="w-4 h-4" />;
  if (t.includes("ride") || t.includes("cycl")) return <Bike className="w-4 h-4" />;
  return <Activity className="w-4 h-4" />;
}

function ActivityBadge({ item }: { item: ActivityFeedItem }) {
  const label = item.is_tonal ? "Tonal" : item.type === "hevy" ? "Hevy" : "Strava";
  const color =
    item.is_tonal || item.type === "hevy"
      ? "bg-purple-100 text-purple-700"
      : "bg-green-100 text-green-700";
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${color}`}>{label}</span>
  );
}

interface Props {
  activities: ActivityFeedItem[];
}

export default function ActivityFeed({ activities }: Props) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Recent Activities</h3>
      {activities.length === 0 ? (
        <p className="text-sm text-gray-400 dark:text-gray-500 text-center py-6">No activities yet. Sync your data to get started.</p>
      ) : (
        <div className="space-y-3">
          {activities.map((item) => (
            <div key={item.id} className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="w-8 h-8 bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 rounded-full flex items-center justify-center flex-shrink-0">
                <ActivityIcon item={item} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">{item.name}</p>
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  {format(parseISO(item.date), "MMM d, yyyy")}
                </p>
              </div>
              <div className="flex flex-col items-end gap-1">
                <ActivityBadge item={item} />
                <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                  {item.moving_time_s && (
                    <span className="flex items-center gap-0.5">
                      <Timer className="w-3 h-3" />
                      {formatDuration(item.moving_time_s)}
                    </span>
                  )}
                  {item.average_hr && (
                    <span className="flex items-center gap-0.5">
                      <Heart className="w-3 h-3" />
                      {item.average_hr} bpm
                    </span>
                  )}
                  {item.distance_m && item.distance_m > 0 && (
                    <span>{formatDistance(item.distance_m)}</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
