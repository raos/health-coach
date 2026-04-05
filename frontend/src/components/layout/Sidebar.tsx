import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Dumbbell,
  Salad,
  HeartPulse,
  Settings,
  LogOut,
  Moon,
  Sun,
  ClipboardCheck,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useState } from "react";
import { getStoredUser } from "../auth/ProtectedRoute";
import { useDarkMode } from "../../hooks/useDarkMode";
import { getProfile } from "../../api/profile";
import type { UserProfile } from "../../types";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/coach", icon: Dumbbell, label: "Coach" },
  { to: "/nutrition", icon: Salad, label: "Nutrition" },
  { to: "/health", icon: HeartPulse, label: "Health" },
  { to: "/checkin", icon: ClipboardCheck, label: "Check-In" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const user = getStoredUser();
  const { dark, toggle } = useDarkMode();
  const [profile, setProfile] = useState<UserProfile | null>(null);

  useEffect(() => {
    getProfile().then(setProfile).catch(() => {});
  }, []);

  function handleLogout() {
    localStorage.removeItem("auth_token");
    navigate("/login", { replace: true });
  }

  return (
    <aside className="w-64 min-h-screen flex flex-col text-white" style={{ background: "linear-gradient(180deg, #071328 0%, #0a1a35 60%, #0d2040 100%)" }}>
      {/* Logo */}
      <div className="flex items-center justify-center px-4 py-5 border-b border-white/10">
        <img src="/logo.png" alt="Health Coach" className="w-60 h-auto" />
      </div>

      {/* User */}
      <div className="px-6 py-4 border-b border-white/10">
        <div className="flex items-center gap-3">
          {user?.picture ? (
            <img
              src={user.picture}
              alt={user.name}
              className="w-8 h-8 rounded-full ring-2 ring-sky-400"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="w-8 h-8 rounded-full bg-sky-600 flex items-center justify-center text-xs font-bold">
              {user?.name?.[0] ?? "S"}
            </div>
          )}
          <div className="min-w-0">
            <p className="text-sm font-medium truncate">{user?.name ?? "Sandeep Rao"}</p>
            <p className="text-xs text-gray-400 truncate">{user?.email ?? ""}</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 text-sm font-medium transition-colors ${
                isActive
                  ? "text-white"
                  : "text-blue-200/70 hover:text-white hover:bg-white/10"
              }`
            }
            style={({ isActive }) => isActive ? { background: "linear-gradient(90deg, #1a6b3c 0%, #0e7490 100%)" } : {}}
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}
        {user?.is_admin && (
          <NavLink
            to="/admin"
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg mb-1 text-sm font-medium transition-colors mt-2 border-t border-white/10 pt-3 ${
                isActive
                  ? "text-white"
                  : "text-blue-200/50 hover:text-white hover:bg-white/10"
              }`
            }
            style={({ isActive }) => isActive ? { background: "linear-gradient(90deg, #6d28d9 0%, #4338ca 100%)" } : {}}
          >
            <ShieldCheck className="w-4 h-4" />
            Admin
          </NavLink>
        )}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-white/10 space-y-3">
        {(profile?.bf_goal_pct || profile?.vo2max_goal) && (
          <div className="px-2">
            {profile.bf_goal_pct && (
              <p className="text-xs text-blue-200/40">
                Goal: {profile.bf_goal_pct}% BF
                {profile.goal_date
                  ? ` by ${new Date(profile.goal_date).toLocaleDateString("en-US", { month: "short", year: "numeric" })}`
                  : ""}
              </p>
            )}
            {profile.vo2max_goal && (
              <p className="text-xs text-blue-200/40 mt-0.5">
                VO₂ Max goal: {profile.vo2max_goal}+
              </p>
            )}
          </div>
        )}
        <button
          onClick={toggle}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-blue-200/60 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
        >
          {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          {dark ? "Light mode" : "Dark mode"}
        </button>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-blue-200/60 hover:text-white hover:bg-white/10 rounded-lg transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
