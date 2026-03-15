import client from "./client";
import type { DexaScan } from "../types";

export async function getLatestDexa(): Promise<DexaScan | null> {
  const res = await client.get("/api/dexa/latest");
  return res.data;
}

export async function getDexaHistory(): Promise<DexaScan[]> {
  const res = await client.get("/api/dexa/history");
  return res.data;
}
