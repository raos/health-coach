import { useEffect, useRef, useState } from "react";
import { Dumbbell, Send, RefreshCw, ChevronDown, ChevronUp, Mail, Upload, CheckCircle, AlertCircle } from "lucide-react";
import StrengthProgress from "../components/coach/StrengthProgress";
import PageWrapper from "../components/layout/PageWrapper";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorBanner from "../components/shared/ErrorBanner";
import MarkdownRenderer from "../components/shared/MarkdownRenderer";
import { getLatestTrainingPlan, generateTrainingPlan, emailTrainingPlan, chatWithCoach } from "../api/coach";
import { pushRoutine } from "../api/hevy";
import type { PushRoutineResult } from "../api/hevy";
import type { TrainingPlan } from "../types";
import { format, parseISO } from "date-fns";

interface ParsedPlan {
  week_start: string;
  weekly_overview: string;
  days: {
    day: string;
    type: string;
    focus: string;
    exercises: {
      name: string;
      tonal_setup?: string;
      sets: number;
      reps: string;
      rest_seconds?: number;
      coaching_note?: string;
    }[];
    session_notes?: string;
  }[];
  weekly_notes?: string;
}

const STRENGTH_TYPES = ["Upper A", "Upper B", "Lower A", "Lower B", "Strength", "Full Body"];

function DayCard({ day }: { day: ParsedPlan["days"][0] }) {
  const [expanded, setExpanded] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [pushResult, setPushResult] = useState<PushRoutineResult | null>(null);
  const [pushError, setPushError] = useState("");

  const isRest = day.type === "Rest";
  const isStrength = STRENGTH_TYPES.some((t) => day.type.includes(t));

  async function handlePushToHevy(e: React.MouseEvent) {
    e.stopPropagation();
    setPushing(true);
    setPushResult(null);
    setPushError("");
    try {
      const title = `${day.day} — ${day.type}`;
      const exercises = day.exercises.map((ex) => ({
        name: ex.name,
        sets: ex.sets,
        reps: ex.reps,
        rest_seconds: ex.rest_seconds ?? 90,
        coaching_note: ex.coaching_note ?? "",
      }));
      const result = await pushRoutine(title, exercises);
      setPushResult(result);
    } catch (err: any) {
      setPushError(err?.response?.data?.detail || "Failed to push to Hevy.");
    } finally {
      setPushing(false);
    }
  }

  return (
    <div className={`border rounded-lg overflow-hidden ${isRest ? "bg-gray-50 dark:bg-gray-700 border-gray-200 dark:border-gray-600" : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700"}`}>
      <button
        onClick={() => !isRest && setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="font-semibold text-gray-900 dark:text-gray-100 whitespace-nowrap">{day.day}</span>
          <span className="text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-600 px-2 py-0.5 rounded-full whitespace-nowrap">{day.type}</span>
        </div>
        <div className="flex flex-1 items-center justify-between gap-2 min-w-0">
          <span className="text-sm text-gray-600 dark:text-gray-400 hidden sm:block truncate">{day.focus}</span>
          <div className="flex items-center gap-2 flex-shrink-0">
            {isStrength && (
              <button
                onClick={handlePushToHevy}
                disabled={pushing}
                title="Send to Hevy as a routine"
                className="flex items-center gap-1 px-2 py-1 text-xs bg-orange-50 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400 border border-orange-200 dark:border-orange-700 rounded-md hover:bg-orange-100 dark:hover:bg-orange-900/50 disabled:opacity-50 transition-colors"
              >
                <Upload className="w-3 h-3" />
                {pushing ? "Sending…" : "Send to Hevy"}
              </button>
            )}
            {!isRest && (expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />)}
          </div>
        </div>
      </button>

      {/* Push result banner */}
      {pushResult && (
        <div className="px-4 py-2 border-t border-orange-100 dark:border-orange-800 bg-orange-50 dark:bg-orange-900/20">
          <div className="flex items-start gap-2">
            <CheckCircle className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" />
            <div className="text-xs text-gray-700 dark:text-gray-300">
              <span className="font-medium text-green-600 dark:text-green-400">Routine created in Hevy!</span>
              {" "}{pushResult.matched.length} exercise{pushResult.matched.length !== 1 ? "s" : ""} added.
              {pushResult.unmatched.length > 0 && (
                <span className="text-amber-600 dark:text-amber-400">
                  {" "}Could not match: {pushResult.unmatched.join(", ")}.
                </span>
              )}
            </div>
          </div>
        </div>
      )}
      {pushError && (
        <div className="px-4 py-2 border-t border-red-100 dark:border-red-800 bg-red-50 dark:bg-red-900/20">
          <div className="flex items-center gap-2 text-xs text-red-600 dark:text-red-400">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            {pushError}
          </div>
        </div>
      )}

      {expanded && !isRest && (
        <div className="px-4 pb-4 border-t border-gray-100 dark:border-gray-600">
          {day.session_notes && (
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-3 mb-3 italic">{day.session_notes}</p>
          )}
          <div className="space-y-2">
            {day.exercises.map((ex, i) => (
              <div key={i} className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-sm text-gray-900 dark:text-gray-100">{ex.name}</p>
                    {ex.tonal_setup && <p className="text-xs text-blue-600 dark:text-blue-400 mt-0.5">{ex.tonal_setup}</p>}
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-300">{ex.sets} × {ex.reps}</p>
                    {ex.rest_seconds && <p className="text-xs text-gray-400 dark:text-gray-500">{ex.rest_seconds}s rest</p>}
                  </div>
                </div>
                {ex.coaching_note && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1.5 border-t border-gray-200 dark:border-gray-600 pt-1.5">{ex.coaching_note}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
}

function DayCounter({ label, value, onDec, onInc, color }: {
  label: string; value: number; onDec: () => void; onInc: () => void; color: string;
}) {
  return (
    <div className="flex flex-col items-center gap-1">
      <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">{label}</span>
      <div className="flex items-center gap-1.5">
        <button onClick={onDec} className="w-6 h-6 rounded-full border border-gray-300 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-center text-sm leading-none">−</button>
        <span className={`w-6 text-center font-bold text-sm ${color}`}>{value}</span>
        <button onClick={onInc} className="w-6 h-6 rounded-full border border-gray-300 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-center text-sm leading-none">+</button>
      </div>
    </div>
  );
}

export default function Coach() {
  const [plan, setPlan] = useState<TrainingPlan | null>(null);
  const [parsedPlan, setParsedPlan] = useState<ParsedPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [emailing, setEmailing] = useState(false);
  const [emailStatus, setEmailStatus] = useState("");
  const [error, setError] = useState("");
  const [strengthDays, setStrengthDays] = useState(4);
  const [cardioDays, setCardioDays] = useState(2);
  const [restDays, setRestDays] = useState(1);

  const totalDays = strengthDays + cardioDays + restDays;

  function clampDay(setter: (n: number) => void, val: number, min: number, max: number) {
    setter(Math.max(min, Math.min(max, val)));
  }

  const [messages, setMessages] = useState<ChatMsg[]>([
    { role: "assistant", content: "Hi! I'm your personal coach. Generate a training plan above or ask me anything about your workouts, Tonal exercises, or training goals." }
  ]);
  const [input, setInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getLatestTrainingPlan()
      .then((p) => {
        if (p) {
          setPlan(p);
          try { setParsedPlan(JSON.parse(p.plan_json)); } catch {}
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleEmail() {
    setEmailing(true);
    setEmailStatus("");
    setError("");
    try {
      await emailTrainingPlan();
      setEmailStatus("Sent!");
      setTimeout(() => setEmailStatus(""), 3000);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to send email. Check SMTP settings.");
    } finally {
      setEmailing(false);
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    setError("");
    try {
      const p = await generateTrainingPlan({ strength_days: strengthDays, cardio_days: cardioDays, rest_days: restDays });
      setPlan(p);
      try { setParsedPlan(JSON.parse(p.plan_json)); } catch {}
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to generate plan. Check your Anthropic API key in Settings.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleChat(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || chatLoading) return;
    const msg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
    setChatLoading(true);

    try {
      const data = await chatWithCoach(msg, "default");
      setMessages((prev) => [...prev, { role: "assistant", content: data.response }]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, I couldn't connect to the coaching service. Make sure the backend is running." }]);
    } finally {
      setChatLoading(false);
    }
  }

  return (
    <PageWrapper
      title="Personal Coach"
      subtitle="Tonal-optimized training plans · Eugene Teo & Jeff Nippard methodology"
      actions={
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3 px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg">
            <DayCounter label="Strength" value={strengthDays} onDec={() => clampDay(setStrengthDays, strengthDays - 1, 2, 6)} onInc={() => clampDay(setStrengthDays, strengthDays + 1, 2, 6)} color="text-blue-600" />
            <div className="w-px h-8 bg-gray-200 dark:bg-gray-600" />
            <DayCounter label="Cardio" value={cardioDays} onDec={() => clampDay(setCardioDays, cardioDays - 1, 0, 4)} onInc={() => clampDay(setCardioDays, cardioDays + 1, 0, 4)} color="text-green-600" />
            <div className="w-px h-8 bg-gray-200 dark:bg-gray-600" />
            <DayCounter label="Rest" value={restDays} onDec={() => clampDay(setRestDays, restDays - 1, 1, 3)} onInc={() => clampDay(setRestDays, restDays + 1, 1, 3)} color="text-orange-500" />
            <div className="w-px h-8 bg-gray-200 dark:bg-gray-600" />
            <span className={`text-xs font-medium ${totalDays === 7 ? "text-gray-400 dark:text-gray-500" : "text-red-500"}`}>
              {totalDays}/7 days
            </span>
          </div>
          <button
            onClick={handleGenerate}
            disabled={generating || totalDays !== 7}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${generating ? "animate-spin" : ""}`} />
            {generating ? "Generating..." : "Generate New Plan"}
          </button>
          <button
            onClick={handleEmail}
            disabled={emailing || !plan}
            className="flex items-center gap-2 px-4 py-2 bg-gray-700 text-white text-sm font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50 transition-colors"
          >
            <Mail className="w-4 h-4" />
            {emailing ? "Sending..." : emailStatus || "Email Plan"}
          </button>
        </div>
      }
    >
      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}

      {/* Strength Progress */}
      <div className="mb-6">
        <StrengthProgress />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Training Plan */}
        <div>
          <h2 className="font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
            <Dumbbell className="w-4 h-4 text-blue-600" />
            {parsedPlan ? `Week of ${format(parseISO(parsedPlan.week_start), "MMM d, yyyy")}` : "Training Plan"}
          </h2>

          {loading && <LoadingSpinner />}

          {!loading && !plan && (
            <div className="border-2 border-dashed border-gray-200 dark:border-gray-600 rounded-xl p-8 text-center">
              <Dumbbell className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
              <p className="text-gray-500 dark:text-gray-400 text-sm mb-4">No training plan yet.</p>
              <button onClick={handleGenerate} disabled={generating || totalDays !== 7} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">
                {generating ? "Generating..." : "Generate Your First Plan"}
              </button>
            </div>
          )}

          {parsedPlan && (
            <div className="space-y-2">
              {parsedPlan.weekly_overview && (
                <p className="text-sm text-gray-600 dark:text-gray-400 bg-blue-50 dark:bg-blue-900/30 border border-blue-100 dark:border-blue-700 rounded-lg p-3 mb-3">{parsedPlan.weekly_overview}</p>
              )}
              {parsedPlan.days.map((day) => (
                <DayCard key={day.day} day={day} />
              ))}
              {parsedPlan.weekly_notes && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-2 italic">{parsedPlan.weekly_notes}</p>
              )}
            </div>
          )}
        </div>

        {/* Chat */}
        <div className="flex flex-col bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden" style={{ height: "600px" }}>
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
            <h2 className="font-semibold text-gray-900 dark:text-gray-100 text-sm">Coach Chat</h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-xs lg:max-w-sm rounded-2xl px-4 py-2.5 text-sm ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-br-sm"
                    : "bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-bl-sm"
                }`}>
                  {msg.role === "assistant" ? (
                    <MarkdownRenderer content={msg.content} />
                  ) : (
                    msg.content
                  )}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 dark:bg-gray-700 rounded-2xl rounded-bl-sm px-4 py-3">
                  <LoadingSpinner size="sm" />
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <form onSubmit={handleChat} className="p-3 border-t border-gray-200 dark:border-gray-700 flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask your coach..."
              className="flex-1 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400"
            />
            <button
              type="submit"
              disabled={!input.trim() || chatLoading}
              className="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </PageWrapper>
  );
}
