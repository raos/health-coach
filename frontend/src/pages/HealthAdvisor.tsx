import { useEffect, useState } from "react";
import { HeartPulse, RefreshCw, Brain, Plus, Moon, Footprints, Activity } from "lucide-react";
import { format, parseISO } from "date-fns";
import {
  ResponsiveContainer, ComposedChart, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from "recharts";
import PageWrapper from "../components/layout/PageWrapper";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorBanner from "../components/shared/ErrorBanner";
import MarkdownRenderer from "../components/shared/MarkdownRenderer";
import { getLatestInsights, generateInsights } from "../api/health";
import { getSleepRange, getStepsRange, getHrvRange, getRestingHrRange } from "../api/garmin";
import type { SleepDay, StepsDay, HrvDay, RestingHrDay } from "../api/garmin";
import { getDexaHistory } from "../api/dexa";
import type { HealthInsight, DexaScan } from "../types";

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
    <div className="flex items-center justify-center h-40 text-sm text-gray-400">
      {message}
    </div>
  );
}

export default function HealthAdvisor() {
  const [insight, setInsight] = useState<HealthInsight | null>(null);
  const [dexaHistory, setDexaHistory] = useState<DexaScan[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  const [days, setDays] = useState(30);
  const [sleepData, setSleepData] = useState<SleepDay[] | null>(null);
  const [stepsData, setStepsData] = useState<StepsDay[] | null>(null);
  const [hrvData, setHrvData] = useState<HrvDay[] | null>(null);
  const [rhrData, setRhrData] = useState<RestingHrDay[] | null>(null);
  const [garminLoading, setGarminLoading] = useState(false);
  const [garminError, setGarminError] = useState("");

  useEffect(() => {
    Promise.all([getLatestInsights(), getDexaHistory()])
      .then(([ins, dexa]) => {
        if (ins) setInsight(ins);
        setDexaHistory(dexa);
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
      const [sleep, steps, hrv, rhr] = await Promise.all([
        getSleepRange(days),
        getStepsRange(days),
        getHrvRange(days),
        getRestingHrRange(days),
      ]);
      setSleepData(sleep);
      setStepsData(steps);
      setHrvData(hrv);
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

  // Merge HRV and RHR onto one timeline
  const heartData = (() => {
    const map: Record<string, { date: string; hrv?: number; rhr?: number }> = {};
    (hrvData ?? []).forEach(d => { map[d.date] = { date: d.date, hrv: d.hrv }; });
    (rhrData ?? []).forEach(d => {
      if (map[d.date]) map[d.date].rhr = d.rhr;
      else map[d.date] = { date: d.date, rhr: d.rhr };
    });
    return Object.values(map).sort((a, b) => a.date.localeCompare(b.date));
  })();

  const garminConnected = !garminError;
  const hasAnyData = (sleepData?.length ?? 0) + (stepsData?.length ?? 0) + heartData.length > 0;

  const avgSleepHours = avg(sleepData?.map(d => d.duration_hours) ?? []);
  const avgSleepScore = avg(sleepData?.map(d => d.score) ?? []);
  const avgSteps = avg(stepsData?.map(d => d.steps) ?? []);
  const avgHrv = avg(heartData.map(d => d.hrv));
  const avgRhr = avg(heartData.map(d => d.rhr));

  return (
    <PageWrapper
      title="Health Advisor"
      subtitle="Peter Attia & Andrew Huberman philosophy · Longevity-focused insights"
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
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="flex items-center justify-between mb-5">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Activity className="w-4 h-4 text-blue-600" />
                Garmin Trends
              </h3>
              <div className="flex items-center gap-1">
                {DAYS_OPTIONS.map(d => (
                  <button
                    key={d}
                    onClick={() => setDays(d)}
                    className={`px-2.5 py-1 text-xs rounded-lg transition-colors ${days === d ? "bg-blue-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"}`}
                  >
                    {d}d
                  </button>
                ))}
              </div>
            </div>

            {garminLoading && <div className="flex justify-center py-10"><LoadingSpinner /></div>}

            {!garminLoading && garminError && (
              <div className="flex flex-col items-center justify-center py-10 text-sm text-gray-400 gap-2">
                <Activity className="w-8 h-8 text-gray-300" />
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
                    <p className="text-sm font-medium text-gray-700 flex items-center gap-1.5">
                      <Moon className="w-4 h-4 text-indigo-500" /> Sleep
                    </p>
                    {avgSleepHours != null && (
                      <span className="text-xs text-gray-500">
                        Avg <span className="font-semibold text-indigo-600">{avgSleepHours}h</span>
                        {avgSleepScore != null && <> · Score <span className="font-semibold text-amber-600">{avgSleepScore}</span></>}
                      </span>
                    )}
                  </div>
                  {(sleepData?.length ?? 0) === 0 ? (
                    <GarminPlaceholder message="No sleep data for this period." />
                  ) : (
                    <ResponsiveContainer width="100%" height={220}>
                      <ComposedChart data={sleepData!} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                        <YAxis yAxisId="hrs" domain={[0, 10]} tickFormatter={v => `${v}h`} tick={{ fontSize: 11 }} />
                        <YAxis yAxisId="score" orientation="right" domain={[0, 100]} tick={{ fontSize: 11 }} hide />
                        <Tooltip
                          formatter={(value: any, name: string) => {
                            if (name === "Hours") return [`${value}h`, "Sleep"];
                            if (name === "Score") return [value, "Sleep Score"];
                            if (name === "Deep") return [`${value}m`, "Deep"];
                            if (name === "REM") return [`${value}m`, "REM"];
                            return [value, name];
                          }}
                          labelFormatter={shortDate}
                        />
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                        <ReferenceLine yAxisId="hrs" y={7.5} stroke="#818cf8" strokeDasharray="4 4" label={{ value: "7.5h goal", fontSize: 10, fill: "#818cf8" }} />
                        {avgSleepHours != null && <ReferenceLine yAxisId="hrs" y={avgSleepHours} stroke="#f97316" strokeDasharray="4 4" label={{ value: `avg ${avgSleepHours}h`, fontSize: 10, fill: "#f97316", position: "insideTopRight" }} />}
                        <Bar yAxisId="hrs" dataKey="duration_hours" name="Hours" fill="#818cf8" opacity={0.85} radius={[3, 3, 0, 0]} />
                        <Line yAxisId="score" dataKey="score" name="Score" stroke="#f59e0b" dot={false} strokeWidth={2} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  )}
                </div>

                {/* Steps */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-medium text-gray-700 flex items-center gap-1.5">
                      <Footprints className="w-4 h-4 text-green-500" /> Daily Steps
                    </p>
                    {avgSteps != null && (
                      <span className="text-xs text-gray-500">
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
                          labelFormatter={shortDate}
                        />
                        <ReferenceLine y={10000} stroke="#22c55e" strokeDasharray="4 4" label={{ value: "10k goal", fontSize: 10, fill: "#22c55e" }} />
                        {avgSteps != null && <ReferenceLine y={avgSteps} stroke="#f97316" strokeDasharray="4 4" label={{ value: `avg ${(avgSteps / 1000).toFixed(1)}k`, fontSize: 10, fill: "#f97316", position: "insideTopRight" }} />}
                        <Bar dataKey="steps" name="Steps" fill="#22c55e" opacity={0.8} radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </div>

                {/* HRV + Resting HR */}
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-medium text-gray-700 flex items-center gap-1.5">
                      <HeartPulse className="w-4 h-4 text-red-500" /> HRV &amp; Resting Heart Rate
                    </p>
                    <span className="text-xs text-gray-500 flex gap-3">
                      {avgHrv != null && <>Avg HRV <span className="font-semibold text-purple-600">{avgHrv}ms</span></>}
                      {avgRhr != null && <>Avg RHR <span className="font-semibold text-red-600">{avgRhr}bpm</span></>}
                    </span>
                  </div>
                  {heartData.length === 0 ? (
                    <GarminPlaceholder message="No HRV or resting HR data for this period." />
                  ) : (
                    <ResponsiveContainer width="100%" height={220}>
                      <LineChart data={heartData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                        <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                        <YAxis yAxisId="hrv" domain={["auto", "auto"]} tick={{ fontSize: 11 }} tickFormatter={v => `${v}ms`} />
                        <YAxis yAxisId="rhr" orientation="right" domain={["auto", "auto"]} tick={{ fontSize: 11 }} tickFormatter={v => `${v}bpm`} />
                        <Tooltip
                          formatter={(v: any, name: string) => {
                            if (name === "HRV") return [`${v}ms`, "HRV"];
                            if (name === "Resting HR") return [`${v} bpm`, "Resting HR"];
                            return [v, name];
                          }}
                          labelFormatter={shortDate}
                        />
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                        {avgHrv != null && <ReferenceLine yAxisId="hrv" y={avgHrv} stroke="#8b5cf6" strokeDasharray="4 4" label={{ value: `avg ${avgHrv}ms`, fontSize: 10, fill: "#8b5cf6", position: "insideTopLeft" }} />}
                        {avgRhr != null && <ReferenceLine yAxisId="rhr" y={avgRhr} stroke="#ef4444" strokeDasharray="4 4" label={{ value: `avg ${avgRhr}bpm`, fontSize: 10, fill: "#ef4444", position: "insideTopRight" }} />}
                        <Line yAxisId="hrv" dataKey="hrv" name="HRV" stroke="#8b5cf6" dot={{ r: 3 }} strokeWidth={2} connectNulls />
                        <Line yAxisId="rhr" dataKey="rhr" name="Resting HR" stroke="#ef4444" dot={{ r: 3 }} strokeWidth={2} connectNulls />
                      </LineChart>
                    </ResponsiveContainer>
                  )}
                </div>

              </div>
            )}
          </div>

          {/* ── DEXA History ───────────────────────────────────────────── */}
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <HeartPulse className="w-4 h-4 text-purple-600" />
                DEXA Scan History
              </h3>
              <a href="/settings" className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                <Plus className="w-3 h-3" /> Log New Scan
              </a>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-xs text-gray-500 uppercase tracking-wide">
                    <th className="text-left pb-2 font-medium">Date</th>
                    <th className="text-right pb-2 font-medium">Weight</th>
                    <th className="text-right pb-2 font-medium">Body Fat</th>
                    <th className="text-right pb-2 font-medium">Lean Mass</th>
                    <th className="text-right pb-2 font-medium">Visceral Fat</th>
                    <th className="text-right pb-2 font-medium">Facility</th>
                  </tr>
                </thead>
                <tbody>
                  {dexaHistory.map((scan) => (
                    <tr key={scan.id} className="border-b border-gray-50">
                      <td className="py-2 font-medium text-gray-900">{format(parseISO(scan.scan_date), "MMM d, yyyy")}</td>
                      <td className="py-2 text-right text-gray-700">{scan.total_weight_lbs} lbs</td>
                      <td className="py-2 text-right">
                        <span className={`font-medium ${scan.body_fat_pct > 25 ? "text-orange-600" : scan.body_fat_pct > 20 ? "text-yellow-600" : "text-green-600"}`}>
                          {scan.body_fat_pct}%
                        </span>
                      </td>
                      <td className="py-2 text-right text-gray-700">{scan.lean_mass_lbs} lbs</td>
                      <td className="py-2 text-right text-gray-500">{scan.visceral_fat_lbs ? `${scan.visceral_fat_lbs} lbs` : "—"}</td>
                      <td className="py-2 text-right text-gray-400 text-xs">{scan.facility || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* ── Key metrics ────────────────────────────────────────────── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-purple-50 border border-purple-200 rounded-xl p-4">
              <p className="text-xs text-purple-600 font-medium uppercase tracking-wide">Current BF%</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{dexaHistory[0]?.body_fat_pct ?? 28.4}%</p>
              <p className="text-xs text-gray-500 mt-0.5">Goal: 18% by Dec 2026</p>
            </div>
            <div className="bg-green-50 border border-green-200 rounded-xl p-4">
              <p className="text-xs text-green-600 font-medium uppercase tracking-wide">VO₂ Max</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">45</p>
              <p className="text-xs text-gray-500 mt-0.5">Goal: 50+ by Dec 2026</p>
            </div>
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
              <p className="text-xs text-blue-600 font-medium uppercase tracking-wide">Lean Mass</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{dexaHistory[0]?.lean_mass_lbs ?? 123.9} lbs</p>
              <p className="text-xs text-gray-500 mt-0.5">Goal: 130+ lbs</p>
            </div>
            <div className="bg-orange-50 border border-orange-200 rounded-xl p-4">
              <p className="text-xs text-orange-600 font-medium uppercase tracking-wide">Visceral Fat</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{dexaHistory[0]?.visceral_fat_lbs ?? 1.38} lbs</p>
              <p className="text-xs text-gray-500 mt-0.5">Target: &lt;0.60 lbs</p>
            </div>
          </div>

          {/* ── AI Insights ────────────────────────────────────────────── */}
          <div className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                <Brain className="w-4 h-4 text-purple-600" />
                Health Insights
              </h3>
              {insight && (
                <p className="text-xs text-gray-400">Generated {format(parseISO(insight.generated_at), "MMM d, yyyy")}</p>
              )}
            </div>

            {!insight ? (
              <div className="text-center py-8">
                <Brain className="w-8 h-8 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500 text-sm mb-4">No insights yet. Generate your personalized health analysis.</p>
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
