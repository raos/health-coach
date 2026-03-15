import client from "./client";
import type { TrainingPlan } from "../types";

export async function getLatestTrainingPlan(): Promise<TrainingPlan | null> {
  const res = await client.get("/api/coach/training-plan/latest");
  return res.data;
}

export async function generateTrainingPlan(config?: {
  strength_days: number;
  cardio_days: number;
  rest_days: number;
}): Promise<TrainingPlan> {
  const res = await client.post("/api/coach/training-plan", config ?? {});
  return res.data;
}

export async function syncActivities() {
  const res = await client.post("/api/coach/sync");
  return res.data;
}
