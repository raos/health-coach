import { useEffect, useState } from "react";
import { Salad, RefreshCw, ChevronDown, ChevronUp, ShoppingCart, RotateCcw, Settings2, Mail } from "lucide-react";
import PageWrapper from "../components/layout/PageWrapper";
import LoadingSpinner from "../components/shared/LoadingSpinner";
import ErrorBanner from "../components/shared/ErrorBanner";
import { getLatestMealPlan, generateMealPlan, regenerateDay, emailMealPlan } from "../api/nutrition";
import type { MealPlan } from "../types";

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
  breakfast: "bg-yellow-50 border-yellow-200",
  lunch: "bg-green-50 border-green-200",
  snack: "bg-blue-50 border-blue-200",
  dinner: "bg-purple-50 border-purple-200",
  dessert: "bg-pink-50 border-pink-200",
};

function MealCard({ meal }: { meal: Meal }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className={`border rounded-lg overflow-hidden ${MEAL_COLORS[meal.meal_type] || "bg-gray-50 border-gray-200"}`}>
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between px-4 py-3 text-left">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium uppercase tracking-wide text-gray-500">{meal.meal_type}</span>
            {meal.meal_type === "lunch" && meal.name.toLowerCase().startsWith("leftover") && (
              <span className="text-xs bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded-full">↩ leftover</span>
            )}
          </div>
          <p className="font-medium text-gray-900 text-sm mt-0.5">{meal.name}</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right text-xs text-gray-500">
            <p className="font-medium text-gray-700">{meal.kcal} kcal</p>
            <p>P:{meal.protein_g}g C:{meal.carbs_g}g F:{meal.fat_g}g</p>
          </div>
          {expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
        </div>
      </button>
      {expanded && (
        <div className="px-4 pb-4 border-t border-current border-opacity-20">
          {meal.ingredients.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">Ingredients</p>
              <ul className="text-sm text-gray-700 space-y-0.5">
                {meal.ingredients.map((ing, i) => <li key={i} className="flex items-start gap-1.5"><span className="text-gray-400">•</span>{ing}</li>)}
              </ul>
            </div>
          )}
          {meal.recipe_steps.length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">Instructions</p>
              <ol className="text-sm text-gray-700 space-y-1">
                {meal.recipe_steps.map((step, i) => <li key={i} className="flex gap-2"><span className="font-medium text-gray-400 flex-shrink-0">{i+1}.</span>{step}</li>)}
              </ol>
            </div>
          )}
          {meal.bobby_parish_notes && (
            <p className="mt-3 text-xs text-green-700 bg-green-50 rounded p-2 italic">{meal.bobby_parish_notes}</p>
          )}
          {meal.prep_time_min && (
            <p className="mt-2 text-xs text-gray-400">Prep time: {meal.prep_time_min} min</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function Nutrition() {
  const [plan, setPlan] = useState<MealPlan | null>(null);
  const [parsedPlan, setParsedPlan] = useState<ParsedMealPlan | null>(null);
  const [activeDay, setActiveDay] = useState(0);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [regeneratingDay, setRegeneratingDay] = useState(false);
  const [emailing, setEmailing] = useState(false);
  const [emailStatus, setEmailStatus] = useState("");
  const [error, setError] = useState("");
  const [showShopping, setShowShopping] = useState(false);
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
    getLatestMealPlan()
      .then((p) => {
        if (p) {
          setPlan(p);
          try { setParsedPlan(JSON.parse(p.plan_json)); } catch {}
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

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

  const currentDay = parsedPlan?.days[activeDay];
  const sortedMeals = currentDay?.meals.slice().sort(
    (a, b) => MEAL_ORDER.indexOf(a.meal_type) - MEAL_ORDER.indexOf(b.meal_type)
  );

  return (
    <PageWrapper
      title="Nutrition Expert"
      subtitle="South Indian vegetarian meal plans · Bobby Parish ingredients"
      actions={
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <input
              type="number"
              min={1200}
              max={4000}
              step={50}
              value={calorieTarget}
              onChange={(e) => setCalorieTarget(Number(e.target.value))}
              className="w-20 px-2 py-1.5 text-sm border border-gray-300 rounded-lg text-center focus:outline-none focus:ring-2 focus:ring-green-500"
            />
            <span className="text-sm text-gray-500">kcal/day</span>
          </div>
          <button
            onClick={() => setShowPrefs(!showPrefs)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg transition-colors ${showPrefs ? "bg-green-50 border-green-300 text-green-700" : "border-gray-300 text-gray-600 hover:bg-gray-50"}`}
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
      }
    >
      {error && <div className="mb-4"><ErrorBanner message={error} /></div>}
      {loading && <LoadingSpinner />}

      {/* Preferences panel */}
      {showPrefs && (
        <div className="mb-4 bg-white border border-green-200 rounded-xl p-4 space-y-4">
          <div className="flex items-center justify-between mb-1">
            <h3 className="font-semibold text-gray-900 text-sm">Meal Preferences</h3>
            <p className="text-xs text-gray-400">These are sent to Claude when you generate a plan</p>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Breakfast — what you like to eat
            </label>
            <textarea
              value={breakfastPrefs}
              onChange={(e) => setBreakfastPrefs(e.target.value)}
              rows={4}
              className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500 resize-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Lunch — what you typically eat
            </label>
            <textarea
              value={lunchPrefs}
              onChange={(e) => setLunchPrefs(e.target.value)}
              rows={2}
              className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500 resize-none"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Dinner (also used for next day's lunch — cook once, eat twice)
            </label>
            <textarea
              value={dinnerPrefs}
              onChange={(e) => setDinnerPrefs(e.target.value)}
              rows={3}
              className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500 resize-none"
            />
          </div>
        </div>
      )}

      {!loading && !plan && (
        <div className="border-2 border-dashed border-gray-200 rounded-xl p-12 text-center">
          <Salad className="w-10 h-10 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">No meal plan yet. Set your calorie target and click <strong>Generate Meal Plan</strong> above.</p>
        </div>
      )}

      {parsedPlan && (
        <div className="space-y-4">
          {/* Target row */}
          <div className="flex items-center gap-4 text-sm text-gray-600 bg-green-50 border border-green-200 rounded-lg px-4 py-2.5">
            <span className="font-medium text-gray-700">Daily target: {parsedPlan.daily_target_kcal} kcal · 140–150g protein</span>
            <span className="text-gray-400">|</span>
            <span>Cook once, eat twice · South Indian veg+egg · Bobby Parish</span>
          </div>

          {/* Day tabs */}
          <div className="flex items-center gap-1 flex-wrap">
            {parsedPlan.days.map((day, i) => (
              <button
                key={day.day}
                onClick={() => setActiveDay(i)}
                className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                  activeDay === i ? "bg-green-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {day.day.slice(0, 3)}
              </button>
            ))}
            <button
              onClick={() => setShowShopping(!showShopping)}
              className="ml-auto flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              <ShoppingCart className="w-3.5 h-3.5" />
              Shopping List
            </button>
          </div>

          {/* Day macros summary */}
          {currentDay && (
            <div className="flex items-center justify-between bg-white border border-gray-200 rounded-lg px-4 py-3">
              <div>
                <p className="font-semibold text-gray-900">{currentDay.day}</p>
                <p className="text-xs text-gray-500 mt-0.5">
                  P: <span className="font-medium text-gray-700">{currentDay.total_protein_g}g</span>
                  {" · "}C: <span className="font-medium text-gray-700">{currentDay.total_carbs_g}g</span>
                  {" · "}F: <span className="font-medium text-gray-700">{currentDay.total_fat_g}g</span>
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold text-gray-900">{currentDay.total_kcal}</span>
                <span className="text-sm text-gray-500">kcal</span>
                <button
                  onClick={handleRegenerateDay}
                  disabled={regeneratingDay}
                  className="ml-2 p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
                  title="Regenerate this day"
                >
                  <RotateCcw className={`w-4 h-4 ${regeneratingDay ? "animate-spin" : ""}`} />
                </button>
              </div>
            </div>
          )}

          {/* Meals */}
          <div className="space-y-2">
            {sortedMeals?.map((meal, i) => <MealCard key={i} meal={meal} />)}
          </div>

          {/* Shopping list */}
          {showShopping && (
            <div className="bg-white border border-gray-200 rounded-xl p-5">
              <h3 className="font-semibold text-gray-900 mb-4 flex items-center gap-2">
                <ShoppingCart className="w-4 h-4" /> Weekly Shopping List
              </h3>
              {parsedPlan.shopping_list && Object.keys(parsedPlan.shopping_list).length > 0 ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(parsedPlan.shopping_list).map(([category, items]) => (
                    <div key={category}>
                      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">{category}</p>
                      <ul className="space-y-1">
                        {(items as string[]).map((item, i) => (
                          <li key={i} className="text-sm text-gray-700 flex items-start gap-1.5">
                            <span className="text-gray-300">•</span>{item}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">No shopping list available. Regenerate the meal plan to get one.</p>
              )}
            </div>
          )}
        </div>
      )}
    </PageWrapper>
  );
}
