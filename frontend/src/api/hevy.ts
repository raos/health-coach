import client from "./client";

export interface ExerciseDataPoint {
  date: string;
  max_weight_lbs: number;
  est_1rm: number;
  is_pr: boolean;
}

export interface PushRoutineExercise {
  name: string;
  sets: number;
  reps: string;
  rest_seconds?: number;
  coaching_note?: string;
}

export interface PushRoutineResult {
  routine_id: string | null;
  matched: { plan_name: string; hevy_name: string; score: number }[];
  unmatched: string[];
}

export async function listExercises(): Promise<string[]> {
  const res = await client.get("/api/hevy/exercises");
  return res.data;
}

export async function getExerciseProgress(
  exerciseName: string,
  weeks = 13
): Promise<ExerciseDataPoint[]> {
  const res = await client.get("/api/hevy/exercise-progress", {
    params: { exercise_name: exerciseName, weeks },
  });
  return res.data;
}

export async function pushRoutine(
  title: string,
  exercises: PushRoutineExercise[]
): Promise<PushRoutineResult> {
  const res = await client.post("/api/hevy/push-routine", { title, exercises });
  return res.data;
}
