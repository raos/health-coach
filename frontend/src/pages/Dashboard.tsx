import { useEffect, useState, useCallback } from "react";
import { Scale, Activity, Flame, Dumbbell, RefreshCw } from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import MetricCard from "../components/dashboard/MetricCard";
import WeightChart from "../components/dashboard/WeightChart";
import GoalProgress from "../components/dashboard/GoalProgress";
import GoalTrajectoryCard from "../components/dashboard/GoalTrajectoryCard";
import ActivityFeed from "../components/dashboard/ActivityFeed";
import QuickWeightLog from "../components/dashboard/QuickWeightLog";
import WorkoutHeatmap from "../components/dashboard/WorkoutHeatmap";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorBanner from "../components/shared/ErrorBanner";
import { getDashboardSummary, getWeightTrend, getActivityFeed, getGoalProgress, getGoalProjection, getWorkoutHeatmap } from "../api/dashboard";
import type { WorkoutDay } from "../api/dashboard";
import { syncActivities } from "../api/coach";
import { getProfile } from "../api/profile";
import { convertWeight, weightUnit } from "../hooks/useMeasurement";
import type { DashboardSummary, WeightLog, ActivityFeedItem, GoalProgress as GoalProgressType, GoalProjection, UserProfile } from "../types";

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [weightTrend, setWeightTrend] = useState<WeightLog[]>([]);
  const [activities, setActivities] = useState<ActivityFeedItem[]>([]);
  const [goalProgress, setGoalProgress] = useState<GoalProgressType | null>(null);
  const [goalProjection, setGoalProjection] = useState<GoalProjection | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [heatmapData, setHeatmapData] = useState<WorkoutDay[]>([]);

  const fetchAll = useCallback(async () => {
    try {
      setError("");
      const [s, wt, af, gp, hm] = await Promise.all([
        getDashboardSummary(),
        getWeightTrend(90),
        getActivityFeed(10),
        getGoalProgress(),
        getWorkoutHeatmap(12),
      ]);
      setSummary(s);
      setWeightTrend(wt);
      setActivities(af);
      setGoalProgress(gp);
      setHeatmapData(hm);
      // Goal projection is independent — failure shouldn't block the dashboard
      getGoalProjection().then(setGoalProjection).catch(() => {});
    } catch {
      setError("Failed to load dashboard data. Make sure the backend is running.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    getProfile().then(setProfile).catch(() => {});
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  async function handleSync() {
    setSyncing(true);
    try {
      await syncActivities();
      await fetchAll();
    } catch {
      // Sync might fail if credentials not set up yet
    } finally {
      setSyncing(false);
    }
  }

  const measurementSystem = profile?.measurement_system ?? "imperial";
  const currentWeightRaw = summary?.latest_weight?.weight_lbs ?? summary?.latest_dexa?.total_weight_lbs;
  const currentWeight = currentWeightRaw != null ? convertWeight(currentWeightRaw, measurementSystem) : undefined;
  const currentBF = summary?.latest_dexa?.body_fat_pct ?? 28.4;
  const currentVO2 = summary?.latest_vo2max?.vo2max ?? 45;
  const currentLeanRaw = summary?.latest_dexa?.lean_mass_lbs ?? 123.9;
  const currentLean = convertWeight(currentLeanRaw, measurementSystem);
  const wUnit = weightUnit(measurementSystem);

  return (
    <PageWrapper
      title="Dashboard"
      subtitle="Your health at a glance"
      actions={
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-2 px-4 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50 transition-colors dark:text-gray-300"
        >
          <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
          {syncing ? "Syncing..." : "Sync Data"}
        </button>
      }
    >
      {loading && (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      )}

      {error && <ErrorBanner message={error} />}

      {!loading && (
        <div className="space-y-6">
          {/* Metric Cards */}
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            <MetricCard
              title="Current Weight"
              value={currentWeight?.toFixed(1) ?? "—"}
              unit={wUnit}
              subtitle={measurementSystem === "metric" ? "Goal: 75 kg" : "Goal: 165 lbs"}
              icon={<Scale className="w-5 h-5" />}
              accentColor="blue"
            />
            <MetricCard
              title="Body Fat"
              value={currentBF?.toFixed(1) ?? "—"}
              unit="%"
              subtitle="Goal: 18% by Dec 2026"
              icon={<Flame className="w-5 h-5" />}
              accentColor="orange"
            />
            <MetricCard
              title="VO₂ Max"
              value={currentVO2?.toFixed(0) ?? "—"}
              subtitle="Goal: 50+ by Dec 2026"
              icon={<Activity className="w-5 h-5" />}
              accentColor="green"
            />
            <MetricCard
              title="Lean Mass"
              value={currentLean?.toFixed(1) ?? "—"}
              unit={wUnit}
              subtitle={measurementSystem === "metric" ? "Goal: 59+ kg" : "Goal: 130+ lbs"}
              icon={<Dumbbell className="w-5 h-5" />}
              accentColor="purple"
            />
          </div>

          {/* Charts + Heatmap + Activity */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Left column: Weight Chart → Heatmap → Activity Feed */}
            <div className="lg:col-span-2 flex flex-col gap-4">
              <WeightChart data={weightTrend} />
              <WorkoutHeatmap data={heatmapData} weeks={12} />
              <ActivityFeed activities={activities} />
            </div>
            {/* Right column: Goal Progress → Goal Trajectory → Quick Weight Log */}
            <div className="flex flex-col gap-4">
              <GoalProgress
                bfCurrent={goalProgress?.bf_current ?? currentBF}
                bfGoal={goalProgress?.bf_goal ?? 18}
                vo2Current={goalProgress?.vo2_current ?? currentVO2}
                vo2Goal={goalProgress?.vo2_goal ?? 50}
              />
              {goalProjection && <GoalTrajectoryCard data={goalProjection} />}
              <QuickWeightLog
                onLogged={fetchAll}
                calibrationFactor={goalProjection?.body_fat?.calibration_factor}
                calibrationDate={goalProjection?.body_fat?.calibration_date}
              />
            </div>
          </div>
        </div>
      )}
    </PageWrapper>
  );
}
