import { useState } from "react";
import { format } from "date-fns";
import { Scale, Check } from "lucide-react";
import { logWeight } from "../../api/weight";

interface Props {
  onLogged?: () => void;
  calibrationFactor?: number | null;
  calibrationDate?: string | null;
}

export default function QuickWeightLog({ onLogged, calibrationFactor, calibrationDate }: Props) {
  const [weight, setWeight] = useState("");
  const [bfPct, setBfPct] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!weight || isNaN(Number(weight))) {
      setError("Enter a valid weight");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const bf = bfPct && !isNaN(Number(bfPct)) ? Number(bfPct) : undefined;
      await logWeight(format(new Date(), "yyyy-MM-dd"), Number(weight), undefined, bf);
      setSuccess(true);
      setWeight("");
      setBfPct("");
      setTimeout(() => setSuccess(false), 2000);
      onLogged?.();
    } catch {
      setError("Failed to log weight");
    } finally {
      setLoading(false);
    }
  }

  const calibratedBf = bfPct && calibrationFactor && !isNaN(Number(bfPct))
    ? (Number(bfPct) * calibrationFactor).toFixed(1)
    : null;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      <div className="flex items-center gap-2 mb-4">
        <Scale className="w-4 h-4 text-blue-600" />
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Log Today's Weight</h3>
      </div>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex items-center gap-2">
          <input
            type="number"
            step="0.1"
            placeholder="Enter your weight"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400"
          />
          <span className="text-sm text-gray-500 dark:text-gray-400 font-medium">lbs</span>
        </div>
        <div className="flex items-center gap-2">
          <input
            type="number"
            step="0.1"
            min="5"
            max="60"
            placeholder="Body fat % (optional, from scale)"
            value={bfPct}
            onChange={(e) => setBfPct(e.target.value)}
            className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400"
          />
          <span className="text-sm text-gray-500 dark:text-gray-400 font-medium">%</span>
        </div>
        {calibratedBf && (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            DEXA-calibrated: ~{calibratedBf}%
            {calibrationDate && ` (×${calibrationFactor?.toFixed(2)} from ${calibrationDate} scan)`}
          </p>
        )}
        {error && <p className="text-xs text-red-500">{error}</p>}
        <button
          type="submit"
          disabled={loading || success}
          className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white text-sm font-medium py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {success ? (
            <>
              <Check className="w-4 h-4" /> Logged!
            </>
          ) : loading ? (
            "Saving..."
          ) : (
            "Log Weight"
          )}
        </button>
      </form>
    </div>
  );
}
