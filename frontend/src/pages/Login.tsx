import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Activity, Mail } from "lucide-react";
import client from "../api/client";

const ERROR_MESSAGES: Record<string, string> = {
  access_denied: "Sign-in was cancelled.",
  token_exchange_failed: "Could not complete sign-in. Please try again.",
  userinfo_failed: "Could not retrieve your Google profile. Please try again.",
  unauthorized_email: "This Google account is not authorized to access the app.",
  invite_required: "An invite code is required to sign up. Please enter your code below.",
  invalid_invite: "This invite code is invalid or has already been used.",
  account_disabled: "Your account has been disabled. Please contact support.",
  invalid_magic_link: "This sign-in link has expired or already been used. Please request a new one.",
  server_error: "A server error occurred. Please try again.",
};

export default function Login() {
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [configError, setConfigError] = useState("");
  const [inviteCode, setInviteCode] = useState(searchParams.get("invite") ?? "");
  const [magicEmail, setMagicEmail] = useState("");
  const [magicSent, setMagicSent] = useState(false);
  const [showMagicLink, setShowMagicLink] = useState(false);

  const errorCode = searchParams.get("error");
  const errorMessage = errorCode ? (ERROR_MESSAGES[errorCode] ?? "Sign-in failed. Please try again.") : "";

  async function handleGoogleSignIn() {
    setLoading(true);
    setConfigError("");
    try {
      const params = inviteCode.trim() ? `?invite=${encodeURIComponent(inviteCode.trim())}` : "";
      const res = await client.get(`/api/auth/google/url${params}`);
      window.location.href = res.data.url;
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? "Unable to start sign-in.";
      setConfigError(detail);
      setLoading(false);
    }
  }

  async function handleMagicLink() {
    if (!magicEmail.trim()) return;
    setLoading(true);
    setConfigError("");
    try {
      await client.post("/api/auth/magic-link/send", {
        email: magicEmail.trim().toLowerCase(),
        invite_code: inviteCode.trim(),
      });
      setMagicSent(true);
    } catch (e: any) {
      setConfigError(e?.response?.data?.detail ?? "Failed to send sign-in link.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Card */}
        <div className="bg-white rounded-2xl shadow-2xl overflow-hidden">
          {/* Header */}
          <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-8 py-10 text-center">
            <div className="flex items-center justify-center gap-3 mb-3">
              <Activity className="w-8 h-8 text-white" />
              <span className="text-2xl font-bold text-white tracking-tight">HealthCoach</span>
            </div>
            <p className="text-blue-100 text-sm">Your personal AI health &amp; fitness coach</p>
          </div>

          {/* Body */}
          <div className="px-8 py-8">
            <div className="text-center mb-6">
              <h1 className="text-xl font-semibold text-gray-900">Sign in</h1>
              <p className="text-sm text-gray-500 mt-1">New users need an invite code to create an account</p>
            </div>

            {/* Error from OAuth redirect */}
            {errorMessage && (
              <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
                {errorMessage}
              </div>
            )}

            {configError && (
              <div className="mb-4 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
                {configError}
              </div>
            )}

            {magicSent ? (
              <div className="text-center py-6">
                <Mail className="w-12 h-12 text-blue-500 mx-auto mb-3" />
                <p className="font-semibold text-gray-900">Check your email</p>
                <p className="text-sm text-gray-500 mt-1">
                  We sent a sign-in link to <strong>{magicEmail}</strong>. It expires in 15 minutes.
                </p>
                <button
                  onClick={() => { setMagicSent(false); setMagicEmail(""); }}
                  className="mt-4 text-sm text-blue-600 hover:underline"
                >
                  Use a different email
                </button>
              </div>
            ) : (
              <>
                {/* Invite code input */}
                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Invite code <span className="text-gray-400 font-normal">(required for new accounts)</span>
                  </label>
                  <input
                    type="text"
                    value={inviteCode}
                    onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                    placeholder="e.g. AB12CD"
                    className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 tracking-widest font-mono"
                  />
                </div>

                {/* Google sign-in */}
                <button
                  onClick={handleGoogleSignIn}
                  disabled={loading}
                  className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white border-2 border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-all shadow-sm disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {!loading ? (
                    <svg className="w-5 h-5" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 animate-spin text-gray-400" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  )}
                  {loading ? "Redirecting…" : "Continue with Google"}
                </button>

                {/* Divider */}
                <div className="my-4 flex items-center gap-3">
                  <div className="flex-1 h-px bg-gray-200" />
                  <span className="text-xs text-gray-400">or</span>
                  <div className="flex-1 h-px bg-gray-200" />
                </div>

                {/* Magic link */}
                {showMagicLink ? (
                  <div className="space-y-3">
                    <input
                      type="email"
                      value={magicEmail}
                      onChange={(e) => setMagicEmail(e.target.value)}
                      placeholder="you@example.com"
                      className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                      onKeyDown={(e) => e.key === "Enter" && handleMagicLink()}
                    />
                    <button
                      onClick={handleMagicLink}
                      disabled={loading || !magicEmail.trim()}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-xl hover:bg-indigo-700 transition-all disabled:opacity-60"
                    >
                      <Mail className="w-4 h-4" />
                      {loading ? "Sending…" : "Send sign-in link"}
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setShowMagicLink(true)}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-gray-200 rounded-xl text-sm text-gray-600 hover:bg-gray-50 transition-all"
                  >
                    <Mail className="w-4 h-4" />
                    Sign in with email link instead
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Stats teaser */}
        <div className="mt-6 grid grid-cols-3 gap-3 text-center">
          {[
            { label: "Training", value: "Personal Coach" },
            { label: "Nutrition", value: "Personal Nutritionist" },
            { label: "Insights", value: "Health Advisor" },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white/10 rounded-xl px-3 py-3 backdrop-blur-sm">
              <p className="text-xs text-gray-400">{label}</p>
              <p className="text-sm font-medium text-white mt-0.5">{value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
