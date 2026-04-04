import client from "./client";
import type { BodyCompositionLog } from "../types";

export async function getLatestBodyComp(): Promise<BodyCompositionLog | null> {
  const res = await client.get("/api/body-composition/latest");
  return res.data;
}

export async function getBodyCompHistory(): Promise<BodyCompositionLog[]> {
  const res = await client.get("/api/body-composition/history");
  return res.data;
}
