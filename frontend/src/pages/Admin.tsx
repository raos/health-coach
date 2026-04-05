import { useState, useEffect } from "react";
import { Users, BarChart2, ClipboardList, Shield, ToggleLeft, ToggleRight, RefreshCw } from "lucide-react";
import client from "../api/client";

interface AdminUser {
  id: string;
  email: string;
  name: string;
  auth_provider: string;
  is_active: boolean;
  is_admin: boolean;
  onboarding_complete: boolean;
  weekly_email_enabled: boolean;
  training_device: string | null;
  dietary_preference: string | null;
  invite_code_used: string | null;
  mcp_api_key: string | null;
  created_at: string | null;
}

interface Stats {
  total_users: number;
  active_users: number;
  onboarded_users: number;
  total_meal_plans: number;
  total_training_plans: number;
  total_nutrition_logs: number;
  strava_connected: number;
  hevy_connected: number;
  total_workouts: number;
  total_strava_activities: number;
}

interface InviteCode {
  id: string;
  code: string;
  max_uses: number;
  use_count: number;
  uses_remaining: number;
  expires_at: string | null;
  used_by: string | null;
  used_at: string | null;
}

type Tab = "users" | "invites" | "stats";

export default function Admin() {
  const [tab, setTab] = useState<Tab>("users");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [invites, setInvites] = useState<InviteCode[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [newCode, setNewCode] = useState("");
  const [newMaxUses, setNewMaxUses] = useState(1);
  const [newExpireDays, setNewExpireDays] = useState(0);
  const [creating, setCreating] = useState(false);

  async function loadTab(t: Tab) {
    setLoading(true);
    setError("");
    try {
      if (t === "users") {
        const res = await client.get("/api/admin/users");
        setUsers(res.data);
      } else if (t === "stats") {
        const res = await client.get("/api/admin/stats");
        setStats(res.data);
      } else if (t === "invites") {
        const res = await client.get("/api/auth/invite-codes");
        setInvites(res.data);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to load data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadTab(tab); }, [tab]);

  async function toggleActive(user: AdminUser) {
    try {
      const res = await client.patch(`/api/admin/users/${user.id}`, { is_active: !user.is_active });
      setUsers((prev) => prev.map((u) => (u.id === user.id ? res.data : u)));
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to update user.");
    }
  }

  async function toggleAdmin(user: AdminUser) {
    try {
      const res = await client.patch(`/api/admin/users/${user.id}`, { is_admin: !user.is_admin });
      setUsers((prev) => prev.map((u) => (u.id === user.id ? res.data : u)));
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to update user.");
    }
  }

  async function createInvite() {
    setCreating(true);
    setError("");
    try {
      const res = await client.post("/api/auth/invite-codes", {
        code: newCode.trim().toUpperCase() || "",
        max_uses: newMaxUses,
        expires_days: newExpireDays,
      });
      setInvites((prev) => [res.data, ...prev]);
      setNewCode("");
      setNewMaxUses(1);
      setNewExpireDays(0);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Failed to create invite code.");
    } finally {
      setCreating(false);
    }
  }

  const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "users", label: "Users", icon: <Users className="w-4 h-4" /> },
    { id: "invites", label: "Invite Codes", icon: <Shield className="w-4 h-4" /> },
    { id: "stats", label: "Stats", icon: <BarChart2 className="w-4 h-4" /> },
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-6 flex items-center gap-3">
        <ClipboardList className="w-7 h-7 text-blue-600" />
        <h1 className="text-2xl font-bold text-gray-900">Admin Panel</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors ${
              tab === t.id
                ? "text-blue-600 border-b-2 border-blue-600 bg-white"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {t.icon}
            {t.label}
          </button>
        ))}
        <button
          onClick={() => loadTab(tab)}
          className="ml-auto p-2 text-gray-400 hover:text-gray-600"
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      {error && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Users Tab */}
      {tab === "users" && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-700">User</th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">Provider</th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">Onboarded</th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">Invite</th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">Joined</th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">Active</th>
                <th className="text-left px-4 py-3 font-medium text-gray-700">Admin</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {users.map((u) => (
                <tr key={u.id} className={`hover:bg-gray-50 ${!u.is_active ? "opacity-50" : ""}`}>
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-900">{u.name || "—"}</p>
                    <p className="text-gray-500 text-xs">{u.email}</p>
                  </td>
                  <td className="px-4 py-3 text-gray-600 capitalize">{u.auth_provider}</td>
                  <td className="px-4 py-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      u.onboarding_complete ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
                    }`}>
                      {u.onboarding_complete ? "Done" : "Pending"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-600 font-mono text-xs">{u.invite_code_used || "—"}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => toggleActive(u)} className="text-gray-400 hover:text-gray-700">
                      {u.is_active
                        ? <ToggleRight className="w-5 h-5 text-green-500" />
                        : <ToggleLeft className="w-5 h-5" />}
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => toggleAdmin(u)} className="text-gray-400 hover:text-gray-700">
                      {u.is_admin
                        ? <ToggleRight className="w-5 h-5 text-purple-500" />
                        : <ToggleLeft className="w-5 h-5" />}
                    </button>
                  </td>
                </tr>
              ))}
              {!loading && users.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-gray-400">No users yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Invite Codes Tab */}
      {tab === "invites" && (
        <div className="space-y-4">
          {/* Create form */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
            <h2 className="font-semibold text-gray-900 mb-3">Generate Invite Code</h2>
            <div className="flex flex-wrap gap-3 items-end">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Code (leave blank to auto-generate)</label>
                <input
                  type="text"
                  value={newCode}
                  onChange={(e) => setNewCode(e.target.value.toUpperCase())}
                  placeholder="e.g. FRIEND01"
                  className="px-3 py-2 text-sm border border-gray-200 rounded-lg font-mono tracking-widest w-36"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Max uses</label>
                <input
                  type="number"
                  min={1}
                  value={newMaxUses}
                  onChange={(e) => setNewMaxUses(Number(e.target.value))}
                  className="px-3 py-2 text-sm border border-gray-200 rounded-lg w-20"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Expires in days (0 = never)</label>
                <input
                  type="number"
                  min={0}
                  value={newExpireDays}
                  onChange={(e) => setNewExpireDays(Number(e.target.value))}
                  className="px-3 py-2 text-sm border border-gray-200 rounded-lg w-24"
                />
              </div>
              <button
                onClick={createInvite}
                disabled={creating}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-60"
              >
                {creating ? "Creating…" : "Create Code"}
              </button>
            </div>
          </div>

          {/* Invite codes table */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-700">Code</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-700">Uses</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-700">Expires</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-700">Used by</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-700">Used at</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {invites.map((inv) => (
                  <tr key={inv.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono font-bold tracking-widest text-blue-700">{inv.code}</td>
                    <td className="px-4 py-3 text-gray-600">
                      {inv.use_count}/{inv.max_uses}
                      {inv.uses_remaining === 0 && (
                        <span className="ml-2 text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">exhausted</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {inv.expires_at ? new Date(inv.expires_at).toLocaleDateString() : "Never"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{inv.used_by ? inv.used_by.slice(0, 8) + "…" : "—"}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {inv.used_at ? new Date(inv.used_at).toLocaleDateString() : "—"}
                    </td>
                  </tr>
                ))}
                {!loading && invites.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-gray-400">No invite codes yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Stats Tab */}
      {tab === "stats" && stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {[
            { label: "Total users", value: stats.total_users },
            { label: "Active users", value: stats.active_users },
            { label: "Onboarded users", value: stats.onboarded_users },
            { label: "Meal plans generated", value: stats.total_meal_plans },
            { label: "Training plans generated", value: stats.total_training_plans },
            { label: "Nutrition log entries", value: stats.total_nutrition_logs },
            { label: "Strava connected", value: stats.strava_connected },
            { label: "Hevy API key set", value: stats.hevy_connected },
            { label: "Total workouts (Hevy)", value: stats.total_workouts },
            { label: "Total Strava activities", value: stats.total_strava_activities },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <p className="text-2xl font-bold text-gray-900">{value}</p>
              <p className="text-sm text-gray-500 mt-0.5">{label}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
