import client from "./client";
import type { WeeklyCheckin } from "../types";

export interface CheckinPayload {
  week_start?: string;
  training_adherence?: number | null;
  energy_level?: number | null;
  sleep_quality?: number | null;
  diet_adherence?: number | null;
  stress_level?: number | null;
  notes?: string | null;
}

export async function upsertCheckin(payload: CheckinPayload): Promise<WeeklyCheckin> {
  const res = await client.post("/api/checkin", payload);
  return res.data;
}

export async function getLatestCheckin(): Promise<WeeklyCheckin | null> {
  const res = await client.get("/api/checkin/latest");
  return res.data;
}

export async function getCheckinHistory(limit = 12): Promise<WeeklyCheckin[]> {
  const res = await client.get("/api/checkin/history", { params: { limit } });
  return res.data;
}
