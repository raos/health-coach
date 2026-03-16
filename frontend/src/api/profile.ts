import client from "./client";
import type { UserProfile } from "../types";

export async function getProfile(): Promise<UserProfile> {
  const res = await client.get("/api/profile");
  return res.data;
}

export async function updateProfile(data: Partial<UserProfile>): Promise<UserProfile> {
  const res = await client.put("/api/profile", data);
  return res.data;
}
