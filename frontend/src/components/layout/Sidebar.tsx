import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Dumbbell,
  Salad,
  HeartPulse,
  Settings,
  Activity,
  LogOut,
  Moon,
  Sun,
} from "lucide-react";
import { getStoredUser } from "../auth/ProtectedRoute";
import { useDarkMode } from "../../hooks/useDarkMode";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/coach", icon: Dumbbell, label: "Coach" },
  { to: "/nutrition", icon: Salad, label: "Nutrition" },
  { to: "/health", icon: HeartPulse, label: "Health" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export default function Sidebar() {
  const navigate = useNavigate();
  const user = getStoredUser();
  const { dark, toggle } = useDarkMode();

  function handleLogout() {
    localStorage.removeItem("auth_token");
    navigate("/login", { replace: true });
  }

  return (
    <aside className="w-64 min-h-screen bg-gray-900 text-white flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2 px-6 py-5 border-b border-gray-700">
        <Activity className="w-6 h-6 text-blue-400" />
        <span className="font-bold text-lg tracking-tight">HealthCoach</span>
      </div>

      {/* User */}
      <div className="px-6 py-4 border-b border-gray-700">
        <div className="flex items-center gap-3">
          {user?.picture ? (
            <img
              src={user.picture}
              alt={user.name}
              className="w-8 h-8 rounded-full ring-2 ring-blue-500"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-xs font-bold">
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
                  ? "bg-blue-600 text-white"
                  : "text-gray-300 hover:bg-gray-800 hover:text-white"
              }`
            }
          >
            <Icon className="w-4 h-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-4 py-4 border-t border-gray-700 space-y-3">
        <div className="px-2">
          <p className="text-xs text-gray-500">Goal: 18% BF by Dec 2026</p>
          <p className="text-xs text-gray-500 mt-0.5">VO₂ Max: 45 → 50+</p>
        </div>
        <button
          onClick={toggle}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
        >
          {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          {dark ? "Light mode" : "Dark mode"}
        </button>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
