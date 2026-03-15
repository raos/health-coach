import { useState } from "react";
import { format } from "date-fns";
import { Scale, Check } from "lucide-react";
import { logWeight } from "../../api/weight";

interface Props {
  onLogged?: () => void;
}

export default function QuickWeightLog({ onLogged }: Props) {
  const [weight, setWeight] = useState("");
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
      await logWeight(format(new Date(), "yyyy-MM-dd"), Number(weight));
      setSuccess(true);
      setWeight("");
      setTimeout(() => setSuccess(false), 2000);
      onLogged?.();
    } catch {
      setError("Failed to log weight");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center gap-2 mb-4">
        <Scale className="w-4 h-4 text-blue-600" />
        <h3 className="font-semibold text-gray-900">Log Today's Weight</h3>
      </div>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex items-center gap-2">
          <input
            type="number"
            step="0.1"
            placeholder="Enter your weight"
            value={weight}
            onChange={(e) => setWeight(e.target.value)}
            className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <span className="text-sm text-gray-500 font-medium">lbs</span>
        </div>
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
