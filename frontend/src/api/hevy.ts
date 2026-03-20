import client from "./client";

export interface ExerciseDataPoint {
  date: string;
  max_weight_lbs: number;
  est_1rm: number;
  is_pr: boolean;
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
