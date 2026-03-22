import client from "./client";
import type { WeightLog } from "../types";

export async function logWeight(date: string, weight_lbs: number, notes?: string): Promise<WeightLog> {
  const res = await client.post("/api/weight/log", { date, weight_lbs, notes });
  return res.data;
}

export async function getLatestWeight(): Promise<WeightLog | null> {
  const res = await client.get("/api/weight/latest");
  return res.data;
}

export async function getWeightHistory(start?: string, end?: string): Promise<WeightLog[]> {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const res = await client.get(`/api/weight/history?${params}`);
  return res.data;
}
