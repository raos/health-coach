import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, ArrowRight, ArrowLeft, CheckCircle } from "lucide-react";
import client from "../api/client";
import { getStoredUser } from "../components/auth/ProtectedRoute";

interface OnboardingData {
  // Step 1: Welcome
  name: string;
  dob: string;
  height_inches: number;
  measurement_system: string;
  // Step 2: Goals
  weight_lbs: number;
  bf_goal_pct: number;
  vo2max_goal: number;
  goal_date: string;
  calorie_target: number;
  // Current readings (optional — saved as initial data points)
  current_bf_pct: number | "";
  current_vo2max: number | "";
  // Step 3: Training
  training_device: string;
  training_days_strength: number;
  training_days_cardio: number;
  training_days_rest: number;
  preferred_exercises: string;
  exercises_to_avoid: string;
  // Step 4: Nutrition
  dietary_preference: string;
  preferred_cuisines: string;
  breakfast_pref: string;
  lunch_pref: string;
  dinner_pref: string;
}

const DEFAULTS: OnboardingData = {
  name: "",
  dob: "",
  height_inches: 68,
  measurement_system: "imperial",
  bf_goal_pct: 18,
  vo2max_goal: 50,
  goal_date: "2026-12-31",
  weight_lbs: 175,
  calorie_target: 2200,
  training_device: "tonal",
  training_days_strength: 3,
  training_days_cardio: 3,
  training_days_rest: 1,
  preferred_exercises: "",
  exercises_to_avoid: "",
  dietary_preference: "omnivore",
  preferred_cuisines: "",
  breakfast_pref: "",
  lunch_pref: "",
  dinner_pref: "",
  current_bf_pct: "",
  current_vo2max: "",
};

const STEPS = [
  "Welcome",
  "Goals",
  "Training",
  "Nutrition",
];

export default function Onboarding() {
  const navigate = useNavigate();
  const currentUser = getStoredUser();
  const [step, setStep] = useState(0);
  const [data, setData] = useState<OnboardingData>(DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function update(field: keyof OnboardingData, value: string | number) {
    setData((d) => ({ ...d, [field]: value }));
  }

  async function finish() {
    setSaving(true);
    setError("");
    try {
      // Save profile fields
      await client.put("/api/profile", {
        name: data.name || undefined,
        dob: data.dob || undefined,
        height_inches: data.height_inches,
        measurement_system: data.measurement_system,
        bf_goal_pct: data.bf_goal_pct,
        vo2max_goal: data.vo2max_goal,
        goal_date: data.goal_date,
        calorie_target: data.calorie_target,
        training_device: data.training_device,
        training_days_strength: data.training_days_strength,
        training_days_cardio: data.training_days_cardio,
        training_days_rest: data.training_days_rest,
        preferred_exercises: data.preferred_exercises || undefined,
        exercises_to_avoid: data.exercises_to_avoid || undefined,
        dietary_preference: data.dietary_preference,
        preferred_cuisines: data.preferred_cuisines || undefined,
        breakfast_pref: data.breakfast_pref || undefined,
        lunch_pref: data.lunch_pref || undefined,
        dinner_pref: data.dinner_pref || undefined,
      });

      // Log initial weight
      if (data.weight_lbs) {
        await client.post("/api/weight/log", {
          date: new Date().toISOString().slice(0, 10),
          weight_lbs: data.weight_lbs,
        }).catch(() => {});
      }

      // Save initial body fat reading
      if (data.current_bf_pct !== "" && data.weight_lbs) {
        const bf = Number(data.current_bf_pct);
        const fat = data.weight_lbs * (bf / 100);
        const lean = data.weight_lbs - fat;
        await client.post("/api/body-composition/log", {
          date: new Date().toISOString().slice(0, 10),
          body_fat_pct: bf,
          fat_mass_lbs: parseFloat(fat.toFixed(1)),
          lean_mass_lbs: parseFloat(lean.toFixed(1)),
        }).catch(() => {});
      }

      // Save initial VO2 max reading
      if (data.current_vo2max !== "") {
        await client.post("/api/dashboard/log-vo2", {
          vo2max: Number(data.current_vo2max),
        }).catch(() => {});
      }

      // Mark onboarding complete — get back a fresh JWT
      const { data: result } = await client.post("/api/profile/complete-onboarding");
      if (result.token) {
        localStorage.setItem("auth_token", result.token);
      }
      navigate("/", { replace: true });
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to save profile. Please try again.");
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* Left panel — branding + step nav */}
      <div className="hidden lg:flex lg:w-80 xl:w-96 flex-shrink-0 bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 flex-col px-10 py-12">
        <div className="flex items-center gap-2 mb-2">
          <Activity className="w-7 h-7 text-blue-400" />
          <span className="text-xl font-bold text-white">HealthCoach</span>
        </div>
        <p className="text-gray-400 text-sm mb-6">Let's set up your profile</p>

        {currentUser && (
          <div className="flex items-center gap-3 mb-12 px-4 py-3 bg-white/5 rounded-xl border border-white/10">
            {currentUser.picture ? (
              <img src={currentUser.picture} alt="" className="w-8 h-8 rounded-full flex-shrink-0" />
            ) : (
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                {currentUser.name?.[0]?.toUpperCase() ?? "?"}
              </div>
            )}
            <div className="min-w-0">
              <p className="text-sm font-medium text-white truncate">{currentUser.name || "Signed in"}</p>
              <p className="text-xs text-gray-400 truncate">{currentUser.email}</p>
            </div>
          </div>
        )}

        <nav className="space-y-2">
          {STEPS.map((label, i) => (
            <div
              key={i}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
                i === step
                  ? "bg-blue-600 text-white"
                  : i < step
                  ? "text-gray-300"
                  : "text-gray-600"
              }`}
            >
              <div
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${
                  i < step
                    ? "bg-green-500 text-white"
                    : i === step
                    ? "bg-white text-blue-600"
                    : "bg-gray-700 text-gray-500"
                }`}
              >
                {i < step ? <CheckCircle className="w-4 h-4" /> : i + 1}
              </div>
              <span className="text-sm font-medium">{label}</span>
            </div>
          ))}
        </nav>

        <p className="mt-auto text-xs text-gray-600 pt-12">
          You can update all of these settings later from Settings.
        </p>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 bg-gray-50 flex flex-col">
        {/* Mobile header */}
        <div className="lg:hidden bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-6 h-6 text-blue-600" />
            <span className="text-lg font-bold text-gray-900">HealthCoach</span>
          </div>
          <div className="flex gap-1.5">
            {STEPS.map((_, i) => (
              <div
                key={i}
                className={`flex-1 h-1.5 rounded-full transition-all ${
                  i <= step ? "bg-blue-500" : "bg-gray-200"
                }`}
              />
            ))}
          </div>
        </div>

        <div className="flex-1 flex flex-col justify-center px-12 py-10">
          <div className="w-full">
            <h2 className="text-2xl font-bold text-gray-900 mb-1">{STEPS[step]}</h2>
            <p className="text-sm text-gray-500 mb-8">Step {step + 1} of {STEPS.length}</p>

            {error && (
              <div className="mb-6 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {error}
              </div>
            )}

            <div className="space-y-5">
              {step === 0 && <StepWelcome data={data} update={update} />}
              {step === 1 && <StepGoals data={data} update={update} />}
              {step === 2 && <StepTraining data={data} update={update} />}
              {step === 3 && <StepNutrition data={data} update={update} />}
            </div>

            {/* Navigation */}
            <div className="flex gap-3 mt-10">
              {step > 0 && (
                <button
                  onClick={() => setStep((s) => s - 1)}
                  className="flex items-center gap-2 px-5 py-2.5 text-sm font-medium text-gray-600 border border-gray-200 rounded-xl hover:bg-white transition-all"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back
                </button>
              )}
              <button
                onClick={step < STEPS.length - 1 ? () => setStep((s) => s + 1) : finish}
                disabled={saving}
                className="flex-1 flex items-center justify-center gap-2 px-5 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-xl hover:bg-blue-700 transition-all disabled:opacity-60"
              >
                {saving ? (
                  "Saving…"
                ) : step < STEPS.length - 1 ? (
                  <>Next <ArrowRight className="w-4 h-4" /></>
                ) : (
                  <>Finish <CheckCircle className="w-4 h-4" /></>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Step components ──────────────────────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
    </div>
  );
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all"
    />
  );
}

function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all bg-white"
    />
  );
}

function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      rows={3}
      {...props}
      className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all resize-none"
    />
  );
}

function StepWelcome({ data, update }: { data: OnboardingData; update: Function }) {
  const isImperial = data.measurement_system === "imperial";

  // Derive display values from the canonical height_inches without local state,
  // so switching measurement_system always stays in sync.
  const totalInches = data.height_inches || 0;
  const ft = Math.floor(totalInches / 12);
  const inPart = Math.round(totalInches % 12);
  const totalCm = Math.round(totalInches * 2.54);
  const m = Math.floor(totalCm / 100);
  const cmPart = totalCm % 100;

  return (
    <>
      <Field label="Your name">
        <Input value={data.name} onChange={(e) => update("name", e.target.value)} placeholder="e.g. Alex Smith" />
      </Field>
      <Field label="Date of birth">
        <Input type="date" value={data.dob} onChange={(e) => update("dob", e.target.value)} />
      </Field>
      <Field label="Units">
        <Select value={data.measurement_system} onChange={(e) => update("measurement_system", e.target.value)}>
          <option value="imperial">Imperial (lbs, ft/in)</option>
          <option value="metric">Metric (kg, m/cm)</option>
        </Select>
      </Field>
      {isImperial ? (
        <div className="grid grid-cols-2 gap-4">
          <Field label="Height — feet">
            <Input
              type="number" min={3} max={8} value={ft}
              onChange={(e) => update("height_inches", Number(e.target.value) * 12 + inPart)}
            />
          </Field>
          <Field label="inches">
            <Input
              type="number" min={0} max={11} value={inPart}
              onChange={(e) => update("height_inches", ft * 12 + Number(e.target.value))}
            />
          </Field>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <Field label="Height — meters">
            <Input
              type="number" min={1} max={2} value={m}
              onChange={(e) => update("height_inches", Math.round((Number(e.target.value) * 100 + cmPart) / 2.54))}
            />
          </Field>
          <Field label="centimeters">
            <Input
              type="number" min={0} max={99} value={cmPart}
              onChange={(e) => update("height_inches", Math.round((m * 100 + Number(e.target.value)) / 2.54))}
            />
          </Field>
        </div>
      )}
    </>
  );
}

function StepGoals({ data, update }: { data: OnboardingData; update: Function }) {
  return (
    <>
      <Field label="Current weight (lbs) *">
        <Input type="number" step="0.1" value={data.weight_lbs} onChange={(e) => update("weight_lbs", Number(e.target.value))} />
      </Field>

      <div className="pt-1">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Current readings (optional)</p>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Body fat %">
            <Input
              type="number" step="0.1" min={5} max={60}
              value={data.current_bf_pct}
              onChange={(e) => update("current_bf_pct", e.target.value === "" ? "" : Number(e.target.value))}
              placeholder="e.g. 24.0"
            />
          </Field>
          <Field label="VO₂ max">
            <Input
              type="number" step="0.1" min={20} max={90}
              value={data.current_vo2max}
              onChange={(e) => update("current_vo2max", e.target.value === "" ? "" : Number(e.target.value))}
              placeholder="e.g. 42"
            />
          </Field>
        </div>
      </div>

      <div className="pt-1">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Goals</p>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Body fat goal (%)">
            <Input type="number" step="0.1" value={data.bf_goal_pct} onChange={(e) => update("bf_goal_pct", Number(e.target.value))} />
          </Field>
          <Field label="VO₂ max goal">
            <Input type="number" step="0.1" value={data.vo2max_goal} onChange={(e) => update("vo2max_goal", Number(e.target.value))} />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-4 mt-4">
          <Field label="Goal date">
            <Input type="date" value={data.goal_date} onChange={(e) => update("goal_date", e.target.value)} />
          </Field>
          <Field label="Daily calorie target">
            <Input type="number" step="50" value={data.calorie_target} onChange={(e) => update("calorie_target", Number(e.target.value))} />
          </Field>
        </div>
      </div>
    </>
  );
}

function StepTraining({ data, update }: { data: OnboardingData; update: Function }) {
  return (
    <>
      <Field label="Training equipment">
        <Select value={data.training_device} onChange={(e) => update("training_device", e.target.value)}>
          <option value="tonal">Tonal (cable machine)</option>
          <option value="gym">Gym (barbells, cables, machines)</option>
          <option value="bodyweight">Bodyweight only</option>
        </Select>
      </Field>
      <div className="grid grid-cols-3 gap-3">
        <Field label="Strength days/wk">
          <Input type="number" min={1} max={7} value={data.training_days_strength} onChange={(e) => update("training_days_strength", Number(e.target.value))} />
        </Field>
        <Field label="Cardio days/wk">
          <Input type="number" min={0} max={7} value={data.training_days_cardio} onChange={(e) => update("training_days_cardio", Number(e.target.value))} />
        </Field>
        <Field label="Rest days/wk">
          <Input type="number" min={0} max={7} value={data.training_days_rest} onChange={(e) => update("training_days_rest", Number(e.target.value))} />
        </Field>
      </div>
      <Field label="Preferred exercises (optional)">
        <Textarea value={data.preferred_exercises} onChange={(e) => update("preferred_exercises", e.target.value)} placeholder="e.g. Bench press, squats, pull-ups" />
      </Field>
      <Field label="Exercises to avoid / injuries (optional)">
        <Textarea value={data.exercises_to_avoid} onChange={(e) => update("exercises_to_avoid", e.target.value)} placeholder="e.g. Overhead press — shoulder injury" />
      </Field>
    </>
  );
}

function StepNutrition({ data, update }: { data: OnboardingData; update: Function }) {
  return (
    <>
      <Field label="Dietary preference">
        <Select value={data.dietary_preference} onChange={(e) => update("dietary_preference", e.target.value)}>
          <option value="omnivore">Omnivore</option>
          <option value="vegetarian">Vegetarian (eggs OK)</option>
          <option value="vegan">Vegan</option>
          <option value="pescatarian">Pescatarian</option>
        </Select>
      </Field>
      <Field label="Preferred cuisines (optional)">
        <Input value={data.preferred_cuisines} onChange={(e) => update("preferred_cuisines", e.target.value)} placeholder="e.g. South Indian, Mediterranean, Mexican" />
      </Field>
      <Field label="Breakfast preferences (optional)">
        <Textarea rows={4} value={data.breakfast_pref} onChange={(e) => update("breakfast_pref", e.target.value)} placeholder="e.g. Quick, high protein, no cooking" />
      </Field>
      <Field label="Lunch preferences (optional)">
        <Textarea rows={4} value={data.lunch_pref} onChange={(e) => update("lunch_pref", e.target.value)} placeholder="e.g. Light, salads, leftovers from dinner" />
      </Field>
      <Field label="Dinner preferences (optional)">
        <Textarea rows={4} value={data.dinner_pref} onChange={(e) => update("dinner_pref", e.target.value)} placeholder="e.g. Whole foods, one-pan meals, no processed foods" />
      </Field>
    </>
  );
}

