import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, ArrowRight, ArrowLeft, CheckCircle } from "lucide-react";
import client from "../api/client";

interface OnboardingData {
  // Step 1: Welcome
  name: string;
  dob: string;
  height_inches: number;
  measurement_system: string;
  // Step 2: Goals
  bf_goal_pct: number;
  vo2max_goal: number;
  goal_date: string;
  weight_lbs: number;
  calorie_target: number;
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
  dinner_pref: string;
  // Step 5: Integrations
  hevy_api_key: string;
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
  training_days_strength: 4,
  training_days_cardio: 2,
  training_days_rest: 1,
  preferred_exercises: "",
  exercises_to_avoid: "",
  dietary_preference: "omnivore",
  preferred_cuisines: "",
  breakfast_pref: "",
  dinner_pref: "",
  hevy_api_key: "",
};

const STEPS = [
  "Welcome",
  "Goals",
  "Training",
  "Nutrition",
  "Integrations",
];

export default function Onboarding() {
  const navigate = useNavigate();
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
        dinner_pref: data.dinner_pref || undefined,
        hevy_api_key: data.hevy_api_key || undefined,
      });

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
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Activity className="w-7 h-7 text-blue-400" />
            <span className="text-2xl font-bold text-white">HealthCoach</span>
          </div>
          <p className="text-gray-400 text-sm">Let's set up your profile</p>
        </div>

        {/* Progress bar */}
        <div className="flex gap-2 mb-6">
          {STEPS.map((label, i) => (
            <div key={i} className="flex-1">
              <div
                className={`h-1.5 rounded-full transition-all ${
                  i <= step ? "bg-blue-500" : "bg-gray-700"
                }`}
              />
              <p className={`text-xs mt-1 text-center ${i === step ? "text-blue-400" : "text-gray-600"}`}>
                {label}
              </p>
            </div>
          ))}
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-2xl overflow-hidden">
          <div className="bg-gradient-to-r from-blue-600 to-indigo-700 px-8 py-5">
            <h2 className="text-lg font-bold text-white">{STEPS[step]}</h2>
          </div>

          <div className="px-8 py-6 space-y-4">
            {error && (
              <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {error}
              </div>
            )}

            {step === 0 && <StepWelcome data={data} update={update} />}
            {step === 1 && <StepGoals data={data} update={update} />}
            {step === 2 && <StepTraining data={data} update={update} />}
            {step === 3 && <StepNutrition data={data} update={update} />}
            {step === 4 && <StepIntegrations data={data} update={update} />}
          </div>

          {/* Navigation */}
          <div className="px-8 pb-6 flex gap-3">
            {step > 0 && (
              <button
                onClick={() => setStep((s) => s - 1)}
                className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-gray-600 border border-gray-200 rounded-xl hover:bg-gray-50 transition-all"
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </button>
            )}
            <button
              onClick={step < STEPS.length - 1 ? () => setStep((s) => s + 1) : finish}
              disabled={saving}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-xl hover:bg-blue-700 transition-all disabled:opacity-60"
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

        <p className="text-center text-xs text-gray-500 mt-4">
          You can update all of these settings later from Settings.
        </p>
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
      rows={2}
      {...props}
      className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all resize-none"
    />
  );
}

function StepWelcome({ data, update }: { data: OnboardingData; update: Function }) {
  return (
    <>
      <Field label="Your name">
        <Input value={data.name} onChange={(e) => update("name", e.target.value)} placeholder="e.g. Alex Smith" />
      </Field>
      <Field label="Date of birth">
        <Input type="date" value={data.dob} onChange={(e) => update("dob", e.target.value)} />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Height (inches)">
          <Input type="number" value={data.height_inches} onChange={(e) => update("height_inches", Number(e.target.value))} />
        </Field>
        <Field label="Units">
          <Select value={data.measurement_system} onChange={(e) => update("measurement_system", e.target.value)}>
            <option value="imperial">Imperial (lbs, in)</option>
            <option value="metric">Metric (kg, cm)</option>
          </Select>
        </Field>
      </div>
    </>
  );
}

function StepGoals({ data, update }: { data: OnboardingData; update: Function }) {
  return (
    <>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Body fat goal (%)">
          <Input type="number" step="0.1" value={data.bf_goal_pct} onChange={(e) => update("bf_goal_pct", Number(e.target.value))} />
        </Field>
        <Field label="VO₂ max goal">
          <Input type="number" step="0.1" value={data.vo2max_goal} onChange={(e) => update("vo2max_goal", Number(e.target.value))} />
        </Field>
      </div>
      <Field label="Goal date">
        <Input type="date" value={data.goal_date} onChange={(e) => update("goal_date", e.target.value)} />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Current weight (lbs)">
          <Input type="number" step="0.1" value={data.weight_lbs} onChange={(e) => update("weight_lbs", Number(e.target.value))} />
        </Field>
        <Field label="Daily calorie target">
          <Input type="number" step="50" value={data.calorie_target} onChange={(e) => update("calorie_target", Number(e.target.value))} />
        </Field>
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
        <Textarea value={data.breakfast_pref} onChange={(e) => update("breakfast_pref", e.target.value)} placeholder="e.g. Quick, high protein, no cooking" />
      </Field>
      <Field label="Dinner preferences (optional)">
        <Textarea value={data.dinner_pref} onChange={(e) => update("dinner_pref", e.target.value)} placeholder="e.g. Whole foods, one-pan meals, no processed foods" />
      </Field>
    </>
  );
}

function StepIntegrations({ data, update }: { data: OnboardingData; update: Function }) {
  return (
    <>
      <p className="text-sm text-gray-600 mb-2">
        Connect your fitness apps for personalized coaching. You can skip all of these and add them later in Settings.
      </p>
      <Field label="Hevy API key (optional — for strength tracking)">
        <Input
          type="password"
          value={data.hevy_api_key}
          onChange={(e) => update("hevy_api_key", e.target.value)}
          placeholder="Get it from app.hevyapp.com → API"
        />
      </Field>
      <div className="px-4 py-3 bg-gray-50 rounded-xl text-sm text-gray-600 space-y-1">
        <p className="font-medium text-gray-700">Other integrations</p>
        <p>• <strong>Strava</strong> — connect after sign-in from Settings → Integrations</p>
        <p>• <strong>Garmin</strong> — connect after sign-in from Settings → Integrations</p>
      </div>
    </>
  );
}
