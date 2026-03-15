import { useEffect, useRef, useState } from "react";
import { Dumbbell, Send, RefreshCw, ChevronDown, ChevronUp, Mail } from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorBanner from "../components/shared/ErrorBanner";
import MarkdownRenderer from "../components/shared/MarkdownRenderer";
import { getLatestTrainingPlan, generateTrainingPlan, emailTrainingPlan } from "../api/coach";
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

function DayCard({ day }: { day: ParsedPlan["days"][0] }) {
  const [expanded, setExpanded] = useState(false);
  const isRest = day.type === "Rest";

  return (
    <div className={`border rounded-lg overflow-hidden ${isRest ? "bg-gray-50 border-gray-200" : "bg-white border-gray-200"}`}>
      <button
        onClick={() => !isRest && setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="font-semibold text-gray-900 whitespace-nowrap">{day.day}</span>
          <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full whitespace-nowrap">{day.type}</span>
        </div>
        <div className="flex flex-1 items-center justify-between gap-2 min-w-0">
          <span className="text-sm text-gray-600 hidden sm:block truncate">{day.focus}</span>
          {!isRest && (expanded ? <ChevronUp className="w-4 h-4 text-gray-400 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />)}
        </div>
      </button>

      {expanded && !isRest && (
        <div className="px-4 pb-4 border-t border-gray-100">
          {day.session_notes && (
            <p className="text-sm text-gray-600 mt-3 mb-3 italic">{day.session_notes}</p>
          )}
          <div className="space-y-2">
            {day.exercises.map((ex, i) => (
              <div key={i} className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-sm text-gray-900">{ex.name}</p>
                    {ex.tonal_setup && <p className="text-xs text-blue-600 mt-0.5">{ex.tonal_setup}</p>}
                  </div>
                  <div className="text-right flex-shrink-0">
                    <p className="text-sm font-medium text-gray-700">{ex.sets} × {ex.reps}</p>
                    {ex.rest_seconds && <p className="text-xs text-gray-400">{ex.rest_seconds}s rest</p>}
                  </div>
                </div>
                {ex.coaching_note && (
                  <p className="text-xs text-gray-500 mt-1.5 border-t border-gray-200 pt-1.5">{ex.coaching_note}</p>
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
      <span className="text-xs text-gray-500 font-medium">{label}</span>
      <div className="flex items-center gap-1.5">
        <button onClick={onDec} className="w-6 h-6 rounded-full border border-gray-300 text-gray-500 hover:bg-gray-100 flex items-center justify-center text-sm leading-none">−</button>
        <span className={`w-6 text-center font-bold text-sm ${color}`}>{value}</span>
        <button onClick={onInc} className="w-6 h-6 rounded-full border border-gray-300 text-gray-500 hover:bg-gray-100 flex items-center justify-center text-sm leading-none">+</button>
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
      const response = await fetch("http://localhost:8000/api/coach/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: msg, session_id: "default" }),
      });
      const data = await response.json();
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
          <div className="flex items-center gap-3 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg">
            <DayCounter label="Strength" value={strengthDays} onDec={() => clampDay(setStrengthDays, strengthDays - 1, 2, 6)} onInc={() => clampDay(setStrengthDays, strengthDays + 1, 2, 6)} color="text-blue-600" />
            <div className="w-px h-8 bg-gray-200" />
            <DayCounter label="Cardio" value={cardioDays} onDec={() => clampDay(setCardioDays, cardioDays - 1, 0, 4)} onInc={() => clampDay(setCardioDays, cardioDays + 1, 0, 4)} color="text-green-600" />
            <div className="w-px h-8 bg-gray-200" />
            <DayCounter label="Rest" value={restDays} onDec={() => clampDay(setRestDays, restDays - 1, 1, 3)} onInc={() => clampDay(setRestDays, restDays + 1, 1, 3)} color="text-orange-500" />
            <div className="w-px h-8 bg-gray-200" />
            <span className={`text-xs font-medium ${totalDays === 7 ? "text-gray-400" : "text-red-500"}`}>
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Training Plan */}
        <div>
          <h2 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
            <Dumbbell className="w-4 h-4 text-blue-600" />
            {parsedPlan ? `Week of ${format(parseISO(parsedPlan.week_start), "MMM d, yyyy")}` : "Training Plan"}
          </h2>

          {loading && <LoadingSpinner />}

          {!loading && !plan && (
            <div className="border-2 border-dashed border-gray-200 rounded-xl p-8 text-center">
              <Dumbbell className="w-8 h-8 text-gray-300 mx-auto mb-3" />
              <p className="text-gray-500 text-sm mb-4">No training plan yet.</p>
              <button onClick={handleGenerate} disabled={generating || totalDays !== 7} className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">
                {generating ? "Generating..." : "Generate Your First Plan"}
              </button>
            </div>
          )}

          {parsedPlan && (
            <div className="space-y-2">
              {parsedPlan.weekly_overview && (
                <p className="text-sm text-gray-600 bg-blue-50 border border-blue-100 rounded-lg p-3 mb-3">{parsedPlan.weekly_overview}</p>
              )}
              {parsedPlan.days.map((day) => (
                <DayCard key={day.day} day={day} />
              ))}
              {parsedPlan.weekly_notes && (
                <p className="text-xs text-gray-500 mt-2 italic">{parsedPlan.weekly_notes}</p>
              )}
            </div>
          )}
        </div>

        {/* Chat */}
        <div className="flex flex-col bg-white border border-gray-200 rounded-xl overflow-hidden" style={{ height: "600px" }}>
          <div className="px-4 py-3 border-b border-gray-200">
            <h2 className="font-semibold text-gray-900 text-sm">Coach Chat</h2>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-xs lg:max-w-sm rounded-2xl px-4 py-2.5 text-sm ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white rounded-br-sm"
                    : "bg-gray-100 text-gray-800 rounded-bl-sm"
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
                <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3">
                  <LoadingSpinner size="sm" />
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <form onSubmit={handleChat} className="p-3 border-t border-gray-200 flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask your coach..."
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
