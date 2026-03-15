import client from "./client";

export interface SleepDay {
  date: string;
  duration_hours: number;
  score: number | null;
  deep_min: number;
  rem_min: number;
  light_min: number;
}

export interface StepsDay {
  date: string;
  steps: number;
}

export interface RestingHrDay {
  date: string;
  rhr: number;
}

export async function getSleepRange(days = 30): Promise<SleepDay[]> {
  const res = await client.get("/api/garmin/sleep/range", { params: { days } });
  return res.data;
}

export async function getStepsRange(days = 30): Promise<StepsDay[]> {
  const res = await client.get("/api/garmin/steps/range", { params: { days } });
  return res.data;
}

export async function getRestingHrRange(days = 30): Promise<RestingHrDay[]> {
  const res = await client.get("/api/garmin/resting-hr/range", { params: { days } });
  return res.data;
}
