import { BrowserRouter, Routes, Route } from "react-router-dom";
import Sidebar from "./components/layout/Sidebar";
import ProtectedRoute from "./components/auth/ProtectedRoute";
import Login from "./pages/Login";
import AuthCallback from "./pages/AuthCallback";
import MagicLinkCallback from "./pages/MagicLinkCallback";
import Onboarding from "./pages/Onboarding";
import Dashboard from "./pages/Dashboard";
import Coach from "./pages/Coach";
import Nutrition from "./pages/Nutrition";
import HealthAdvisor from "./pages/HealthAdvisor";
import Settings from "./pages/Settings";
import WeeklyCheckin from "./pages/WeeklyCheckin";
import Admin from "./pages/Admin";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes — no sidebar, no auth */}
        <Route path="/login" element={<Login />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/auth/magic-link" element={<MagicLinkCallback />} />

        {/* Onboarding — auth required but no sidebar */}
        <Route
          path="/onboarding"
          element={
            <ProtectedRoute>
              <Onboarding />
            </ProtectedRoute>
          }
        />

        {/* Protected routes — require sign-in */}
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <div className="flex min-h-screen bg-gray-50 dark:bg-gray-900" style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}>
                <Sidebar />
                <main className="flex-1 overflow-hidden">
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/coach" element={<Coach />} />
                    <Route path="/nutrition" element={<Nutrition />} />
                    <Route path="/health" element={<HealthAdvisor />} />
                    <Route path="/checkin" element={<WeeklyCheckin />} />
                    <Route path="/settings" element={<Settings />} />
                    <Route path="/admin" element={<Admin />} />
                  </Routes>
                </main>
              </div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
