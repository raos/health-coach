import client from "./client";
import type { DashboardSummary, GoalProgress, ActivityFeedItem, WeightLog, Vo2MaxLog, GoalProjection } from "../types";

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

export async function getWorkoutHeatmap(weeks = 12): Promise<WorkoutDay[]> {
  const res = await client.get(`/api/dashboard/workout-heatmap?weeks=${weeks}`);
  return res.data;
}

export async function getDashboardGoalProjection(): Promise<GoalProjection> {
  const res = await client.get<GoalProjection>("/api/dashboard/goal-projection");
  return res.data;
}

export async function getVo2Trend(): Promise<Vo2MaxLog[]> {
  const res = await client.get("/api/dashboard/vo2-trend");
  return res.data;
}

export interface WorkoutDay {
  date: string;
  count: number;
  hevy_volume_lbs: number;
  cardio_minutes: number;
  total_minutes: number;
  types: string[];
}
