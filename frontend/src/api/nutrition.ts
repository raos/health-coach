import client from "./client";
import type { MealPlan } from "../types";

export async function getLatestMealPlan(): Promise<MealPlan | null> {
  const res = await client.get("/api/nutrition/meal-plan/latest");
  return res.data;
}

export async function generateMealPlan(params?: {
  calorieTarget?: number;
  breakfastPrefs?: string;
  lunchPrefs?: string;
  dinnerPrefs?: string;
}): Promise<MealPlan> {
  const body: Record<string, unknown> = {};
  if (params?.calorieTarget) body.calorie_target = params.calorieTarget;
  if (params?.breakfastPrefs) body.breakfast_prefs = params.breakfastPrefs;
  if (params?.lunchPrefs) body.lunch_prefs = params.lunchPrefs;
  if (params?.dinnerPrefs) body.dinner_prefs = params.dinnerPrefs;
  const res = await client.post("/api/nutrition/meal-plan", body);
  return res.data;
}

export async function regenerateDay(plan_id: number, day_of_week: string): Promise<MealPlan> {
  const res = await client.post("/api/nutrition/meal-plan/regenerate-day", { plan_id, day_of_week });
  return res.data;
}
