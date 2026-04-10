import { useEffect, useState, useCallback } from "react";
import { Scale, Activity, Flame, Dumbbell, RefreshCw } from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import MetricCard from "../components/dashboard/MetricCard";
import WeightChart from "../components/dashboard/WeightChart";
import GoalProgress from "../components/dashboard/GoalProgress";
import ActivityFeed from "../components/dashboard/ActivityFeed";
import QuickMetricsLog from "../components/dashboard/QuickMetricsLog";
import WorkoutHeatmap from "../components/dashboard/WorkoutHeatmap";
import Vo2GaugeCard from "../components/dashboard/Vo2GaugeCard";
import GoalTrajectoryCard from "../components/dashboard/GoalTrajectoryCard";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorBanner from "../components/shared/ErrorBanner";
import { getDashboardSummary, getWeightTrend, getActivityFeed, getGoalProgress, getWorkoutHeatmap, getDashboardGoalProjection } from "../api/dashboard";
import type { WorkoutDay } from "../api/dashboard";
import { syncActivities } from "../api/coach";
import { getProfile } from "../api/profile";
import { convertWeight, weightUnit } from "../hooks/useMeasurement";
import type { DashboardSummary, WeightLog, ActivityFeedItem, GoalProgress as GoalProgressType, UserProfile, GoalProjection } from "../types";

export default function Dashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [weightTrend, setWeightTrend] = useState<WeightLog[]>([]);
  const [activities, setActivities] = useState<ActivityFeedItem[]>([]);
  const [goalProgress, setGoalProgress] = useState<GoalProgressType | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [heatmapData, setHeatmapData] = useState<WorkoutDay[]>([]);
  const [goalProjection, setGoalProjection] = useState<GoalProjection | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      setError("");
      const [s, wt, af, gp, hm, proj] = await Promise.all([
        getDashboardSummary(),
        getWeightTrend(90),
        getActivityFeed(10),
        getGoalProgress(),
        getWorkoutHeatmap(12),
        getDashboardGoalProjection(),
      ]);
      setSummary(s);
      setWeightTrend(wt);
      setActivities(af);
      setGoalProgress(gp);
      setHeatmapData(hm);
      setGoalProjection(proj);
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
  const age = profile?.dob
    ? Math.floor((Date.now() - new Date(profile.dob).getTime()) / (365.25 * 24 * 3600 * 1000))
    : 46;
  const currentWeightRaw = summary?.latest_weight?.weight_lbs;
  const currentWeight = currentWeightRaw != null ? convertWeight(currentWeightRaw, measurementSystem) : undefined;
  const currentBF: number | null = summary?.latest_body_comp?.body_fat_pct ?? null;
  const currentVO2: number | null = summary?.latest_vo2max?.vo2max ?? null;
  const currentLeanRaw: number | null = summary?.latest_body_comp?.lean_mass_lbs ?? null;
  const currentLean = currentLeanRaw != null ? convertWeight(currentLeanRaw, measurementSystem) : null;
  const wUnit = weightUnit(measurementSystem);
  const hasVO2Goal = Boolean(summary?.goal_vo2max);

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
              icon={<Scale className="w-5 h-5" />}
              accentColor="blue"
            />
            {currentBF !== null && (
              <MetricCard
                title="Body Fat"
                value={currentBF.toFixed(1)}
                unit="%"
                subtitle={goalProgress?.bf_goal ? `Goal: ${goalProgress.bf_goal}%` : undefined}
                icon={<Flame className="w-5 h-5" />}
                accentColor="orange"
              />
            )}
            {currentVO2 !== null && (
              <MetricCard
                title="VO₂ Max"
                value={currentVO2.toFixed(0)}
                subtitle={goalProgress?.vo2_goal ? `Goal: ${goalProgress.vo2_goal}+` : undefined}
                icon={<Activity className="w-5 h-5" />}
                accentColor="green"
              />
            )}
            {currentLean !== null && (
              <MetricCard
                title="Lean Mass"
                value={currentLean.toFixed(1)}
                unit={wUnit}
                icon={<Dumbbell className="w-5 h-5" />}
                accentColor="purple"
              />
            )}
          </div>

          {/* Charts + Heatmap + Activity */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Left column: Weight Chart → Heatmap → Activity Feed */}
            <div className="lg:col-span-2 flex flex-col gap-4">
              <WeightChart data={weightTrend} />
              <WorkoutHeatmap data={heatmapData} weeks={12} />
              <ActivityFeed activities={activities} />
            </div>
            {/* Right column: Goal Progress → VO2 Trend → Quick Weight Log */}
            <div className="flex flex-col gap-4">
              <GoalProgress
                bfCurrent={goalProgress?.bf_current ?? null}
                bfGoal={goalProgress?.bf_goal ?? null}
                bfPctComplete={goalProgress?.bf_pct_complete ?? null}
                vo2Current={goalProgress?.vo2_current ?? null}
                vo2Goal={goalProgress?.vo2_goal ?? null}
                vo2PctComplete={goalProgress?.vo2_pct_complete ?? null}
                goalDate={summary?.goal_date}
              />
              {currentVO2 !== null && hasVO2Goal && (
                <Vo2GaugeCard vo2max={currentVO2} goal={summary!.goal_vo2max!} age={age} />
              )}
              {goalProjection && <GoalTrajectoryCard data={goalProjection} />}
              <QuickMetricsLog onLogged={fetchAll} />
            </div>
          </div>
        </div>
      )}
    </PageWrapper>
  );
}
