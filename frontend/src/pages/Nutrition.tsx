import { useEffect, useRef, useState } from "react";
import { Salad, RefreshCw, ChevronDown, ChevronUp, ShoppingCart, RotateCcw, Settings2, Mail, ClipboardList, ChevronLeft, ChevronRight, MessageSquare, Send } from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorBanner from "../components/shared/ErrorBanner";
import MarkdownRenderer from "../components/shared/MarkdownRenderer";
import { getLatestMealPlan, generateMealPlan, regenerateDay, emailMealPlan, emailShoppingList, getNutritionLog, nutritionChat, logMealFromDescription } from "../api/nutrition";
import type { NutritionLogEntry } from "../api/nutrition";
import { getProfile } from "../api/profile";
import type { MealPlan } from "../types";

type Tab = "meal-plan" | "food-log" | "shopping-list" | "chat";

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
}

interface Meal {
  meal_type: string;
  name: string;
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  ingredients: string[];
  recipe_steps: string[];
  prep_time_min?: number;
  bobby_parish_notes?: string;
}

interface Day {
  day: string;
  total_kcal: number;
  total_protein_g: number;
  total_carbs_g: number;
  total_fat_g: number;
  meals: Meal[];
}

interface ParsedMealPlan {
  week_start: string;
  daily_target_kcal: number;
  days: Day[];
  shopping_list?: {
    produce?: string[];
    pantry?: string[];
    refrigerated?: string[];
    spices?: string[];
  };
  weekly_notes?: string;
}

const MEAL_ORDER = ["breakfast", "lunch", "snack", "dinner", "dessert"];
const MEAL_COLORS: Record<string, string> = {
  breakfast: "bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-700",
  lunch: "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-700",
  snack: "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-700",
  dinner: "bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-700",
  dessert: "bg-pink-50 dark:bg-pink-900/20 border-pink-200 dark:border-pink-700",
};

function parseQuantity(s: string): number {
  if (s.includes("/")) {
    const [a, b] = s.split("/");
    return parseFloat(a) / parseFloat(b);
  }
  return parseFloat(s);
}

function scaleIngredient(ingredient: string, factor: number): string {
  if (factor === 1) return ingredient;
  const m = ingredient.match(/^(\d+(?:\/\d+)?(?:\.\d+)?)\s+(.*)/);
  if (m) {
    const scaled = parseQuantity(m[1]) * factor;
    const display = Number(scaled.toFixed(1)).toString().replace(/\.0$/, "");
    return `${display} ${m[2]}`;
  }
  return `${ingredient} (×${factor})`;
}

function MacroPills({ kcal, protein_g, carbs_g, fat_g, scale }: {
  kcal: number; protein_g: number; carbs_g: number; fat_g: number; scale: number;
}) {
  const s = (v: number) => Math.round(v * scale);
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">{s(kcal)} kcal</span>
      <span className="text-xs bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded-full font-medium">P {s(protein_g)}g</span>
      <span className="text-xs bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300 px-1.5 py-0.5 rounded-full font-medium">C {s(carbs_g)}g</span>
      <span className="text-xs bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300 px-1.5 py-0.5 rounded-full font-medium">F {s(fat_g)}g</span>
    </div>
  );
}

function MacroBar({ protein_g, carbs_g, fat_g }: { protein_g: number; carbs_g: number; fat_g: number }) {
  const total = protein_g * 4 + carbs_g * 4 + fat_g * 9;
  if (!total) return null;
  const pPct = (protein_g * 4 / total) * 100;
  const cPct = (carbs_g * 4 / total) * 100;
  const fPct = (fat_g * 9 / total) * 100;
  return (
    <div className="mt-3">
      <div className="flex h-2 rounded-full overflow-hidden gap-0.5">
        <div className="bg-blue-400 dark:bg-blue-500 rounded-l-full" style={{ width: `${pPct}%` }} title={`Protein ${pPct.toFixed(0)}%`} />
        <div className="bg-orange-400 dark:bg-orange-500" style={{ width: `${cPct}%` }} title={`Carbs ${cPct.toFixed(0)}%`} />
        <div className="bg-yellow-400 dark:bg-yellow-500 rounded-r-full" style={{ width: `${fPct}%` }} title={`Fat ${fPct.toFixed(0)}%`} />
      </div>
      <div className="flex gap-3 mt-1">
        <span className="text-xs text-blue-600 dark:text-blue-400">Protein {pPct.toFixed(0)}%</span>
        <span className="text-xs text-orange-600 dark:text-orange-400">Carbs {cPct.toFixed(0)}%</span>
        <span className="text-xs text-yellow-600 dark:text-yellow-400">Fat {fPct.toFixed(0)}%</span>
      </div>
    </div>
  );
}

function MealCard({ meal }: { meal: Meal }) {
  const [expanded, setExpanded] = useState(false);
  const [servings, setServings] = useState(1);

  return (
    <div className={`border rounded-lg overflow-hidden ${MEAL_COLORS[meal.meal_type] || "bg-gray-50 dark:bg-gray-700 border-gray-200 dark:border-gray-600"}`}>
      {/* Header */}
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between px-4 py-3 text-left">
        <div className="flex-1 min-w-0 mr-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">{meal.meal_type}</span>
            {meal.meal_type === "lunch" && meal.name.toLowerCase().startsWith("leftover") && (
              <span className="text-xs bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300 px-1.5 py-0.5 rounded-full">↩ leftover</span>
            )}
            {meal.prep_time_min && (
              <span className="text-xs text-gray-400 dark:text-gray-500">⏱ {meal.prep_time_min} min</span>
            )}
          </div>
          <p className="font-medium text-gray-900 dark:text-gray-100 text-sm mt-0.5">{meal.name}</p>
          <div className="mt-1.5">
            <MacroPills
              kcal={meal.kcal}
              protein_g={meal.protein_g}
              carbs_g={meal.carbs_g}
              fat_g={meal.fat_g}
              scale={servings}
            />
          </div>
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 text-gray-400 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />}
      </button>

      {/* Expanded body */}
      {expanded && (
        <div className="px-4 pb-4 border-t border-current border-opacity-20">
          <MacroBar protein_g={meal.protein_g * servings} carbs_g={meal.carbs_g * servings} fat_g={meal.fat_g * servings} />

          {meal.ingredients.length > 0 && (
            <div className="flex items-center gap-2 mt-3 mb-1">
              <span className="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide">Ingredients</span>
              <div className="ml-auto flex items-center gap-1.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg px-2 py-1">
                <button
                  onClick={(e) => { e.stopPropagation(); setServings(Math.max(1, servings - 1)); }}
                  className="w-5 h-5 flex items-center justify-center text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 font-bold text-sm leading-none"
                >−</button>
                <span className="text-xs font-medium text-gray-700 dark:text-gray-300 w-12 text-center">
                  {servings} serving{servings !== 1 ? "s" : ""}
                </span>
                <button
                  onClick={(e) => { e.stopPropagation(); setServings(Math.min(8, servings + 1)); }}
                  className="w-5 h-5 flex items-center justify-center text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 font-bold text-sm leading-none"
                >+</button>
              </div>
            </div>
          )}

          {meal.ingredients.length > 0 && (
            <ul className="text-sm text-gray-700 dark:text-gray-300 space-y-0.5 mt-1.5">
              {meal.ingredients.map((ing, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <span className="text-gray-400 dark:text-gray-500">•</span>
                  {scaleIngredient(ing, servings)}
                </li>
              ))}
            </ul>
          )}

          {meal.recipe_steps.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase tracking-wide mb-1.5">Instructions</p>
              <ol className="text-sm text-gray-700 dark:text-gray-300 space-y-1">
                {meal.recipe_steps.map((step, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="font-medium text-gray-400 dark:text-gray-500 flex-shrink-0">{i + 1}.</span>
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {meal.bobby_parish_notes && (
            <p className="mt-3 text-xs text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 rounded p-2 italic">{meal.bobby_parish_notes}</p>
          )}
        </div>
      )}
    </div>
  );
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function offsetDate(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function formatDisplayDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("en-US", { weekday: "long", month: "short", day: "numeric" });
}

export default function Nutrition() {
  const [plan, setPlan] = useState<MealPlan | null>(null);
  const [parsedPlan, setParsedPlan] = useState<ParsedMealPlan | null>(null);
  const [activeDay, setActiveDay] = useState(() => {
    const dow = new Date().getDay(); // 0=Sun … 6=Sat
    return dow === 0 ? 6 : dow - 1; // Mon=0 … Sun=6
  });
  const [activeTab, setActiveTab] = useState<Tab>("meal-plan");
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [regeneratingDay, setRegeneratingDay] = useState(false);
  const [emailing, setEmailing] = useState(false);
  const [emailStatus, setEmailStatus] = useState("");
  const [error, setError] = useState("");
  const [foodLog, setFoodLog] = useState<NutritionLogEntry[]>([]);
  const [foodLogLoading, setFoodLogLoading] = useState(false);
  const [foodLogDate, setFoodLogDate] = useState(todayISO);
  const [quickLogText, setQuickLogText] = useState("");
  const [quickLogging, setQuickLogging] = useState(false);
  const [quickLogError, setQuickLogError] = useState("");
  const [checkedItems, setCheckedItems] = useState<Set<string>>(new Set());
  const [emailingList, setEmailingList] = useState(false);
  const [listEmailStatus, setListEmailStatus] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([
    { role: "assistant", content: "Hi! I'm your personal nutritionist. I have access to your food log, meal plan, and health goals. Ask me about healthy eating habits, food swaps, eating out suggestions, or anything nutrition-related." }
  ]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const [calorieTarget, setCalorieTarget] = useState(2200);
  const [showPrefs, setShowPrefs] = useState(false);
  const [breakfastPrefs, setBreakfastPrefs] = useState(
    "Rotate among these options — keep them quick, no cooking:\n" +
    "1. Overnight oats: rolled oats + whey protein + unsweetened almond milk + hemp/pumpkin seeds + berries\n" +
    "2. Protein smoothie: whey protein + creatine + frozen fruit + non-fat Greek yogurt + hemp/pumpkin seeds + unsweetened almond milk\n" +
    "3. Eggs + toast + cottage cheese: 2-3 pasture-raised eggs + Dave's Killer Bread + cottage cheese\n" +
    "No traditional Indian breakfast (no idli, dosa, upma)."
  );
  const [lunchPrefs, setLunchPrefs] = useState("Lunch is usually previous night's dinner");
  const [dinnerPrefs, setDinnerPrefs] = useState(
    "South Indian home cooking: sambar with rice, kootu, poriyal, rasam, dal tadka, chana masala, rajma, paneer dishes, egg curries. " +
    "Occasional non-Indian (pasta, grain bowls) 1-2x/week is fine."
  );

  useEffect(() => {
    getProfile()
      .then((p) => { if (p.calorie_target) setCalorieTarget(p.calorie_target); })
      .catch(() => {});

    getLatestMealPlan()
      .then((p) => {
        if (p) {
          setPlan(p);
          try {
            const parsed = JSON.parse(p.plan_json);
            setParsedPlan(parsed);
            // Clamp to last day if plan has fewer days than today's index
            const dow = new Date().getDay();
            const todayIdx = dow === 0 ? 6 : dow - 1;
            setActiveDay(Math.min(todayIdx, parsed.days.length - 1));
          } catch {}
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (activeTab !== "food-log") return;
    setFoodLogLoading(true);
    getNutritionLog(foodLogDate)
      .then((entries) => setFoodLog(entries))
      .catch(() => setFoodLog([]))
      .finally(() => setFoodLogLoading(false));
  }, [activeTab, foodLogDate]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  async function handleQuickLog() {
    if (!quickLogText.trim() || quickLogging) return;
    setQuickLogging(true);
    setQuickLogError("");
    try {
      const entry = await logMealFromDescription(quickLogText.trim(), foodLogDate);
      setFoodLog((prev) => [...prev, entry]);
      setQuickLogText("");
    } catch (e: any) {
      setQuickLogError(e?.response?.data?.detail || "Failed to log meal. Try again.");
    } finally {
      setQuickLogging(false);
    }
  }

  async function sendChat() {
    const msg = chatInput.trim();
    if (!msg || chatLoading) return;
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", content: msg }]);
    setChatLoading(true);
    try {
      const reply = await nutritionChat(msg);
      setChatMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch {
      setChatMessages((prev) => [...prev, { role: "assistant", content: "Sorry, couldn't reach the nutritionist service. Make sure the backend is running." }]);
    } finally {
      setChatLoading(false);
    }
  }

  async function handleEmail() {
    setEmailing(true);
    setEmailStatus("");
    setError("");
    try {
      await emailMealPlan();
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
      const p = await generateMealPlan({ calorieTarget, breakfastPrefs, lunchPrefs, dinnerPrefs });
      setPlan(p);
      try { setParsedPlan(JSON.parse(p.plan_json)); } catch {}
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to generate meal plan. Check your Anthropic API key in Settings.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleRegenerateDay() {
    if (!plan || !parsedPlan) return;
    const dayName = parsedPlan.days[activeDay]?.day;
    if (!dayName) return;
    setRegeneratingDay(true);
    try {
      const p = await regenerateDay(plan.id, dayName);
      setPlan(p);
      try { setParsedPlan(JSON.parse(p.plan_json)); } catch {}
    } catch (e: any) {
      setError("Failed to regenerate day.");
    } finally {
      setRegeneratingDay(false);
    }
  }

  function toggleItem(key: string) {
    setCheckedItems((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  async function handleEmailShoppingList() {
    if (!parsedPlan?.shopping_list) return;
    const grouped: Record<string, string[]> = {};
    for (const [category, items] of Object.entries(parsedPlan.shopping_list)) {
      const checked = (items as string[]).filter((_item, i) => checkedItems.has(`${category}::${i}`));
      if (checked.length > 0) grouped[category] = checked;
    }
    if (Object.keys(grouped).length === 0) {
      setError("No items checked. Check the items you need to buy first.");
      return;
    }
    setEmailingList(true);
    setListEmailStatus("");
    setError("");
    try {
      await emailShoppingList(grouped);
      setListEmailStatus("Sent!");
      setTimeout(() => setListEmailStatus(""), 3000);
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Failed to send shopping list email.");
    } finally {
      setEmailingList(false);
    }
  }

  const currentDay = parsedPlan?.days[activeDay];
  const sortedMeals = currentDay?.meals.slice().sort(
    (a, b) => MEAL_ORDER.indexOf(a.meal_type) - MEAL_ORDER.indexOf(b.meal_type)
  );

  const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: "meal-plan", label: "Meal Plan", icon: Salad },
    { id: "food-log", label: "Food Log", icon: ClipboardList },
    { id: "shopping-list", label: "Shopping List", icon: ShoppingCart },
    { id: "chat", label: "Nutritionist", icon: MessageSquare },
  ];

  return (
    <PageWrapper title="Nutrition Expert">
      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}
      {loading && <LoadingSpinner />}

      {/* Tab bar */}
      <div className="flex border-b border-gray-200 dark:border-gray-700 mb-5">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-5 py-3 text-sm font-medium border-b-2 transition-colors -mb-px ${
              activeTab === id
                ? "border-green-600 text-green-600 dark:text-green-400"
                : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600"
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* ── Meal Plan tab ── */}
      {activeTab === "meal-plan" && (
        <>
          {/* Toolbar */}
          <div className="flex items-center gap-2 mb-4 flex-wrap">
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min={1200}
                max={4000}
                step={50}
                value={calorieTarget}
                onChange={(e) => setCalorieTarget(Number(e.target.value))}
                className="w-20 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg text-center focus:outline-none focus:ring-2 focus:ring-green-500 bg-white dark:bg-gray-700 dark:text-gray-100"
              />
              <span className="text-sm text-gray-500">kcal/day</span>
            </div>
            <button
              onClick={() => setShowPrefs(!showPrefs)}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg transition-colors ${showPrefs ? "bg-green-50 dark:bg-green-900/30 border-green-300 dark:border-green-700 text-green-700 dark:text-green-400" : "border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700"}`}
            >
              <Settings2 className="w-4 h-4" />
              Preferences
            </button>
            <button
              onClick={handleGenerate}
              disabled={generating}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${generating ? "animate-spin" : ""}`} />
              {generating ? "Generating..." : "Generate Meal Plan"}
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

          {/* Preferences panel */}
          {showPrefs && (
            <div className="mb-4 bg-white dark:bg-gray-800 border border-green-200 dark:border-green-700 rounded-xl p-4 space-y-4">
              <div className="flex items-center justify-between mb-1">
                <h3 className="font-semibold text-gray-900 dark:text-gray-100 text-sm">Meal Preferences</h3>
                <p className="text-xs text-gray-400 dark:text-gray-500">These are sent to Claude when you generate a plan</p>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Breakfast — what you like to eat</label>
                <textarea value={breakfastPrefs} onChange={(e) => setBreakfastPrefs(e.target.value)} rows={4}
                  className="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500 resize-none bg-white dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Lunch — what you typically eat</label>
                <textarea value={lunchPrefs} onChange={(e) => setLunchPrefs(e.target.value)} rows={2}
                  className="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500 resize-none bg-white dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Dinner (also used for next day's lunch — cook once, eat twice)</label>
                <textarea value={dinnerPrefs} onChange={(e) => setDinnerPrefs(e.target.value)} rows={3}
                  className="w-full text-sm border border-gray-200 dark:border-gray-600 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500 resize-none bg-white dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400" />
              </div>
            </div>
          )}

          {!loading && !plan && (
            <div className="border-2 border-dashed border-gray-200 dark:border-gray-600 rounded-xl p-12 text-center">
              <Salad className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
              <p className="text-gray-500 dark:text-gray-400">No meal plan yet. Set your calorie target and click <strong>Generate Meal Plan</strong> above.</p>
            </div>
          )}

          {parsedPlan && (
            <div className="space-y-4">
              {/* Target row */}
              <div className="flex items-center gap-4 text-sm text-gray-600 dark:text-gray-400 bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-700 rounded-lg px-4 py-2.5">
                <span className="font-medium text-gray-700 dark:text-gray-300">Daily target: {parsedPlan.daily_target_kcal} kcal · 140–150g protein</span>
                <span className="text-gray-400 dark:text-gray-600">|</span>
                <span>Cook once, eat twice · South Indian veg+egg · Bobby Parish</span>
              </div>

              {/* Day tabs */}
              <div className="flex items-center gap-1 flex-wrap">
                {parsedPlan.days.map((day, i) => (
                  <button
                    key={day.day}
                    onClick={() => setActiveDay(i)}
                    className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                      activeDay === i ? "bg-green-600 text-white" : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
                    }`}
                  >
                    {day.day.slice(0, 3)}
                  </button>
                ))}
              </div>

              {/* Day macros summary */}
              {currentDay && (
                <div className="flex items-center justify-between bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3">
                  <div>
                    <p className="font-semibold text-gray-900 dark:text-gray-100">{currentDay.day}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                      P: <span className="font-medium text-gray-700 dark:text-gray-300">{currentDay.total_protein_g}g</span>
                      {" · "}C: <span className="font-medium text-gray-700 dark:text-gray-300">{currentDay.total_carbs_g}g</span>
                      {" · "}F: <span className="font-medium text-gray-700 dark:text-gray-300">{currentDay.total_fat_g}g</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-2xl font-bold text-gray-900 dark:text-gray-100">{currentDay.total_kcal}</span>
                    <span className="text-sm text-gray-500 dark:text-gray-400">kcal</span>
                    <button
                      onClick={handleRegenerateDay}
                      disabled={regeneratingDay}
                      className="ml-2 p-1.5 text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                      title="Regenerate this day"
                    >
                      <RotateCcw className={`w-4 h-4 ${regeneratingDay ? "animate-spin" : ""}`} />
                    </button>
                  </div>
                </div>
              )}

              {/* Meal cards */}
              <div className="space-y-2">
                {sortedMeals?.map((meal, i) => <MealCard key={i} meal={meal} />)}
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Food Log tab ── */}
      {activeTab === "food-log" && (
        <div className="space-y-4">
          {/* Date navigator */}
          <div className="flex items-center justify-between bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-3">
            <button
              onClick={() => setFoodLogDate((d) => offsetDate(d, -1))}
              className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <span className="font-medium text-gray-900 dark:text-gray-100">{formatDisplayDate(foodLogDate)}</span>
              {foodLogDate !== todayISO() && (
                <button
                  onClick={() => setFoodLogDate(todayISO())}
                  className="text-xs text-green-600 dark:text-green-400 hover:underline"
                >
                  Today
                </button>
              )}
            </div>
            <button
              onClick={() => setFoodLogDate((d) => offsetDate(d, 1))}
              disabled={foodLogDate >= todayISO()}
              className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors disabled:opacity-30"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>

          {/* Quick log input */}
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">Log a meal</p>
            <div className="flex gap-2 items-start">
              <textarea
                value={quickLogText}
                onChange={(e) => setQuickLogText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && e.metaKey && handleQuickLog()}
                placeholder="Describe what you ate, e.g. '2 scrambled eggs with toast and a glass of milk for breakfast'"
                rows={2}
                className="flex-1 px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500 resize-none bg-white dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400"
              />
              <button
                onClick={handleQuickLog}
                disabled={!quickLogText.trim() || quickLogging}
                className="flex items-center gap-1.5 px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors whitespace-nowrap"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${quickLogging ? "animate-spin" : ""}`} />
                {quickLogging ? "Logging..." : "Log Food"}
              </button>
            </div>
            {quickLogError && <p className="text-xs text-red-500 dark:text-red-400 mt-1.5">{quickLogError}</p>}
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1.5">Claude will estimate the macros automatically · ⌘↵ to submit</p>
          </div>

          {/* Log entries */}
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5">
            {foodLogLoading ? (
              <p className="text-sm text-gray-400 dark:text-gray-500">Loading...</p>
            ) : foodLog.length === 0 ? (
              <div className="text-center py-8">
                <ClipboardList className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
                <p className="text-sm text-gray-500 dark:text-gray-400">No meals logged for this date.</p>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Tell Claude on your phone what you ate to log a meal.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {foodLog.map((entry) => (
                  <div key={entry.id} className="flex items-start justify-between p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">{entry.meal_type}</span>
                        <span className="font-medium text-sm text-gray-900 dark:text-gray-100">{entry.name}</span>
                      </div>
                      {entry.description && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{entry.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 flex-shrink-0 ml-3">
                      <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">{entry.kcal} kcal</span>
                      <span className="text-xs bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded-full">P {entry.protein_g}g</span>
                      <span className="text-xs bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300 px-1.5 py-0.5 rounded-full">C {entry.carbs_g}g</span>
                      <span className="text-xs bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300 px-1.5 py-0.5 rounded-full">F {entry.fat_g}g</span>
                    </div>
                  </div>
                ))}
                <div className="flex items-center justify-between pt-3 border-t border-gray-200 dark:border-gray-700">
                  <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Daily totals</span>
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-bold text-gray-900 dark:text-gray-100">
                      {foodLog.reduce((sum, e) => sum + e.kcal, 0)} kcal
                    </span>
                    <span className="text-xs bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded-full">
                      P {Math.round(foodLog.reduce((sum, e) => sum + e.protein_g, 0))}g
                    </span>
                    <span className="text-xs bg-orange-100 dark:bg-orange-900/40 text-orange-700 dark:text-orange-300 px-1.5 py-0.5 rounded-full">
                      C {Math.round(foodLog.reduce((sum, e) => sum + e.carbs_g, 0))}g
                    </span>
                    <span className="text-xs bg-yellow-100 dark:bg-yellow-900/40 text-yellow-700 dark:text-yellow-300 px-1.5 py-0.5 rounded-full">
                      F {Math.round(foodLog.reduce((sum, e) => sum + e.fat_g, 0))}g
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Shopping List tab ── */}
      {activeTab === "shopping-list" && (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
              <ShoppingCart className="w-4 h-4" /> Weekly Shopping List
            </h3>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400 dark:text-gray-500">
                {checkedItems.size} item{checkedItems.size !== 1 ? "s" : ""} checked
              </span>
              <button
                onClick={handleEmailShoppingList}
                disabled={emailingList || checkedItems.size === 0}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-gray-700 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50 transition-colors"
              >
                <Mail className="w-3.5 h-3.5" />
                {emailingList ? "Sending..." : listEmailStatus || "Email Checked Items"}
              </button>
            </div>
          </div>
          {parsedPlan?.shopping_list && Object.keys(parsedPlan.shopping_list).length > 0 ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(parsedPlan.shopping_list).map(([category, items]) => (
                <div key={category}>
                  <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-2">{category}</p>
                  <ul className="space-y-1.5">
                    {(items as string[]).map((item, i) => {
                      const key = `${category}::${i}`;
                      const checked = checkedItems.has(key);
                      return (
                        <li key={i}>
                          <label className="flex items-start gap-2 cursor-pointer group">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => toggleItem(key)}
                              className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 accent-green-600 cursor-pointer"
                            />
                            <span className={`text-sm transition-colors ${checked ? "line-through text-gray-400 dark:text-gray-500" : "text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-gray-100"}`}>
                              {item}
                            </span>
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <ShoppingCart className="w-8 h-8 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
              <p className="text-sm text-gray-500 dark:text-gray-400">No shopping list available.</p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Generate a meal plan to get your weekly shopping list.</p>
            </div>
          )}
        </div>
      )}

      {/* ── Chat tab ── */}
      {activeTab === "chat" && (
        <div className="flex flex-col bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden" style={{ height: "600px" }}>
          {/* Message list */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {chatMessages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                  msg.role === "user"
                    ? "bg-green-600 text-white rounded-br-sm"
                    : "bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-bl-sm"
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
                  <div className="flex gap-1 items-center h-4">
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          {/* Input bar */}
          <div className="border-t border-gray-200 dark:border-gray-700 p-3 flex gap-2">
            <input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendChat()}
              placeholder="Ask about healthy eating, food swaps, eating out..."
              className="flex-1 px-4 py-2.5 text-sm border border-gray-200 dark:border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-green-500 bg-white dark:bg-gray-700 dark:text-gray-100 dark:placeholder-gray-400"
            />
            <button
              onClick={sendChat}
              disabled={!chatInput.trim() || chatLoading}
              className="px-4 py-2.5 bg-green-600 text-white rounded-xl hover:bg-green-700 disabled:opacity-50 transition-colors flex items-center gap-1.5"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </PageWrapper>
  );
}
