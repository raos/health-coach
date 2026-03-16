import { useEffect, useState } from "react";
import { Check, X, ExternalLink, Loader2, Save } from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import client from "../api/client";
import { getProfile, updateProfile } from "../api/profile";
import type { UserProfile } from "../types";

export default function Settings() {
  const [stravaStatus, setStravaStatus] = useState<{ connected: boolean; athlete_name?: string } | null>(null);
  const [integrationStatus, setIntegrationStatus] = useState<{ garmin: boolean; hevy: boolean; anthropic: boolean } | null>(null);
  const [garminAuth, setGarminAuth] = useState<{ authenticated: boolean } | null>(null);
  const [garminConnecting, setGarminConnecting] = useState(false);
  const [garminMfaPending, setGarminMfaPending] = useState(false);
  const [garminOtp, setGarminOtp] = useState("");
  const [garminError, setGarminError] = useState("");

  // Profile state
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileForm, setProfileForm] = useState<Partial<UserProfile>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveSuccess, setSaveSuccess] = useState(false);
  // Height input in the selected unit
  const [heightInput, setHeightInput] = useState("");

  function refreshGarminStatus() {
    client.get("/api/garmin/status")
      .then((r) => setGarminAuth(r.data))
      .catch(() => {});
  }

  useEffect(() => {
    client.get("/api/strava/status")
      .then((r) => setStravaStatus(r.data))
      .catch(() => setStravaStatus({ connected: false }));

    client.get("/api/settings/status")
      .then((r) => setIntegrationStatus(r.data))
      .catch(() => {});

    refreshGarminStatus();

    getProfile()
      .then((p) => {
        setProfile(p);
        setProfileForm(p);
        setHeightInput(formatHeightInput(p.height_inches, p.measurement_system));
      })
      .catch(() => {});
  }, []);

  function formatHeightInput(inches: number | null, system: "imperial" | "metric"): string {
    if (!inches) return "";
    if (system === "metric") {
      return String(Math.round(inches * 2.54));
    }
    return String(Math.round(inches));
  }

  function parseHeightToInches(value: string, system: "imperial" | "metric"): number | null {
    const n = parseFloat(value);
    if (isNaN(n)) return null;
    if (system === "metric") {
      return Math.round((n / 2.54) * 10) / 10;
    }
    return n;
  }

  function handleFieldChange(field: keyof UserProfile, value: unknown) {
    setProfileForm((prev) => ({ ...prev, [field]: value }));
    setSaveSuccess(false);
    setSaveError("");
  }

  function handleMeasurementSystemChange(system: "imperial" | "metric") {
    const currentInches = profileForm.height_inches ?? profile?.height_inches ?? null;
    setProfileForm((prev) => ({ ...prev, measurement_system: system }));
    setHeightInput(formatHeightInput(currentInches, system));
    setSaveSuccess(false);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaveError("");
    setSaveSuccess(false);

    const system = profileForm.measurement_system ?? "imperial";
    const heightInches = parseHeightToInches(heightInput, system);

    const payload: Partial<UserProfile> = {
      ...profileForm,
      height_inches: heightInches ?? profileForm.height_inches ?? undefined,
    };

    try {
      const updated = await updateProfile(payload);
      setProfile(updated);
      setProfileForm(updated);
      setHeightInput(formatHeightInput(updated.height_inches, updated.measurement_system));
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e: any) {
      setSaveError(e?.response?.data?.detail || "Failed to save profile.");
    } finally {
      setSaving(false);
    }
  }

  async function connectGarmin() {
    setGarminConnecting(true);
    setGarminError("");
    try {
      const res = await client.post("/api/garmin/login");
      if (res.data.status === "mfa_required") {
        setGarminMfaPending(true);
      } else {
        refreshGarminStatus();
      }
    } catch (e: any) {
      setGarminError(e?.response?.data?.detail || e.message);
    } finally {
      setGarminConnecting(false);
    }
  }

  async function submitGarminMfa() {
    if (!garminOtp.trim()) return;
    setGarminConnecting(true);
    setGarminError("");
    try {
      await client.post("/api/garmin/verify-mfa", { otp: garminOtp });
      setGarminMfaPending(false);
      setGarminOtp("");
      refreshGarminStatus();
    } catch (e: any) {
      setGarminError(e?.response?.data?.detail || e.message);
    } finally {
      setGarminConnecting(false);
    }
  }

  async function connectStrava() {
    const res = await client.get("/api/strava/auth/url");
    window.location.href = res.data.url;
  }

  const measurementSystem = (profileForm.measurement_system ?? "imperial") as "imperial" | "metric";
  const trainingDevice = (profileForm.training_device ?? "tonal") as "tonal" | "gym" | "bodyweight";
  const heightUnit = measurementSystem === "metric" ? "cm" : "inches";

  const pillBase = "px-4 py-1.5 text-sm font-medium transition-colors cursor-pointer";
  const pillActive = "bg-blue-600 text-white";
  const pillInactive = "bg-white dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-600";

  const inputClass =
    "w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400";
  const labelClass = "block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1";

  return (
    <PageWrapper title="Settings" subtitle="Configure integrations and your profile">
      <div className="max-w-2xl space-y-6">
        {/* Integrations */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
          <h2 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Integrations</h2>
          <div className="space-y-4">
            {/* Strava */}
            <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-orange-500 rounded-lg flex items-center justify-center text-white font-bold text-xs">S</div>
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">Strava</p>
                  {stravaStatus?.connected && stravaStatus.athlete_name && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">{stravaStatus.athlete_name}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {stravaStatus?.connected ? (
                  <span className="flex items-center gap-1 text-xs text-green-700 bg-green-100 px-2 py-1 rounded-full">
                    <Check className="w-3 h-3" /> Connected
                  </span>
                ) : (
                  <button onClick={connectStrava} className="px-3 py-1.5 bg-orange-500 text-white text-xs font-medium rounded-lg hover:bg-orange-600">
                    Connect
                  </button>
                )}
              </div>
            </div>

            {/* Garmin */}
            <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-blue-700 rounded-lg flex items-center justify-center text-white font-bold text-xs">G</div>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">Garmin Connect</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {garminAuth?.authenticated
                        ? "Session active — sleep, HRV, body battery available"
                        : integrationStatus?.garmin
                        ? "Credentials set — click Connect to authenticate"
                        : "Add GARMIN_EMAIL + GARMIN_PASSWORD to .env"}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {garminAuth?.authenticated ? (
                    <span className="flex items-center gap-1 text-xs text-green-700 bg-green-100 px-2 py-1 rounded-full">
                      <Check className="w-3 h-3" /> Connected
                    </span>
                  ) : integrationStatus?.garmin ? (
                    <button
                      onClick={connectGarmin}
                      disabled={garminConnecting}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-700 text-white text-xs font-medium rounded-lg hover:bg-blue-800 disabled:opacity-50"
                    >
                      {garminConnecting ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                      {garminConnecting ? "Connecting..." : "Connect"}
                    </button>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 bg-gray-200 dark:bg-gray-600 px-2 py-1 rounded-full">
                      <X className="w-3 h-3" /> Not configured
                    </span>
                  )}
                </div>
              </div>
              {/* MFA input */}
              {garminMfaPending && (
                <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg">
                  <p className="text-xs text-blue-800 dark:text-blue-300 font-medium mb-2">
                    Garmin sent a one-time code to your email. Enter it below:
                  </p>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={garminOtp}
                      onChange={(e) => setGarminOtp(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && submitGarminMfa()}
                      placeholder="123456"
                      className="flex-1 px-3 py-1.5 text-sm border border-blue-300 dark:border-blue-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400"
                      autoFocus
                    />
                    <button
                      onClick={submitGarminMfa}
                      disabled={garminConnecting || !garminOtp.trim()}
                      className="px-3 py-1.5 bg-blue-700 text-white text-xs font-medium rounded-lg hover:bg-blue-800 disabled:opacity-50"
                    >
                      {garminConnecting ? "Verifying..." : "Verify"}
                    </button>
                  </div>
                </div>
              )}
              {garminError && (
                <p className="mt-2 text-xs text-red-600">{garminError}</p>
              )}
            </div>

            {/* Hevy */}
            <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-gray-800 rounded-lg flex items-center justify-center text-white font-bold text-xs">H</div>
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">Hevy</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {integrationStatus?.hevy ? "API key configured — workouts available in Coach" : "Add HEVY_API_KEY to .env (from api.hevyapp.com/docs)"}
                  </p>
                </div>
              </div>
              {integrationStatus?.hevy ? (
                <span className="flex items-center gap-1 text-xs text-green-700 bg-green-100 px-2 py-1 rounded-full">
                  <Check className="w-3 h-3" /> Connected
                </span>
              ) : (
                <span className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 bg-gray-200 dark:bg-gray-600 px-2 py-1 rounded-full">
                  <X className="w-3 h-3" /> Not configured
                </span>
              )}
            </div>

            {/* Patient Gateway */}
            <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg opacity-60">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-teal-600 rounded-lg flex items-center justify-center text-white font-bold text-xs">P</div>
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">Patient Gateway</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Epic FHIR integration pending — requires OAuth2 registration with your provider</p>
                </div>
              </div>
              <a href="https://fhir.epic.com" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-xs text-blue-600 hover:underline">
                Learn more <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>

        {/* Profile — editable form */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
          <h2 className="font-semibold text-gray-900 dark:text-gray-100 mb-5">Your Profile</h2>

          {!profile ? (
            <p className="text-sm text-gray-400 dark:text-gray-500">Loading profile…</p>
          ) : (
            <form onSubmit={handleSave} className="space-y-6">
              {/* Personal Details */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-3">Personal Details</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Name</label>
                    <input
                      type="text"
                      value={profileForm.name ?? ""}
                      onChange={(e) => handleFieldChange("name", e.target.value)}
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className={labelClass}>Email</label>
                    <input
                      type="email"
                      value={profileForm.email ?? ""}
                      onChange={(e) => handleFieldChange("email", e.target.value)}
                      className={inputClass}
                      placeholder="you@example.com"
                    />
                  </div>
                  <div>
                    <label className={labelClass}>Date of Birth</label>
                    <input
                      type="date"
                      value={profileForm.dob ?? ""}
                      onChange={(e) => handleFieldChange("dob", e.target.value)}
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className={labelClass}>Height ({heightUnit})</label>
                    <input
                      type="number"
                      value={heightInput}
                      onChange={(e) => { setHeightInput(e.target.value); setSaveSuccess(false); }}
                      step={measurementSystem === "metric" ? "1" : "0.5"}
                      min={measurementSystem === "metric" ? "100" : "48"}
                      max={measurementSystem === "metric" ? "250" : "96"}
                      className={inputClass}
                      placeholder={measurementSystem === "metric" ? "e.g. 173" : "e.g. 68"}
                    />
                  </div>
                </div>
              </div>

              {/* Goals */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-3">Goals</h3>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className={labelClass}>Body Fat Goal (%)</label>
                    <input
                      type="number"
                      value={profileForm.bf_goal_pct ?? ""}
                      onChange={(e) => handleFieldChange("bf_goal_pct", e.target.value ? parseFloat(e.target.value) : null)}
                      step="0.1"
                      min="5"
                      max="50"
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className={labelClass}>VO&#8322; Max Goal</label>
                    <input
                      type="number"
                      value={profileForm.vo2max_goal ?? ""}
                      onChange={(e) => handleFieldChange("vo2max_goal", e.target.value ? parseFloat(e.target.value) : null)}
                      step="1"
                      min="20"
                      max="90"
                      className={inputClass}
                    />
                  </div>
                  <div>
                    <label className={labelClass}>Goal Date</label>
                    <input
                      type="date"
                      value={profileForm.goal_date ?? ""}
                      onChange={(e) => handleFieldChange("goal_date", e.target.value)}
                      className={inputClass}
                    />
                  </div>
                </div>
              </div>

              {/* Preferences */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-3">Preferences</h3>
                <div className="space-y-4">
                  <div>
                    <label className={labelClass}>Measurement System</label>
                    <div className="flex rounded-lg border border-gray-200 dark:border-gray-600 overflow-hidden w-fit">
                      {(["imperial", "metric"] as const).map((sys) => (
                        <button
                          key={sys}
                          type="button"
                          onClick={() => handleMeasurementSystemChange(sys)}
                          className={`${pillBase} ${measurementSystem === sys ? pillActive : pillInactive}`}
                        >
                          {sys.charAt(0).toUpperCase() + sys.slice(1)}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className={labelClass}>Training Device</label>
                    <div className="flex rounded-lg border border-gray-200 dark:border-gray-600 overflow-hidden w-fit">
                      {([
                        { value: "tonal", label: "Tonal" },
                        { value: "gym", label: "Gym" },
                        { value: "bodyweight", label: "Bodyweight" },
                      ] as const).map((opt) => (
                        <button
                          key={opt.value}
                          type="button"
                          onClick={() => { handleFieldChange("training_device", opt.value); }}
                          className={`${pillBase} ${trainingDevice === opt.value ? pillActive : pillInactive}`}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Nutrition */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-3">Nutrition</h3>
                <div className="w-40">
                  <label className={labelClass}>Daily Calorie Target (kcal)</label>
                  <input
                    type="number"
                    value={profileForm.calorie_target ?? ""}
                    onChange={(e) => handleFieldChange("calorie_target", e.target.value ? parseInt(e.target.value, 10) : null)}
                    step="50"
                    min="1000"
                    max="5000"
                    className={inputClass}
                  />
                </div>
              </div>

              {/* Email Recipients */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-3">Email Recipients</h3>
                <div className="space-y-3">
                  <div>
                    <label className={labelClass}>Training Plan Recipients</label>
                    <input
                      type="text"
                      value={profileForm.training_plan_recipients ?? ""}
                      onChange={(e) => handleFieldChange("training_plan_recipients", e.target.value)}
                      className={inputClass}
                      placeholder="email1@example.com, email2@example.com"
                    />
                  </div>
                  <div>
                    <label className={labelClass}>Meal Plan Recipients</label>
                    <input
                      type="text"
                      value={profileForm.meal_plan_recipients ?? ""}
                      onChange={(e) => handleFieldChange("meal_plan_recipients", e.target.value)}
                      className={inputClass}
                      placeholder="email1@example.com, email2@example.com"
                    />
                  </div>
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    Comma-separated email addresses. Leave blank to use EMAIL_RECIPIENTS_* from .env
                  </p>
                </div>
              </div>

              {/* Save button */}
              <div className="flex items-center gap-3 pt-2">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  {saving ? "Saving..." : "Save Changes"}
                </button>
                {saveSuccess && (
                  <span className="flex items-center gap-1.5 text-sm text-green-600 dark:text-green-400">
                    <Check className="w-4 h-4" /> Saved
                  </span>
                )}
                {saveError && (
                  <span className="text-sm text-red-600">{saveError}</span>
                )}
              </div>
            </form>
          )}
        </div>
      </div>
    </PageWrapper>
  );
}
