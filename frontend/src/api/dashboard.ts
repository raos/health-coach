import client from "./client";
import type { DashboardSummary, GoalProgress, ActivityFeedItem, WeightLog } from "../types";

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const res = await client.get("/api/dashboard/summary");
  return res.data;
}

export async function getWeightTrend(days = 90): Promise<WeightLog[]> {
  const res = await client.get(`/api/dashboard/weight-trend?days=${days}`);
  return res.data;
}

export async function getActivityFeed(limit = 10): Promise<ActivityFeedItem[]> {
  const res = await client.get(`/api/dashboard/activity-feed?limit=${limit}`);
  return res.data;
}

export async function getGoalProgress(): Promise<GoalProgress> {
  const res = await client.get("/api/dashboard/goal-progress");
  return res.data;
}
