import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Mail, CheckCircle } from "lucide-react";
import client from "../api/client";

const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  access_denied: "Sign-in was cancelled.",
  token_exchange_failed: "Could not complete sign-in. Please try again.",
  userinfo_failed: "Could not retrieve your Google profile. Please try again.",
  unauthorized_email: "This Google account is not authorized to access the app.",
  invite_required: "An invite code is required to sign up. Please use the Sign Up tab.",
  invalid_invite: "This invite code is invalid or has already been used.",
  account_disabled: "Your account has been disabled. Please contact support.",
  invalid_magic_link: "This sign-in link has expired or already been used. Please request a new one.",
  server_error: "A server error occurred. Please try again.",
};

type Tab = "signin" | "signup";

// ── Sign In tab ──────────────────────────────────────────────────────────────
function SignInTab() {
  const [searchParams] = useSearchParams();
  const oauthError = searchParams.get("error");
  const oauthErrorMessage =
    oauthError ? (OAUTH_ERROR_MESSAGES[oauthError] ?? "Sign-in failed. Please try again.") : "";

  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleError, setGoogleError] = useState("");

  const [showMagicLink, setShowMagicLink] = useState(false);
  const [magicEmail, setMagicEmail] = useState("");
  const [magicLoading, setMagicLoading] = useState(false);
  const [magicError, setMagicError] = useState("");
  const [magicSent, setMagicSent] = useState(false);

  async function handleGoogleSignIn() {
    setGoogleLoading(true);
    setGoogleError("");
    try {
      const res = await client.get("/api/auth/google/url");
      window.location.href = res.data.url;
    } catch (e: any) {
      setGoogleError(e?.response?.data?.detail ?? "Unable to start sign-in.");
      setGoogleLoading(false);
    }
  }

  async function handleSendSignInLink() {
    const email = magicEmail.trim().toLowerCase();
    if (!email) { setMagicError("Please enter your email address."); return; }
    if (!email.includes("@")) { setMagicError("Please enter a valid email address."); return; }
    setMagicLoading(true);
    setMagicError("");
    try {
      await client.post("/api/auth/magic-link/send", { email, invite_code: "" });
      setMagicSent(true);
    } catch (e: any) {
      const status = e?.response?.status;
      if (status === 403) {
        setMagicError("No account found for this email. Use the Sign Up tab with your invite code.");
      } else {
        setMagicError(e?.response?.data?.detail ?? "Failed to send sign-in link. Please try again.");
      }
    } finally {
      setMagicLoading(false);
    }
  }

  if (magicSent) {
    return (
      <div className="text-center py-8">
        <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Mail className="w-8 h-8 text-blue-600" />
        </div>
        <h2 className="text-xl font-bold text-gray-900 mb-2">Check your email</h2>
        <p className="text-sm text-gray-500 mb-1">We sent a sign-in link to</p>
        <p className="font-semibold text-gray-800 mb-6">{magicEmail}</p>
        <p className="text-xs text-gray-400 mb-6">The link expires in 15 minutes.</p>
        <button onClick={() => { setMagicSent(false); setMagicEmail(""); }} className="text-sm text-blue-600 hover:underline">
          Use a different email
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {oauthErrorMessage && (
        <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
          {oauthErrorMessage}
        </div>
      )}
      {googleError && (
        <div className="px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
          {googleError}
        </div>
      )}

      {/* Google */}
      <button
        onClick={handleGoogleSignIn}
        disabled={googleLoading}
        className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white border-2 border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-all shadow-sm disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {!googleLoading ? (
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
        {googleLoading ? "Redirecting…" : "Continue with Google"}
      </button>

      {/* Divider */}
      <div className="flex items-center gap-3">
        <div className="flex-1 h-px bg-gray-200" />
        <span className="text-xs text-gray-400">or</span>
        <div className="flex-1 h-px bg-gray-200" />
      </div>

      {/* Magic link */}
      {!showMagicLink ? (
        <button
          onClick={() => setShowMagicLink(true)}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-gray-200 rounded-xl text-sm text-gray-600 hover:bg-white transition-all bg-gray-50"
        >
          <Mail className="w-4 h-4" />
          Sign in with email link instead
        </button>
      ) : (
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email address</label>
            <input
              type="email"
              value={magicEmail}
              onChange={(e) => { setMagicEmail(e.target.value); setMagicError(""); }}
              placeholder="you@example.com"
              className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              onKeyDown={(e) => e.key === "Enter" && handleSendSignInLink()}
            />
          </div>
          {magicError && (
            <div className="px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
              {magicError}
            </div>
          )}
          <button
            onClick={handleSendSignInLink}
            disabled={magicLoading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-xl hover:bg-indigo-700 disabled:opacity-60 transition-all"
          >
            <Mail className="w-4 h-4" />
            {magicLoading ? "Sending…" : "Send sign-in link"}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Sign Up tab ──────────────────────────────────────────────────────────────
function SignUpTab() {
  // Step 1: enter + validate invite code
  // Step 2: choose auth method
  const [step, setStep] = useState<1 | 2>(1);
  const [inviteCode, setInviteCode] = useState("");
  const [validating, setValidating] = useState(false);
  const [inviteError, setInviteError] = useState("");

  // Step 2 — Google
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleError, setGoogleError] = useState("");

  // Step 2 — magic link
  const [showMagicLink, setShowMagicLink] = useState(false);
  const [magicEmail, setMagicEmail] = useState("");
  const [magicLoading, setMagicLoading] = useState(false);
  const [magicError, setMagicError] = useState("");
  const [magicSent, setMagicSent] = useState(false);

  async function handleValidateInvite() {
    const code = inviteCode.trim().toUpperCase();
    if (!code) { setInviteError("Please enter your invite code."); return; }
    setValidating(true);
    setInviteError("");
    try {
      await client.get(`/api/auth/validate-invite?code=${encodeURIComponent(code)}`);
      setInviteCode(code);
      setStep(2);
    } catch (e: any) {
      const detail = e?.response?.data?.detail ?? "";
      setInviteError(detail || "Invalid or expired invite code. Please check and try again.");
    } finally {
      setValidating(false);
    }
  }

  async function handleGoogleSignUp() {
    setGoogleLoading(true);
    setGoogleError("");
    try {
      const res = await client.get(`/api/auth/google/url?invite=${encodeURIComponent(inviteCode)}`);
      window.location.href = res.data.url;
    } catch (e: any) {
      setGoogleError(e?.response?.data?.detail ?? "Unable to start sign-up.");
      setGoogleLoading(false);
    }
  }

  async function handleSendSignUpLink() {
    const email = magicEmail.trim().toLowerCase();
    if (!email) { setMagicError("Please enter your email address."); return; }
    if (!email.includes("@")) { setMagicError("Please enter a valid email address."); return; }
    setMagicLoading(true);
    setMagicError("");
    try {
      await client.post("/api/auth/magic-link/send", { email, invite_code: inviteCode });
      setMagicSent(true);
    } catch (e: any) {
      setMagicError(e?.response?.data?.detail ?? "Failed to send sign-up link. Please try again.");
    } finally {
      setMagicLoading(false);
    }
  }

  if (magicSent) {
    return (
      <div className="text-center py-8">
        <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <Mail className="w-8 h-8 text-blue-600" />
        </div>
        <h2 className="text-xl font-bold text-gray-900 mb-2">Check your email</h2>
        <p className="text-sm text-gray-500 mb-1">We sent a sign-up link to</p>
        <p className="font-semibold text-gray-800 mb-6">{magicEmail}</p>
        <p className="text-xs text-gray-400 mb-6">The link expires in 15 minutes.</p>
        <button onClick={() => { setMagicSent(false); setMagicEmail(""); }} className="text-sm text-blue-600 hover:underline">
          Use a different email
        </button>
      </div>
    );
  }

  if (step === 1) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-gray-500">
          HealthCoach is invite-only. Enter the invite code you received to get started.
        </p>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Invite code</label>
          <input
            type="text"
            value={inviteCode}
            onChange={(e) => { setInviteCode(e.target.value.toUpperCase()); setInviteError(""); }}
            placeholder="e.g. AB12CD"
            className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 tracking-widest font-mono uppercase"
            onKeyDown={(e) => e.key === "Enter" && handleValidateInvite()}
          />
        </div>
        {inviteError && (
          <div className="px-4 py-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {inviteError}
          </div>
        )}
        <button
          onClick={handleValidateInvite}
          disabled={validating}
          className="w-full px-4 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-xl hover:bg-blue-700 disabled:opacity-60 transition-all"
        >
          {validating ? "Checking…" : "Continue →"}
        </button>
      </div>
    );
  }

  // Step 2
  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-green-50 border border-green-200 rounded-xl text-sm text-green-700">
        <CheckCircle className="w-4 h-4 flex-shrink-0" />
        Invite code accepted — choose how to sign up
      </div>

      {googleError && (
        <div className="px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
          {googleError}
        </div>
      )}

      {/* Google */}
      <button
        onClick={handleGoogleSignUp}
        disabled={googleLoading}
        className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white border-2 border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-all shadow-sm disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {!googleLoading ? (
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
        {googleLoading ? "Redirecting…" : "Sign up with Google"}
      </button>

      {/* Divider */}
      <div className="flex items-center gap-3">
        <div className="flex-1 h-px bg-gray-200" />
        <span className="text-xs text-gray-400">or</span>
        <div className="flex-1 h-px bg-gray-200" />
      </div>

      {/* Magic link */}
      {!showMagicLink ? (
        <button
          onClick={() => setShowMagicLink(true)}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 border border-gray-200 rounded-xl text-sm text-gray-600 hover:bg-white transition-all bg-gray-50"
        >
          <Mail className="w-4 h-4" />
          Sign up with email link instead
        </button>
      ) : (
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email address</label>
            <input
              type="email"
              value={magicEmail}
              onChange={(e) => { setMagicEmail(e.target.value); setMagicError(""); }}
              placeholder="you@example.com"
              className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              onKeyDown={(e) => e.key === "Enter" && handleSendSignUpLink()}
            />
          </div>
          {magicError && (
            <div className="px-4 py-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
              {magicError}
            </div>
          )}
          <button
            onClick={handleSendSignUpLink}
            disabled={magicLoading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white text-sm font-medium rounded-xl hover:bg-indigo-700 disabled:opacity-60 transition-all"
          >
            <Mail className="w-4 h-4" />
            {magicLoading ? "Sending…" : "Send sign-up link"}
          </button>
        </div>
      )}

      <button
        onClick={() => setStep(1)}
        className="w-full text-center text-xs text-gray-400 hover:text-gray-600 transition-colors py-1"
      >
        ← Use a different invite code
      </button>
    </div>
  );
}

// ── Main Login page ──────────────────────────────────────────────────────────
export default function Login() {
  const [searchParams] = useSearchParams();
  // If redirected back from OAuth with invite_required, go straight to Sign Up tab
  const defaultTab: Tab = searchParams.get("error") === "invite_required" ? "signup" : "signin";
  const [tab, setTab] = useState<Tab>(defaultTab);

  return (
    <div className="min-h-screen flex flex-col lg:grid lg:grid-cols-2">
      {/* Left panel — branding */}
      <div className="hidden lg:flex flex-col items-center justify-center px-16 text-white" style={{ background: "#0a215a" }}>
        <img src="/logo.png" alt="Health Coach" className="w-52 h-auto mb-6" />
        <p className="text-blue-200/70 text-lg text-center mb-12 max-w-sm">
          Your personal AI health &amp; fitness coach.
        </p>
        <div className="grid grid-cols-1 gap-5 w-full max-w-sm">
          {[
            { label: "Training", value: "Personal Coach", desc: "Optimised weekly plans" },
            { label: "Nutrition", value: "Personal Nutritionist", desc: "Meal plans + Food log + Macros Breakdown" },
            { label: "Insights", value: "Health Advisor", desc: "Key health metrics and insights" },
          ].map(({ label, value, desc }) => (
            <div key={label} className="rounded-2xl px-5 py-4 backdrop-blur-sm border border-white/10" style={{ background: "rgba(255,255,255,0.06)" }}>
              <p className="text-xs uppercase tracking-wider mb-0.5" style={{ color: "#4ade80" }}>{label}</p>
              <p className="font-semibold">{value}</p>
              <p className="text-sm text-gray-400 mt-0.5">{desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel */}
      <div className="flex flex-col items-center justify-center bg-gray-50 px-8 py-12">
        {/* Mobile logo */}
        <div className="flex lg:hidden items-center justify-center mb-10">
          <img src="/logo.png" alt="Health Coach" className="w-36 h-auto" />
        </div>

        <div className="w-full max-w-sm">
          <div className="mb-6">
            <h1 className="text-2xl font-bold text-gray-900 mb-4">Welcome</h1>

            {/* Sign In / Sign Up tabs */}
            <div className="flex rounded-xl border border-gray-200 overflow-hidden bg-white">
              <button
                onClick={() => setTab("signin")}
                className={`flex-1 py-2.5 text-sm font-medium transition-colors ${
                  tab === "signin"
                    ? "bg-blue-600 text-white"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                Sign In
              </button>
              <button
                onClick={() => setTab("signup")}
                className={`flex-1 py-2.5 text-sm font-medium transition-colors ${
                  tab === "signup"
                    ? "bg-blue-600 text-white"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                Sign Up
              </button>
            </div>
          </div>

          {tab === "signin" ? <SignInTab /> : <SignUpTab />}
        </div>
      </div>
    </div>
  );
}
