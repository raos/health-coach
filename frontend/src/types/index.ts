export interface WeightLog {
  id: number;
  date: string;
  weight_lbs: number;
  notes?: string;
  source: string;
  created_at: string;
}

export interface DexaScan {
  id: number;
  scan_date: string;
  total_weight_lbs: number;
  body_fat_pct: number;
  fat_mass_lbs: number;
  lean_mass_lbs: number;
  bone_mass_lbs?: number;
  visceral_fat_lbs?: number;
  ag_ratio?: number;
  almi?: number;
  ffmi?: number;
  t_score?: number;
  facility?: string;
  notes?: string;
  raw_pdf_path?: string;
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
  latest_dexa?: DexaScan;
  latest_vo2max?: Vo2MaxLog;
  goal_bf_pct: number;
  goal_vo2max: number;
  goal_date: string;
}

export interface GoalProgress {
  bf_current: number;
  bf_goal: number;
  bf_pct_complete: number;
  bf_lbs_to_lose: number;
  bf_projected_date?: string;
  vo2_current: number;
  vo2_goal: number;
  vo2_pct_complete: number;
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
