import client from "./client";

export interface Supplement {
  id: number;
  name: string;
  dosage: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string | null;
}

export interface SupplementLog {
  id: number;
  supplement_id: number;
  date: string;
  taken_at: string | null;
}

export async function getSupplements(): Promise<Supplement[]> {
  const res = await client.get("/api/supplements");
  return res.data;
}

export async function createSupplement(payload: {
  name: string;
  dosage?: string;
  notes?: string;
}): Promise<Supplement> {
  const res = await client.post("/api/supplements", payload);
  return res.data;
}

export async function updateSupplement(id: number, payload: { name?: string; dosage?: string; notes?: string }): Promise<Supplement> {
  const res = await client.patch(`/api/supplements/${id}`, payload);
  return res.data;
}

export async function deleteSupplement(id: number): Promise<void> {
  await client.delete(`/api/supplements/${id}`);
}

export async function getSupplementLog(date?: string): Promise<SupplementLog[]> {
  const res = await client.get("/api/supplements/log", { params: date ? { log_date: date } : {} });
  return res.data;
}

export async function logSupplementTaken(supplementId: number, date?: string): Promise<SupplementLog> {
  const res = await client.post("/api/supplements/log", {
    supplement_id: supplementId,
    ...(date ? { date } : {}),
  });
  return res.data;
}

export async function unlogSupplement(logId: number): Promise<void> {
  await client.delete(`/api/supplements/log/${logId}`);
}
