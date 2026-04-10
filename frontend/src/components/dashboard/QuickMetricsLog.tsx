import { useState } from "react";
import { format } from "date-fns";
import { Scale, Flame, Activity, Check } from "lucide-react";
import { logWeight } from "../../api/weight";
import client from "../../api/client";

interface Props {
  onLogged?: () => void;
}

type Tab = "weight" | "bodyfat" | "vo2";

export default function QuickMetricsLog({ onLogged }: Props) {
  const [tab, setTab] = useState<Tab>("weight");

  // Weight
  const [weight, setWeight] = useState("");
  const [weightBfPct, setWeightBfPct] = useState("");
  // Body fat
  const [bfPct, setBfPct] = useState("");
  // VO2 max
  const [vo2, setVo2] = useState("");

  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  function resetState() {
    setLoading(false);
    setError("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    resetState();
    setSuccess(false);

    try {
      setLoading(true);
      const today = format(new Date(), "yyyy-MM-dd");

      if (tab === "weight") {
        if (!weight || isNaN(Number(weight))) { setError("Enter a valid weight"); return; }
        const bfPct = weightBfPct && !isNaN(Number(weightBfPct)) ? Number(weightBfPct) : null;
        await logWeight(today, Number(weight), undefined, bfPct);
        setWeight("");
        setWeightBfPct("");
      } else if (tab === "bodyfat") {
        if (!bfPct || isNaN(Number(bfPct))) { setError("Enter a valid body fat %"); return; }
        await client.post("/api/body-composition/log", {
          date: today,
          body_fat_pct: Number(bfPct),
        });
        setBfPct("");
      } else {
        if (!vo2 || isNaN(Number(vo2))) { setError("Enter a valid VO₂ max"); return; }
        await client.post("/api/dashboard/log-vo2", { vo2max: Number(vo2) });
        setVo2("");
      }

      setSuccess(true);
      setTimeout(() => setSuccess(false), 2000);
      onLogged?.();
    } catch {
      setError("Failed to save. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: "weight",  label: "Weight",    icon: <Scale   className="w-3.5 h-3.5" /> },
    { key: "bodyfat", label: "Body Fat",  icon: <Flame   className="w-3.5 h-3.5" /> },
    { key: "vo2",     label: "VO₂ Max",   icon: <Activity className="w-3.5 h-3.5" /> },
  ];

  const inputCls = "flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400";

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-3">Log Today</h3>

      {/* Tab bar */}
      <div className="flex rounded-lg border border-gray-200 dark:border-gray-600 overflow-hidden mb-4">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => { setTab(t.key); setError(""); setSuccess(false); }}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium transition-colors ${
              tab === t.key
                ? "bg-blue-600 text-white"
                : "bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600"
            }`}
          >
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        {tab === "weight" && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <input type="number" step="0.1" placeholder="Weight" value={weight}
                onChange={(e) => setWeight(e.target.value)} className={inputCls} />
              <span className="text-sm text-gray-500 dark:text-gray-400 font-medium">lbs</span>
            </div>
            <div className="flex items-center gap-2">
              <input type="number" step="0.1" min="5" max="50" placeholder="Body fat % (optional)" value={weightBfPct}
                onChange={(e) => setWeightBfPct(e.target.value)} className={inputCls} />
              <span className="text-sm text-gray-500 dark:text-gray-400 font-medium">%</span>
            </div>
          </div>
        )}

        {tab === "bodyfat" && (
          <div className="flex items-center gap-2">
            <input type="number" step="0.1" placeholder="Body fat %" value={bfPct}
              onChange={(e) => setBfPct(e.target.value)} className={inputCls} />
            <span className="text-sm text-gray-500 dark:text-gray-400 font-medium">%</span>
          </div>
        )}

        {tab === "vo2" && (
          <div className="flex items-center gap-2">
            <input type="number" step="0.1" placeholder="VO₂ max" value={vo2}
              onChange={(e) => setVo2(e.target.value)} className={inputCls} />
            <span className="text-sm text-gray-500 dark:text-gray-400 font-medium">ml/kg/min</span>
          </div>
        )}

        {error && <p className="text-xs text-red-500">{error}</p>}

        <button
          type="submit"
          disabled={loading || success}
          className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white text-sm font-medium py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {success ? <><Check className="w-4 h-4" /> Logged!</> : loading ? "Saving…" : "Log"}
        </button>
      </form>
    </div>
  );
}
