import { useEffect, useState } from "react";
import { HeartPulse, RefreshCw, Brain, Plus } from "lucide-react";
import { format, parseISO } from "date-fns";
import PageWrapper from "../components/layout/PageWrapper";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorBanner from "../components/shared/ErrorBanner";
import MarkdownRenderer from "../components/shared/MarkdownRenderer";
import { getLatestInsights, generateInsights } from "../api/health";
import { getDexaHistory } from "../api/dexa";
import type { HealthInsight, DexaScan } from "../types";

export default function HealthAdvisor() {
  const [insight, setInsight] = useState<HealthInsight | null>(null);
  const [dexaHistory, setDexaHistory] = useState<DexaScan[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getLatestInsights(), getDexaHistory()])
      .then(([ins, dexa]) => {
        if (ins) setInsight(ins);
        setDexaHistory(dexa);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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
          {/* DEXA History */}
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

          {/* Key metrics row */}
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

          {/* Garmin placeholder */}
          <div className="bg-gray-50 border border-gray-200 border-dashed rounded-xl p-5">
            <p className="text-sm text-gray-500 text-center">
              Garmin sleep, HRV, and body battery data will appear here once Garmin credentials are configured in Settings.
            </p>
          </div>

          {/* AI Insights */}
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
