import { useEffect, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Activity } from "lucide-react";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/**
 * Handles clicks on magic-link sign-in emails.
 * The email link points to /auth/magic-link?token=<raw_token>.
 * We redirect the browser to the backend verify endpoint which
 * validates the token and issues a JWT redirect to /auth/callback.
 */
export default function MagicLinkCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;

    const token = searchParams.get("token");
    if (!token) {
      navigate("/login?error=invalid_magic_link", { replace: true });
      return;
    }
    // Hand off to backend — it validates the token and 302-redirects to /auth/callback?token=<jwt>
    window.location.href = `${API_BASE}/api/auth/magic-link/verify?token=${encodeURIComponent(token)}`;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 flex items-center justify-center">
      <div className="text-center">
        <div className="flex items-center justify-center gap-3 mb-4">
          <Activity className="w-7 h-7 text-blue-400 animate-pulse" />
          <span className="text-xl font-bold text-white">HealthCoach</span>
        </div>
        <p className="text-gray-400 text-sm">Verifying sign-in link…</p>
      </div>
    </div>
  );
}
