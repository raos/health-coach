import { useEffect, useState } from "react";
import { CheckSquare, ChevronDown, ChevronUp } from "lucide-react";
import { upsertCheckin, getCheckinHistory } from "../api/checkin";
import type { CheckinPayload } from "../api/checkin";
import type { WeeklyCheckin } from "../types";

type Payload = CheckinPayload;

// ----- helpers -----
function mondayOfWeek(d: Date): string {
  const day = d.getDay(); // 0=Sun
  const diff = (day === 0 ? -6 : 1 - day);
  const monday = new Date(d);
  monday.setDate(d.getDate() + diff);
  return monday.toISOString().slice(0, 10);
}

const FIELDS: { key: keyof Payload; label: string; lowLabel: string; highLabel: string }[] = [
  { key: "training_adherence", label: "Training Adherence", lowLabel: "Missed most", highLabel: "Hit all sessions" },
  { key: "energy_level",       label: "Energy Level",       lowLabel: "Very low",     highLabel: "Very high" },
  { key: "sleep_quality",      label: "Sleep Quality",      lowLabel: "Poor",         highLabel: "Excellent" },
  { key: "diet_adherence",     label: "Diet Adherence",     lowLabel: "Off track",    highLabel: "On target" },
  { key: "stress_level",       label: "Stress Level",       lowLabel: "Very low",     highLabel: "Very high" },
];

function starColor(field: string, val: number): string {
  if (field === "stress_level") {
    // high stress = bad
    if (val <= 2) return "text-green-500";
    if (val === 3) return "text-yellow-500";
    return "text-red-500";
  }
  if (val >= 4) return "text-green-500";
  if (val === 3) return "text-yellow-500";
  return "text-red-500";
}

function RatingInput({
  fieldKey,
  label,
  lowLabel,
  highLabel,
  value,
  onChange,
}: {
  fieldKey: string;
  label: string;
  lowLabel: string;
  highLabel: string;
  value: number | null;
  onChange: (v: number) => void;
}) {
  return (
    <div className="mb-6">
      <div className="flex justify-between items-baseline mb-2">
        <label className="text-sm font-medium text-gray-700 dark:text-gray-300">{label}</label>
        {value !== null && (
          <span className={`text-sm font-semibold ${starColor(fieldKey, value)}`}>{value}/5</span>
        )}
      </div>
      <div className="flex gap-2">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            onClick={() => onChange(n)}
            className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors ${
              value === n
                ? "bg-blue-600 border-blue-600 text-white"
                : "border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:border-blue-400 hover:text-blue-600 dark:hover:text-blue-400"
            }`}
          >
            {n}
          </button>
        ))}
      </div>
      <div className="flex justify-between mt-1 text-xs text-gray-400">
        <span>{lowLabel}</span>
        <span>{highLabel}</span>
      </div>
    </div>
  );
}

function CheckinCard({ checkin }: { checkin: WeeklyCheckin }) {
  const [expanded, setExpanded] = useState(false);
  const date = new Date(checkin.week_start + "T12:00:00");
  const label = date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

  const ratings = FIELDS.map((f) => ({
    ...f,
    val: checkin[f.key as keyof WeeklyCheckin] as number | null,
  })).filter((f) => f.val !== null);

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
      >
        <div className="flex items-center gap-3">
          <CheckSquare className="w-4 h-4 text-blue-500" />
          <span className="text-sm font-medium text-gray-900 dark:text-gray-100">Week of {label}</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex gap-1.5">
            {ratings.map(({ key, val }) => (
              <span key={key} className={`text-xs font-semibold px-1.5 py-0.5 rounded ${starColor(key, val!)} bg-opacity-10`}>
                {val}
              </span>
            ))}
          </div>
          {expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
        </div>
      </button>
      {expanded && (
        <div className="px-5 pb-5 border-t border-gray-100 dark:border-gray-700 pt-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
            {FIELDS.map(({ key, label: fieldLabel }) => {
              const val = checkin[key as keyof WeeklyCheckin] as number | null;
              return (
                <div key={key} className="text-sm">
                  <p className="text-gray-500 dark:text-gray-400 text-xs mb-0.5">{fieldLabel}</p>
                  <p className={`font-semibold ${val !== null ? starColor(key, val) : "text-gray-400"}`}>
                    {val !== null ? `${val}/5` : "—"}
                  </p>
                </div>
              );
            })}
          </div>
          {checkin.notes && (
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Journal</p>
              <p className="text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap">{checkin.notes}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function WeeklyCheckinPage() {
  const [form, setForm] = useState<Payload>({
    week_start: mondayOfWeek(new Date()),
    training_adherence: null,
    energy_level: null,
    sleep_quality: null,
    diet_adherence: null,
    stress_level: null,
    notes: "",
  });
  const [history, setHistory] = useState<WeeklyCheckin[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  async function loadHistory() {
    try {
      const data = await getCheckinHistory(12);
      setHistory(data);
      // Pre-fill if current week already has a check-in
      const thisWeek = mondayOfWeek(new Date());
      const existing = data.find((c) => c.week_start === thisWeek);
      if (existing) {
        setForm({
          week_start: existing.week_start,
          training_adherence: existing.training_adherence,
          energy_level: existing.energy_level,
          sleep_quality: existing.sleep_quality,
          diet_adherence: existing.diet_adherence,
          stress_level: existing.stress_level,
          notes: existing.notes ?? "",
        });
      }
    } catch {
      // ignore
    }
  }

  function setRating(key: keyof Payload, val: number) {
    setForm((prev) => ({ ...prev, [key]: val }));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await upsertCheckin(form);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      await loadHistory();
    } catch {
      setError("Failed to save check-in. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const thisWeek = mondayOfWeek(new Date());
  const weekLabel = new Date(thisWeek + "T12:00:00").toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Weekly Check-In</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Week of {weekLabel} — your responses inform Coach and Health Advisor recommendations
        </p>
      </div>

      {/* Form */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-6 mb-6">
        {FIELDS.map((f) => (
          <RatingInput
            key={f.key}
            fieldKey={f.key}
            label={f.label}
            lowLabel={f.lowLabel}
            highLabel={f.highLabel}
            value={(form[f.key as keyof Payload] as number | null) ?? null}
            onChange={(v) => setRating(f.key as keyof Payload, v)}
          />
        ))}

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Journal / Notes <span className="text-gray-400 font-normal">(optional)</span>
          </label>
          <textarea
            rows={4}
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            placeholder="How did the week feel? Any notable events, wins, or struggles..."
            value={form.notes ?? ""}
            onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))}
          />
        </div>

        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
        >
          {saving ? "Saving…" : saved ? "Saved!" : "Save Check-In"}
        </button>
      </div>

      {/* History */}
      {history.length > 0 && (
        <div>
          <h2 className="text-base font-semibold text-gray-700 dark:text-gray-300 mb-3">Past Check-Ins</h2>
          <div className="space-y-2">
            {history.map((c) => (
              <CheckinCard key={c.id} checkin={c} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
