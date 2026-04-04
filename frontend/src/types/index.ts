export interface WeightLog {
  id: number;
  date: string;
  weight_lbs: number;
  notes?: string;
  source: string;
  created_at: string;
}

export interface BodyCompositionLog {
  id: number;
  date: string;
  body_fat_pct: number;
  lean_mass_lbs?: number;
  fat_mass_lbs?: number;
  notes?: string;
}

export interface Vo2MaxLog {
  id: number;
  date: string;
  vo2max: number;
  source: string;
}

export interface StravaActivity {
  id: number;
  name: string;
  activity_type: string;
  start_date: string;
  distance_m?: number;
  moving_time_s?: number;
  average_hr?: number;
  max_hr?: number;
}

export interface HevyWorkout {
  id: string;
  title: string;
  start_time: string;
  end_time?: string;
  duration_s?: number;
  volume_lbs?: number;
}

export interface ActivityFeedItem {
  id: string;
  type: "strava" | "hevy";
  name: string;
  activity_type?: string;
  date: string;
  distance_m?: number;
  moving_time_s?: number;
  average_hr?: number;
  volume_lbs?: number;
  is_tonal?: boolean;
}

export interface DashboardSummary {
  latest_weight?: WeightLog;
  latest_body_comp?: BodyCompositionLog;
  latest_vo2max?: Vo2MaxLog;
  goal_bf_pct: number;
  goal_vo2max: number;
  goal_date: string;
}

export interface GoalProgress {
  bf_current: number | null;
  bf_goal: number | null;
  bf_pct_complete: number | null;
  bf_lbs_to_lose: number | null;
  bf_projected_date?: string;
  vo2_current: number | null;
  vo2_goal: number | null;
  vo2_pct_complete: number | null;
}

export interface UserProfile {
  id: number;
  name: string;
  dob: string | null;
  height_inches: number | null;
  email: string;
  bf_goal_pct: number | null;
  vo2max_goal: number | null;
  goal_date: string | null;
  calorie_target: number | null;
  measurement_system: "imperial" | "metric";
  training_device: "tonal" | "gym" | "bodyweight";
  training_days_strength?: number | null;
  training_days_cardio?: number | null;
  training_days_rest?: number | null;
  breakfast_pref?: string | null;
  lunch_pref?: string | null;
  dinner_pref?: string | null;
  dietary_preference?: string | null;
  preferred_cuisines?: string | null;
  preferred_exercises?: string | null;
  exercises_to_avoid?: string | null;
}

export interface TrainingPlan {
  id: number;
  generated_at: string;
  week_start: string;
  plan_json: string;
  is_active: boolean;
}

export interface MealPlan {
  id: number;
  generated_at: string;
  week_start: string;
  plan_json: string;
  calorie_target?: number;
  is_active: boolean;
}

export interface HealthInsight {
  id: number;
  generated_at: string;
  insight_type: string;
  content_md: string;
  is_read: boolean;
}

export interface WeeklyCheckin {
  id: number;
  week_start: string;
  training_adherence: number | null;
  energy_level: number | null;
  sleep_quality: number | null;
  diet_adherence: number | null;
  stress_level: number | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}
