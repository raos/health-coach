import { useEffect, useState } from "react";
import { Check, X, AlertCircle, ExternalLink, Loader2 } from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import client from "../api/client";

export default function Settings() {
  const [stravaStatus, setStravaStatus] = useState<{ connected: boolean; athlete_name?: string } | null>(null);
  const [integrationStatus, setIntegrationStatus] = useState<{ garmin: boolean; hevy: boolean; anthropic: boolean } | null>(null);
  const [garminAuth, setGarminAuth] = useState<{ authenticated: boolean } | null>(null);
  const [garminConnecting, setGarminConnecting] = useState(false);
  const [garminMfaPending, setGarminMfaPending] = useState(false);
  const [garminOtp, setGarminOtp] = useState("");
  const [garminError, setGarminError] = useState("");

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
  }, []);

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

        {/* API Keys */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
          <h2 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">API Configuration</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">All API keys are configured via the <code className="bg-gray-100 dark:bg-gray-700 dark:text-gray-300 px-1.5 py-0.5 rounded text-xs">.env</code> file in the project root.</p>
          <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
            <pre className="text-xs text-gray-600 dark:text-gray-300 font-mono">{`ANTHROPIC_API_KEY=sk-ant-...
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_secret
GARMIN_EMAIL=your@email.com
GARMIN_PASSWORD=yourpassword
HEVY_API_KEY=your-hevy-api-key`}</pre>
          </div>
          <div className="flex items-start gap-2 mt-3">
            <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-gray-500 dark:text-gray-400">Never commit the .env file to version control. It is gitignored by default.</p>
          </div>
        </div>

        {/* Profile */}
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-6">
          <h2 className="font-semibold text-gray-900 dark:text-gray-100 mb-4">Your Profile</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div><p className="text-gray-500 dark:text-gray-400">Name</p><p className="font-medium text-gray-900 dark:text-gray-100">Sandeep Rao</p></div>
            <div><p className="text-gray-500 dark:text-gray-400">Date of Birth</p><p className="font-medium text-gray-900 dark:text-gray-100">Nov 11, 1979 (Age 46)</p></div>
            <div><p className="text-gray-500 dark:text-gray-400">Body Fat Goal</p><p className="font-medium text-gray-900 dark:text-gray-100">18% by Dec 31, 2026</p></div>
            <div><p className="text-gray-500 dark:text-gray-400">VO₂ Max Goal</p><p className="font-medium text-gray-900 dark:text-gray-100">50+ by Dec 31, 2026</p></div>
            <div><p className="text-gray-500 dark:text-gray-400">Calorie Target</p><p className="font-medium text-gray-900 dark:text-gray-100">~2,200 kcal/day</p></div>
            <div><p className="text-gray-500 dark:text-gray-400">Training Device</p><p className="font-medium text-gray-900 dark:text-gray-100">Tonal (cable-based)</p></div>
          </div>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-4">To update profile settings, edit the user_profile table in health.db or use the /api/profile endpoint.</p>
        </div>
      </div>
    </PageWrapper>
  );
}
