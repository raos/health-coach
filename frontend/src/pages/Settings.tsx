import { useEffect, useState } from "react";
import { Check, X, ExternalLink, Loader2, Save, Download, Trash2 } from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import client from "../api/client";
import { getProfile, updateProfile } from "../api/profile";
import type { UserProfile } from "../types";

export default function Settings() {
  const [stravaStatus, setStravaStatus] = useState<{ connected: boolean; athlete_name?: string } | null>(null);
  const [integrationStatus, setIntegrationStatus] = useState<{ hevy: boolean; anthropic: boolean; mcp_api_key?: string; telegram_connected?: boolean; telegram_bot_username?: string } | null>(null);
  const [telegramStatus, setTelegramStatus] = useState<{ connected: boolean; username: string | null; connected_at: string | null } | null>(null);
  const [mcpCopied, setMcpCopied] = useState(false);

  const [showPasteData, setShowPasteData] = useState(false);
  const [pasteJson, setPasteJson] = useState("");
  const [pasteImporting, setPasteImporting] = useState(false);
  const [pasteError, setPasteError] = useState("");
  const [pasteResult, setPasteResult] = useState<{ date: string; steps: number | null; resting_hr: number | null; sleep_duration_hours: number | null } | null>(null);

  // Profile state
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileForm, setProfileForm] = useState<Partial<UserProfile>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveSuccess, setSaveSuccess] = useState(false);
  // Height input in the selected unit
  const [heightInput, setHeightInput] = useState("");

  // Text representations of JSON array fields
  const [exercisesText, setExercisesText] = useState("");
  const [avoidText, setAvoidText] = useState("");
  const [cuisinesText, setCuisinesText] = useState("");

  // Hevy API key
  const [hevyKey, setHevyKey] = useState("");
  const [hevySaving, setHevySaving] = useState(false);

  // MCP key generation
  const [mcpGenerating, setMcpGenerating] = useState(false);

  // Log measurements
  const [measWeight, setMeasWeight] = useState("");
  const [measBfPct, setMeasBfPct] = useState("");
  const [measVo2, setMeasVo2] = useState("");
  const [measSaving, setMeasSaving] = useState(false);
  const [measSuccess, setMeasSuccess] = useState(false);
  const [measError, setMeasError] = useState("");

  // Data export
  const [exporting, setExporting] = useState(false);

  // Account deletion
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteInput, setDeleteInput] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  useEffect(() => {
    client.get("/api/strava/status")
      .then((r) => setStravaStatus(r.data))
      .catch(() => setStravaStatus({ connected: false }));


    client.get("/api/settings/status")
      .then((r) => setIntegrationStatus(r.data))
      .catch(() => {});

    client.get("/api/telegram/status")
      .then((r) => setTelegramStatus(r.data))
      .catch(() => setTelegramStatus({ connected: false, username: null, connected_at: null }));

    getProfile()
      .then((p) => {
        setProfile(p);
        setProfileForm(p);
        setHeightInput(formatHeightInput(p.height_inches, p.measurement_system));
        const parseArr = (s?: string | null) => {
          try { return s ? (JSON.parse(s) as string[]).join(", ") : ""; } catch { return s ?? ""; }
        };
        setExercisesText(parseArr(p.preferred_exercises));
        setAvoidText(parseArr(p.exercises_to_avoid));
        setCuisinesText(parseArr(p.preferred_cuisines));
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

    const textToArr = (s: string) => JSON.stringify(s.split(",").map((x) => x.trim()).filter(Boolean));
    const payload: Partial<UserProfile> = {
      ...profileForm,
      height_inches: heightInches ?? profileForm.height_inches ?? undefined,
      preferred_exercises: exercisesText.trim() ? textToArr(exercisesText) : undefined,
      exercises_to_avoid: avoidText.trim() ? textToArr(avoidText) : undefined,
      preferred_cuisines: cuisinesText.trim() ? textToArr(cuisinesText) : undefined,
    };

    try {
      const updated = await updateProfile(payload);
      setProfile(updated);
      setProfileForm(updated);
      setHeightInput(formatHeightInput(updated.height_inches, updated.measurement_system));
      const parseArr = (s?: string | null) => {
        try { return s ? (JSON.parse(s) as string[]).join(", ") : ""; } catch { return s ?? ""; }
      };
      setExercisesText(parseArr(updated.preferred_exercises));
      setAvoidText(parseArr(updated.exercises_to_avoid));
      setCuisinesText(parseArr(updated.preferred_cuisines));
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (e: any) {
      setSaveError(e?.response?.data?.detail || "Failed to save profile.");
    } finally {
      setSaving(false);
    }
  }

  async function saveHevyKey() {
    if (!hevyKey.trim()) return;
    setHevySaving(true);
    try {
      await client.put("/api/profile", { hevy_api_key: hevyKey.trim() });
      setHevyKey("");
      const r = await client.get("/api/settings/status");
      setIntegrationStatus(r.data);
    } catch (e: any) {
      console.error("Failed to save Hevy key:", e);
    } finally {
      setHevySaving(false);
    }
  }

  async function disconnectHevy() {
    if (!confirm("Disconnect Hevy? Your synced workouts will remain but no new sync will be possible until you reconnect.")) return;
    await client.delete("/api/hevy/disconnect");
    setIntegrationStatus((prev) => prev ? { ...prev, hevy: false } : prev);
  }

  async function disconnectTelegram() {
    if (!confirm("Unlink your Telegram account?")) return;
    await client.delete("/api/telegram/disconnect");
    setTelegramStatus({ connected: false, username: null, connected_at: null });
  }

  async function generateMcpKey() {
    setMcpGenerating(true);
    try {
      const r = await client.post("/api/profile/generate-mcp-key");
      setIntegrationStatus((prev) => prev ? { ...prev, mcp_api_key: r.data.mcp_api_key } : prev);
    } catch (e: any) {
      console.error("Failed to generate MCP key:", e);
    } finally {
      setMcpGenerating(false);
    }
  }

  async function saveAllMeasurements() {
    setMeasError("");
    if (!measWeight && !measBfPct && !measVo2) {
      setMeasError("Enter at least one measurement to log.");
      return;
    }
    if (measWeight && isNaN(Number(measWeight))) { setMeasError("Enter a valid weight."); return; }
    if (measBfPct && isNaN(Number(measBfPct))) { setMeasError("Enter a valid body fat %."); return; }
    if (measVo2 && isNaN(Number(measVo2))) { setMeasError("Enter a valid VO₂ max."); return; }

    setMeasSaving(true);
    const today = new Date().toISOString().slice(0, 10);
    try {
      const calls: Promise<any>[] = [];
      if (measWeight) calls.push(client.post("/api/weight/log", { date: today, weight_lbs: Number(measWeight) }));
      if (measBfPct) calls.push(client.post("/api/body-composition/log", { date: today, body_fat_pct: Number(measBfPct) }));
      if (measVo2) calls.push(client.post("/api/dashboard/log-vo2", { vo2max: Number(measVo2) }));
      await Promise.all(calls);
      if (measWeight) setMeasWeight("");
      if (measBfPct) setMeasBfPct("");
      if (measVo2) setMeasVo2("");
      setMeasSuccess(true);
      setTimeout(() => setMeasSuccess(false), 2500);
    } catch (e: any) {
      setMeasError(e?.response?.data?.detail || "Failed to save.");
    } finally {
      setMeasSaving(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    try {
      const res = await client.get("/api/account/data-export", { responseType: "blob" });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `healthcoach_export_${new Date().toISOString().slice(0, 10)}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      console.error("Export failed:", e);
    } finally {
      setExporting(false);
    }
  }

  async function handleDeleteAccount() {
    if (deleteInput !== "DELETE") return;
    setDeleting(true);
    setDeleteError("");
    try {
      await client.delete("/api/account", { data: { confirmation: "DELETE" } });
      localStorage.removeItem("auth_token");
      window.location.href = "/login";
    } catch (e: any) {
      setDeleteError(e?.response?.data?.detail ?? "Failed to delete account.");
      setDeleting(false);
    }
  }

  async function importPasteData() {
    setPasteError("");
    setPasteResult(null);
    if (!pasteJson.trim()) return;
    setPasteImporting(true);
    try {
      const res = await client.post("/api/garmin/paste-data", { json_data: pasteJson.trim() });
      setPasteResult(res.data);
      setPasteJson("");
    } catch (e: any) {
      setPasteError(e?.response?.data?.detail || "Import failed.");
    } finally {
      setPasteImporting(false);
    }
  }

  async function connectStrava() {
    const res = await client.get("/api/strava/auth/url");
    window.location.href = res.data.url;
  }

  async function disconnectStrava() {
    if (!confirm("Disconnect Strava? Your synced activities will remain but no new sync will be possible until you reconnect.")) return;
    await client.delete("/api/strava/disconnect");
    setStravaStatus({ connected: false });
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
                  <>
                    <span className="flex items-center gap-1 text-xs text-green-700 bg-green-100 px-2 py-1 rounded-full">
                      <Check className="w-3 h-3" /> Connected
                    </span>
                    <button onClick={disconnectStrava} className="px-3 py-1.5 bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 text-xs font-medium rounded-lg hover:bg-red-100 hover:text-red-700 dark:hover:bg-red-900 dark:hover:text-red-300 transition-colors">
                      Disconnect
                    </button>
                  </>
                ) : (
                  <button onClick={connectStrava} className="px-3 py-1.5 bg-orange-500 text-white text-xs font-medium rounded-lg hover:bg-orange-600">
                    Connect
                  </button>
                )}
              </div>
            </div>

            {/* Garmin */}
            <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-8 h-8 bg-blue-700 rounded-lg flex items-center justify-center text-white font-bold text-xs">G</div>
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">Garmin Connect</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Import daily summary data from Garmin Connect</p>
                </div>
              </div>
              <button
                onClick={() => { setShowPasteData(!showPasteData); setPasteError(""); setPasteResult(null); }}
                className="text-xs text-blue-600 dark:text-blue-400 underline"
              >
                {showPasteData ? "Hide" : "Paste daily summary JSON from Garmin Connect →"}
              </button>
              {showPasteData && (
                <div className="mt-3 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg space-y-3">
                  <div>
                    <p className="text-xs font-semibold text-blue-800 dark:text-blue-300">Import one day from Garmin Connect</p>
                    <p className="text-xs text-blue-700 dark:text-blue-400 mt-0.5">
                      On connect.garmin.com → open DevTools (⌘⌥I) → Network tab → Fetch/XHR → navigate to a date →
                      find a request with <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">usersummary</code> in the URL →
                      Copy Response → paste below.
                    </p>
                  </div>
                  <textarea
                    value={pasteJson}
                    onChange={(e) => { setPasteJson(e.target.value); setPasteError(""); setPasteResult(null); }}
                    placeholder={'{"calendarDate": "2026-03-26", "totalSteps": 20009, "restingHeartRate": 54, ...}'}
                    rows={5}
                    className="w-full px-3 py-2 text-xs font-mono border border-blue-300 dark:border-blue-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400 bg-white dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400 resize-none"
                  />
                  {pasteError && <p className="text-xs text-red-600 dark:text-red-400">{pasteError}</p>}
                  {pasteResult && (
                    <p className="text-xs text-green-700 dark:text-green-400">
                      Imported {pasteResult.date}
                      {pasteResult.steps != null ? ` · steps: ${pasteResult.steps.toLocaleString()}` : ""}
                      {pasteResult.resting_hr != null ? ` · resting HR: ${pasteResult.resting_hr} bpm` : ""}
                      {pasteResult.sleep_duration_hours != null ? ` · sleep: ${pasteResult.sleep_duration_hours}h` : ""}
                    </p>
                  )}
                  <button
                    onClick={importPasteData}
                    disabled={pasteImporting || !pasteJson.trim()}
                    className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    {pasteImporting ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
                    {pasteImporting ? "Importing..." : "Import"}
                  </button>
                </div>
              )}
            </div>

            {/* Hevy */}
            <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-gray-800 rounded-lg flex items-center justify-center text-white font-bold text-xs">H</div>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">Hevy</p>
                    {!integrationStatus?.hevy && (
                      <p className="text-xs text-gray-500 dark:text-gray-400">Enter your API key from app.hevyapp.com → API</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {integrationStatus?.hevy ? (
                    <>
                      <span className="flex items-center gap-1 text-xs text-green-700 bg-green-100 px-2 py-1 rounded-full">
                        <Check className="w-3 h-3" /> Connected
                      </span>
                      <button onClick={disconnectHevy} className="px-3 py-1.5 bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 text-xs font-medium rounded-lg hover:bg-red-100 hover:text-red-700 dark:hover:bg-red-900 dark:hover:text-red-300 transition-colors">
                        Disconnect
                      </button>
                    </>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 bg-gray-200 dark:bg-gray-600 px-2 py-1 rounded-full">
                      <X className="w-3 h-3" /> Not configured
                    </span>
                  )}
                </div>
              </div>
              {!integrationStatus?.hevy && (
                <div className="flex gap-2 mt-3">
                  <input
                    type="password"
                    value={hevyKey}
                    onChange={(e) => setHevyKey(e.target.value)}
                    placeholder="Paste your Hevy API key…"
                    className="flex-1 px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                  />
                  <button
                    onClick={saveHevyKey}
                    disabled={hevySaving || !hevyKey.trim()}
                    className="px-3 py-2 bg-gray-800 text-white text-xs font-medium rounded-lg hover:bg-gray-900 disabled:opacity-50"
                  >
                    {hevySaving ? "Saving…" : "Save"}
                  </button>
                </div>
              )}
            </div>

            {/* Mobile Access (Claude.app MCP) */}
            <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-8 h-8 bg-purple-600 rounded-lg flex items-center justify-center text-white font-bold text-xs">M</div>
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">Mobile Access (Claude.app)</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Connect Claude.app to log meals, weight, and query your health data</p>
                </div>
                {integrationStatus?.mcp_api_key ? (
                  <span className="ml-auto flex items-center gap-1 text-xs text-green-700 bg-green-100 px-2 py-1 rounded-full">
                    <Check className="w-3 h-3" /> Configured
                  </span>
                ) : (
                  <span className="ml-auto flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 bg-gray-200 dark:bg-gray-600 px-2 py-1 rounded-full">
                    <X className="w-3 h-3" /> Not configured
                  </span>
                )}
              </div>
              {integrationStatus?.mcp_api_key ? (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-gray-600 dark:text-gray-400">Your personal MCP SSE URL</p>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded px-2 py-1.5 text-gray-700 dark:text-gray-300 break-all">
                      {`${(client.defaults.baseURL || "").replace(/\/$/, "")}/mcp/sse?key=${integrationStatus.mcp_api_key}`}
                    </code>
                    <button
                      onClick={() => {
                        const url = `${(client.defaults.baseURL || "").replace(/\/$/, "")}/mcp/sse?key=${integrationStatus.mcp_api_key}`;
                        navigator.clipboard.writeText(url).then(() => {
                          setMcpCopied(true);
                          setTimeout(() => setMcpCopied(false), 2000);
                        });
                      }}
                      className="px-3 py-1.5 bg-purple-600 text-white text-xs font-medium rounded-lg hover:bg-purple-700 whitespace-nowrap"
                    >
                      {mcpCopied ? "Copied!" : "Copy"}
                    </button>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    In Claude.app: Settings → Integrations → Add Integration → paste this URL
                  </p>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <p className="text-xs text-gray-500 dark:text-gray-400 flex-1">
                    Generate a personal API key to connect Claude.app to your health data.
                  </p>
                  <button
                    onClick={generateMcpKey}
                    disabled={mcpGenerating}
                    className="px-3 py-1.5 bg-purple-600 text-white text-xs font-medium rounded-lg hover:bg-purple-700 disabled:opacity-50 whitespace-nowrap"
                  >
                    {mcpGenerating ? "Generating…" : "Generate Key"}
                  </button>
                </div>
              )}
            </div>

            {/* Telegram */}
            <div className="p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center text-white font-bold text-sm">T</div>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-gray-100 text-sm">Telegram Bot</p>
                    {telegramStatus?.connected && telegramStatus.username ? (
                      <p className="text-xs text-gray-500 dark:text-gray-400">@{telegramStatus.username}</p>
                    ) : (
                      <p className="text-xs text-gray-500 dark:text-gray-400">Chat with your health data via Telegram</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {telegramStatus?.connected ? (
                    <>
                      <span className="flex items-center gap-1 text-xs text-green-700 bg-green-100 dark:bg-green-900/40 dark:text-green-400 px-2 py-1 rounded-full">
                        <Check className="w-3 h-3" /> Connected
                      </span>
                      <button
                        onClick={disconnectTelegram}
                        className="px-3 py-1.5 bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-200 text-xs font-medium rounded-lg hover:bg-red-100 hover:text-red-700 dark:hover:bg-red-900 dark:hover:text-red-300 transition-colors"
                      >
                        Disconnect
                      </button>
                    </>
                  ) : integrationStatus?.telegram_bot_username ? (
                    <a
                      href={`https://t.me/${integrationStatus.telegram_bot_username}?start=${integrationStatus?.mcp_api_key ?? ""}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 px-3 py-1.5 bg-blue-500 text-white text-xs font-medium rounded-lg hover:bg-blue-600"
                    >
                      Open Bot <ExternalLink className="w-3 h-3" />
                    </a>
                  ) : (
                    <span className="text-xs text-gray-400 dark:text-gray-500">Bot not configured</span>
                  )}
                </div>
              </div>
              {!telegramStatus?.connected && integrationStatus?.telegram_bot_username && integrationStatus?.mcp_api_key && (
                <div className="mt-3 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-lg">
                  <p className="text-xs text-blue-800 dark:text-blue-300 font-medium mb-1">How to connect:</p>
                  <ol className="text-xs text-blue-700 dark:text-blue-400 space-y-1 list-decimal list-inside">
                    <li>Click <b>Open Bot</b> above — your account links automatically</li>
                    <li>Or search <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">@{integrationStatus.telegram_bot_username}</code> and send: <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">/connect {integrationStatus.mcp_api_key}</code></li>
                  </ol>
                </div>
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

        {/* Data & Privacy */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
          <h2 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Data & Privacy</h2>
          <div className="space-y-4">
            {/* Export */}
            <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div>
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100">Export Your Data</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">Download a ZIP of all your health data as JSON files.</p>
              </div>
              <button
                onClick={handleExport}
                disabled={exporting}
                className="flex items-center gap-2 px-3 py-2 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                <Download className="w-3.5 h-3.5" />
                {exporting ? "Exporting…" : "Export"}
              </button>
            </div>

            {/* Delete account */}
            <div className="p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
              <p className="text-sm font-medium text-red-700 dark:text-red-400">Delete Account</p>
              <p className="text-xs text-red-600 dark:text-red-500 mt-1 mb-3">
                This will deactivate your account. All data will be permanently deleted after 30 days.
              </p>
              {!showDeleteConfirm ? (
                <button
                  onClick={() => setShowDeleteConfirm(true)}
                  className="flex items-center gap-2 px-3 py-2 bg-red-600 text-white text-xs font-medium rounded-lg hover:bg-red-700"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Delete My Account
                </button>
              ) : (
                <div className="space-y-2">
                  <p className="text-xs text-red-700 dark:text-red-400 font-medium">Type DELETE to confirm:</p>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={deleteInput}
                      onChange={(e) => setDeleteInput(e.target.value)}
                      placeholder="DELETE"
                      className="flex-1 px-3 py-2 text-sm border border-red-300 rounded-lg bg-white dark:bg-gray-800 text-red-700 dark:text-red-400"
                    />
                    <button
                      onClick={handleDeleteAccount}
                      disabled={deleteInput !== "DELETE" || deleting}
                      className="px-3 py-2 bg-red-600 text-white text-xs font-medium rounded-lg hover:bg-red-700 disabled:opacity-50"
                    >
                      {deleting ? "Deleting…" : "Confirm"}
                    </button>
                    <button
                      onClick={() => { setShowDeleteConfirm(false); setDeleteInput(""); setDeleteError(""); }}
                      className="px-3 py-2 text-xs font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50"
                    >
                      Cancel
                    </button>
                  </div>
                  {deleteError && <p className="text-xs text-red-600">{deleteError}</p>}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Log Measurements */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
          <h2 className="font-semibold text-gray-900 dark:text-gray-100 mb-1">Log Measurements</h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-5">Record current readings — these build your history and update the Dashboard.</p>

          {measError && (
            <p className="mb-4 text-xs text-red-600 dark:text-red-400">{measError}</p>
          )}

          <div className="space-y-5">
            {/* Weight */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">Weight</p>
              <div className="flex items-center gap-2">
                <input
                  type="number" step="0.1" placeholder="e.g. 175.5"
                  value={measWeight}
                  onChange={(e) => setMeasWeight(e.target.value)}
                  className={inputClass + " max-w-40"}
                />
                <span className="text-sm text-gray-500 dark:text-gray-400">lbs</span>
              </div>
            </div>

            {/* Body composition */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">Body Fat %</p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mb-2">Lean body mass is derived from your latest logged weight.</p>
              <div className="flex items-center gap-2">
                <input
                  type="number" step="0.1" placeholder="Body fat %"
                  value={measBfPct}
                  onChange={(e) => setMeasBfPct(e.target.value)}
                  className={inputClass + " max-w-40"}
                />
                <span className="text-sm text-gray-500 dark:text-gray-400">%</span>
              </div>
            </div>

            {/* VO2 Max */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">VO₂ Max</p>
              <div className="flex items-center gap-2">
                <input
                  type="number" step="0.1" placeholder="e.g. 45"
                  value={measVo2}
                  onChange={(e) => setMeasVo2(e.target.value)}
                  className={inputClass + " max-w-40"}
                />
                <span className="text-sm text-gray-500 dark:text-gray-400">ml/kg/min</span>
              </div>
            </div>

            <button
              onClick={saveAllMeasurements}
              disabled={measSaving}
              className="px-4 py-2 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {measSuccess ? "Saved!" : measSaving ? "Saving…" : "Log"}
            </button>
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
                <div className="space-y-4">
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
                  <div>
                    <label className={labelClass}>Diet Type</label>
                    <div className="flex flex-wrap gap-1">
                      {(["omnivore", "vegetarian", "vegan", "pescatarian", "other"] as const).map((opt) => (
                        <button
                          key={opt}
                          type="button"
                          onClick={() => handleFieldChange("dietary_preference", opt)}
                          className={`px-3 py-1.5 text-xs font-medium rounded-full border transition-colors ${
                            (profileForm.dietary_preference ?? "omnivore") === opt
                              ? "bg-blue-600 border-blue-600 text-white"
                              : "bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:border-blue-400"
                          }`}
                        >
                          {opt.charAt(0).toUpperCase() + opt.slice(1)}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className={labelClass}>Cuisine Preferences <span className="font-normal text-gray-400">(comma-separated)</span></label>
                    <input
                      type="text"
                      value={cuisinesText}
                      onChange={(e) => { setCuisinesText(e.target.value); setSaveSuccess(false); setSaveError(""); }}
                      className={inputClass}
                      placeholder="e.g. South Indian, Mediterranean, Japanese"
                    />
                  </div>
                  <div>
                    <label className={labelClass}>Breakfast Preferences</label>
                    <textarea
                      rows={4}
                      value={profileForm.breakfast_pref ?? ""}
                      onChange={(e) => handleFieldChange("breakfast_pref", e.target.value || null)}
                      className={inputClass}
                      placeholder="Describe your breakfast preferences…"
                    />
                  </div>
                  <div>
                    <label className={labelClass}>Lunch Preferences</label>
                    <textarea
                      rows={2}
                      value={profileForm.lunch_pref ?? ""}
                      onChange={(e) => handleFieldChange("lunch_pref", e.target.value || null)}
                      className={inputClass}
                      placeholder="Describe your lunch preferences…"
                    />
                  </div>
                  <div>
                    <label className={labelClass}>Dinner Preferences</label>
                    <textarea
                      rows={3}
                      value={profileForm.dinner_pref ?? ""}
                      onChange={(e) => handleFieldChange("dinner_pref", e.target.value || null)}
                      className={inputClass}
                      placeholder="Describe your dinner preferences…"
                    />
                  </div>
                </div>
              </div>

              {/* Training Preferences */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-3">Training Preferences</h3>
                <div className="space-y-4">
                  <div>
                    <label className={labelClass}>Exercises I'm Interested In <span className="font-normal text-gray-400">(comma-separated)</span></label>
                    <textarea
                      rows={2}
                      value={exercisesText}
                      onChange={(e) => { setExercisesText(e.target.value); setSaveSuccess(false); setSaveError(""); }}
                      className={inputClass}
                      placeholder="e.g. cable rows, Romanian deadlifts, lateral raises"
                    />
                  </div>
                  <div>
                    <label className={labelClass}>Exercises to Avoid <span className="font-normal text-gray-400">(comma-separated)</span></label>
                    <textarea
                      rows={2}
                      value={avoidText}
                      onChange={(e) => { setAvoidText(e.target.value); setSaveSuccess(false); setSaveError(""); }}
                      className={inputClass}
                      placeholder="e.g. barbell back squats, overhead press"
                    />
                  </div>
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
