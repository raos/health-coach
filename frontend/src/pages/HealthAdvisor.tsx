import { useEffect, useState } from "react";
import { HeartPulse, RefreshCw, Brain, Moon, Footprints, Activity } from "lucide-react";
import { format, parseISO } from "date-fns";
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
} from "recharts";
import PageWrapper from "../components/layout/PageWrapper";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorBanner from "../components/shared/ErrorBanner";
import MarkdownRenderer from "../components/shared/MarkdownRenderer";
import { getLatestInsights, generateInsights } from "../api/health";
import { getSleepRange, getStepsRange, getRestingHrRange } from "../api/garmin";
import type { SleepDay, StepsDay, RestingHrDay } from "../api/garmin";
import type { HealthInsight } from "../types";

const DAYS_OPTIONS = [7, 14, 30, 60];

function avg(values: (number | undefined | null)[]): number | null {
  const valid = values.filter((v): v is number => v != null && !isNaN(v));
  return valid.length > 0 ? Math.round((valid.reduce((a, b) => a + b, 0) / valid.length) * 10) / 10 : null;
}

function shortDate(iso: string) {
  return format(parseISO(iso), "MMM d");
}

function GarminPlaceholder({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center h-40 text-sm text-gray-400 dark:text-gray-500">
      {message}
    </div>
  );
}

export default function HealthAdvisor() {
  const [insight, setInsight] = useState<HealthInsight | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const [days, setDays] = useState(30);
  const [sleepData, setSleepData] = useState<SleepDay[] | null>(null);
  const [stepsData, setStepsData] = useState<StepsDay[] | null>(null);
  const [rhrData, setRhrData] = useState<RestingHrDay[] | null>(null);
  const [garminLoading, setGarminLoading] = useState(false);
  const [garminError, setGarminError] = useState("");

  useEffect(() => {
    Promise.all([getLatestInsights()])
      .then(([ins]) => {
        if (ins) setInsight(ins);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchGarminCharts();
  }, [days]);

  async function fetchGarminCharts() {
    setGarminLoading(true);
    setGarminError("");
    try {
      const [sleep, steps, rhr] = await Promise.all([
        getSleepRange(days),
        getStepsRange(days),
        getRestingHrRange(days),
      ]);
      setSleepData(sleep);
      setStepsData(steps);
      setRhrData(rhr);
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? "";
      if (e?.response?.status === 503) {
        setGarminError(detail || "Garmin not connected");
      } else {
        setGarminError("Failed to load Garmin data.");
      }
    } finally {
      setGarminLoading(false);
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    setError("");
    try {
      const ins = await generateInsights();
      setInsight(ins);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to generate insights. Check your Anthropic API key in Settings.");
    } finally {
      setGenerating(false);
    }
  }

  const garminConnected = !garminError;
  const hasAnyData = (sleepData?.length ?? 0) + (stepsData?.length ?? 0) + (rhrData?.length ?? 0) > 0;

  const avgSleepHours = avg(sleepData?.map(d => d.duration_hours) ?? []);
  const avgSteps = avg(stepsData?.map(d => d.steps) ?? []);
  const avgRhr = avg(rhrData?.map(d => d.rhr) ?? []);

  return (
    <PageWrapper
      title="Health Advisor"
      subtitle=""
      actions={
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${generating ? "animate-spin" : ""}`} />
          {generating ? "Analyzing..." : "Refresh Insights"}
        </button>
      }
    >
      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}
      {loading && <LoadingSpinner />}

      {!loading && (
        <div className="space-y-6">

          {/* ── Garmin charts ──────────────────────────────────────────── */}
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5">
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <Activity className="w-4 h-4 text-blue-600" />
                Garmin Trends
              </h3>
              <div className="flex items-center gap-1">
                {DAYS_OPTIONS.map(d => (
                  <button
                    key={d}
                    onClick={() => setDays(d)}
                    className={`px-2.5 py-1 text-xs rounded-lg transition-colors ${days === d ? "bg-blue-600 text-white" : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"}`}
                  >
                    {d}d
                  </button>
                ))}
              </div>
            </div>

            {garminLoading && <div className="flex justify-center py-10"><LoadingSpinner /></div>}

            {!garminLoading && garminError && (
              <div className="flex flex-col items-center justify-center py-10 text-sm text-gray-400 dark:text-gray-500 gap-2">
                <Activity className="w-8 h-8 text-gray-300 dark:text-gray-600" />
                <p>{garminError}</p>
                <a href="/settings" className="text-blue-600 hover:underline text-xs">
                  Connect Garmin in Settings →
                </a>
              </div>
            )}

            {!garminLoading && garminConnected && !hasAnyData && (
              <GarminPlaceholder message="No data returned for this period. Try a shorter range." />
            )}

            {!garminLoading && garminConnected && hasAnyData && (
              <div className="space-y-8">

                {/* Sleep */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
                      <Moon className="w-4 h-4 text-indigo-500" /> Sleep
                    </p>
                    {avgSleepHours != null && (
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        Avg <span className="font-semibold text-indigo-600">{avgSleepHours}h</span>
                      </span>
                    )}
                  </div>
                  {(sleepData?.length ?? 0) === 0 ? (
                    <GarminPlaceholder message="No sleep data for this period." />
                  ) : (
                    <ResponsiveContainer width="100%" height={220}>
                      <BarChart data={sleepData!} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                        <YAxis domain={[0, 10]} tickFormatter={v => `${v}h`} tick={{ fontSize: 11 }} />
                        <Tooltip
                          formatter={(value: any) => [`${value}h`, "Sleep"]}
                          labelFormatter={(label: any) => shortDate(String(label))}
                        />
                        <ReferenceLine y={7.5} stroke="#818cf8" strokeDasharray="4 4" label={{ value: "7.5h goal", fontSize: 10, fill: "#818cf8" }} />
                        {avgSleepHours != null && <ReferenceLine y={avgSleepHours} stroke="#f97316" strokeDasharray="4 4" label={{ value: `avg ${avgSleepHours}h`, fontSize: 10, fill: "#f97316", position: "insideTopRight" }} />}
                        <Bar dataKey="duration_hours" name="Hours" fill="#818cf8" opacity={0.85} radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>

                {/* Steps */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
                      <Footprints className="w-4 h-4 text-green-500" /> Daily Steps
                    </p>
                    {avgSteps != null && (
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        Avg <span className="font-semibold text-green-600">{avgSteps.toLocaleString()} steps</span>
                      </span>
                    )}
                  </div>
                  {(stepsData?.length ?? 0) === 0 ? (
                    <GarminPlaceholder message="No steps data for this period." />
                  ) : (
                    <ResponsiveContainer width="100%" height={200}>
                      <BarChart data={stepsData!} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                        <YAxis tickFormatter={v => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v} tick={{ fontSize: 11 }} />
                        <Tooltip
                          formatter={(v: any) => [v.toLocaleString(), "Steps"]}
                          labelFormatter={(label: any) => shortDate(String(label))}
                        />
                        <ReferenceLine y={10000} stroke="#22c55e" strokeDasharray="4 4" label={{ value: "10k goal", fontSize: 10, fill: "#22c55e" }} />
                        {avgSteps != null && <ReferenceLine y={avgSteps} stroke="#f97316" strokeDasharray="4 4" label={{ value: `avg ${(avgSteps / 1000).toFixed(1)}k`, fontSize: 10, fill: "#f97316", position: "insideTopRight" }} />}
                        <Bar dataKey="steps" name="Steps" fill="#22c55e" opacity={0.8} radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>

                {/* Resting Heart Rate */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
                      <HeartPulse className="w-4 h-4 text-red-500" /> Resting Heart Rate
                    </p>
                    {avgRhr != null && (
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        Avg <span className="font-semibold text-red-600">{avgRhr} bpm</span>
                      </span>
                    )}
                  </div>
                  {(rhrData?.length ?? 0) === 0 ? (
                    <GarminPlaceholder message="No resting HR data for this period." />
                  ) : (
                    <ResponsiveContainer width="100%" height={200}>
                      <LineChart data={rhrData!} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                        <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} tickFormatter={v => `${v}bpm`} />
                        <Tooltip formatter={(v: any) => [`${v} bpm`, "Resting HR"]} labelFormatter={(label: any) => shortDate(String(label))} />
                        {avgRhr != null && <ReferenceLine y={avgRhr} stroke="#f97316" strokeDasharray="4 4" label={{ value: `avg ${avgRhr}bpm`, fontSize: 10, fill: "#f97316", position: "insideTopRight" }} />}
                        <Line dataKey="rhr" name="Resting HR" stroke="#ef4444" dot={{ r: 3 }} strokeWidth={2} connectNulls />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </div>

              </div>
            )}
          </div>


          {/* ── AI Insights ────────────────────────────────────────────── */}
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                <Brain className="w-4 h-4 text-purple-600" />
                Health Insights
              </h3>
              {insight && (
                <p className="text-xs text-gray-400 dark:text-gray-500">Generated {format(parseISO(insight.generated_at), "MMM d, yyyy")}</p>
              )}
            </div>

            {!insight ? (
              <div className="text-center py-8">
                <Brain className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
                <p className="text-gray-500 dark:text-gray-400 text-sm mb-4">No insights yet. Generate your personalized health analysis.</p>
                <button onClick={handleGenerate} disabled={generating} className="px-4 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 disabled:opacity-50">
                  {generating ? "Analyzing..." : "Generate Insights"}
                </button>
              </div>
            ) : (
              <MarkdownRenderer content={insight.content_md} />
            )}
          </div>

        </div>
      )}
    </PageWrapper>
  );
}
