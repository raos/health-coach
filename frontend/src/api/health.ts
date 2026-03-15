import client from "./client";
import type { HealthInsight } from "../types";

export async function getLatestInsights(): Promise<HealthInsight | null> {
  const res = await client.get("/api/health/insights/latest");
  return res.data;
}

export async function generateInsights(): Promise<HealthInsight> {
  const res = await client.post("/api/health/insights");
  return res.data;
}
