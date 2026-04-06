import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Activity } from "lucide-react";

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  // Guard against React StrictMode double-invocation of effects
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    handled.current = true;

    const token = searchParams.get("token");
    if (token) {
      localStorage.setItem("auth_token", token);
      navigate("/", { replace: true });
    } else {
      navigate("/login?error=missing_token", { replace: true });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 flex items-center justify-center">
      <div className="text-center">
        <div className="flex items-center justify-center gap-3 mb-4">
          <Activity className="w-7 h-7 text-blue-400 animate-pulse" />
          <span className="text-xl font-bold text-white">Health Coach</span>
        </div>
        <p className="text-gray-400 text-sm">Signing you in…</p>
      </div>
    </div>
  );
}
