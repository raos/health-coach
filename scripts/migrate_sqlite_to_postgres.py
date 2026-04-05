"""
Migrate existing data from SQLite (health.db) into PostgreSQL.
Assigns all existing rows to Sandeep's user_id.

Run from backend/ with the venv active:
    python ../scripts/migrate_sqlite_to_postgres.py

Safe to run multiple times — skips rows that already exist.
"""
import sys
import os
import uuid
import json
from datetime import datetime, date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from config import settings
from database.models import (
    User, UserProfile, WeightLog, DexaScan, Vo2MaxLog,
    StravaActivity, HevyWorkout, HevyExerciseSet,
    TrainingPlan, MealPlan, HealthInsight, CoachConversation,
    OAuthToken, DailyHealthCache, NutritionLog,
    Supplement, SupplementLog, WeeklyCheckin,
)

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "backend", "health.db")


def get_sqlite_engine():
    return sa.create_engine(f"sqlite:///{SQLITE_PATH}", connect_args={"check_same_thread": False})


def get_pg_session():
    pg_engine = sa.create_engine(settings.database_url)
    Session = sessionmaker(bind=pg_engine)
    return Session()


def migrate():
    if not os.path.exists(SQLITE_PATH):
        print(f"SQLite database not found at {SQLITE_PATH} — nothing to migrate.")
        return

    sqlite_engine = get_sqlite_engine()
    pg = get_pg_session()

    try:
        # Get Sandeep's user_id from Postgres
        admin_email = (settings.admin_email or settings.allowed_email or "").lower()
        admin_user = pg.query(User).filter(User.email == admin_email).first()
        if not admin_user:
            print(f"ERROR: Admin user {admin_email} not found in Postgres. Run seed_admin_user.py first.")
            return

        user_id = admin_user.id
        print(f"Migrating data to user_id={user_id} ({admin_email})")

        with sqlite_engine.connect() as sqlite_conn:

            # ── WeightLog ─────────────────────────────────────────────────────
            rows = sqlite_conn.execute(sa.text("SELECT * FROM weight_logs")).fetchall()
            migrated = 0
            for row in rows:
                row = dict(row._mapping)
                exists = pg.query(WeightLog).filter(
                    WeightLog.user_id == user_id,
                    WeightLog.date == row["date"],
                ).first()
                if not exists:
                    pg.add(WeightLog(
                        user_id=user_id,
                        date=row["date"],
                        weight_lbs=row["weight_lbs"],
                        notes=row.get("notes"),
                        source=row.get("source", "manual"),
                    ))
                    migrated += 1
            print(f"  WeightLog: {migrated}/{len(rows)} migrated")

            # ── DexaScan ──────────────────────────────────────────────────────
            rows = sqlite_conn.execute(sa.text("SELECT * FROM dexa_scans")).fetchall()
            migrated = 0
            for row in rows:
                row = dict(row._mapping)
                exists = pg.query(DexaScan).filter(
                    DexaScan.user_id == user_id,
                    DexaScan.scan_date == row["scan_date"],
                ).first()
                if not exists:
                    pg.add(DexaScan(
                        user_id=user_id,
                        scan_date=row["scan_date"],
                        total_weight_lbs=row["total_weight_lbs"],
                        body_fat_pct=row["body_fat_pct"],
                        fat_mass_lbs=row["fat_mass_lbs"],
                        lean_mass_lbs=row["lean_mass_lbs"],
                        bone_mass_lbs=row.get("bone_mass_lbs"),
                        visceral_fat_lbs=row.get("visceral_fat_lbs"),
                        ag_ratio=row.get("ag_ratio"),
                        almi=row.get("almi"),
                        ffmi=row.get("ffmi"),
                        t_score=row.get("t_score"),
                        facility=row.get("facility"),
                        notes=row.get("notes"),
                        raw_pdf_path=row.get("raw_pdf_path"),
                    ))
                    migrated += 1
            print(f"  DexaScan: {migrated}/{len(rows)} migrated")

            # ── Vo2MaxLog ─────────────────────────────────────────────────────
            rows = sqlite_conn.execute(sa.text("SELECT * FROM vo2max_logs")).fetchall()
            migrated = 0
            for row in rows:
                row = dict(row._mapping)
                exists = pg.query(Vo2MaxLog).filter(
                    Vo2MaxLog.user_id == user_id,
                    Vo2MaxLog.date == row["date"],
                ).first()
                if not exists:
                    pg.add(Vo2MaxLog(user_id=user_id, date=row["date"], vo2max=row["vo2max"], source=row.get("source", "manual")))
                    migrated += 1
            print(f"  Vo2MaxLog: {migrated}/{len(rows)} migrated")

            # ── StravaActivity ────────────────────────────────────────────────
            rows = sqlite_conn.execute(sa.text("SELECT * FROM strava_activities")).fetchall()
            migrated = 0
            for row in rows:
                row = dict(row._mapping)
                exists = pg.query(StravaActivity).filter(StravaActivity.id == row["id"]).first()
                if not exists:
                    pg.add(StravaActivity(
                        id=row["id"], user_id=user_id,
                        name=row["name"], activity_type=row.get("activity_type"),
                        start_date=row["start_date"], distance_m=row.get("distance_m"),
                        moving_time_s=row.get("moving_time_s"), elapsed_time_s=row.get("elapsed_time_s"),
                        total_elevation=row.get("total_elevation"), average_hr=row.get("average_hr"),
                        max_hr=row.get("max_hr"), average_speed=row.get("average_speed"),
                        kudos_count=row.get("kudos_count"), raw_json=row.get("raw_json"),
                    ))
                    migrated += 1
            print(f"  StravaActivity: {migrated}/{len(rows)} migrated")

            # ── HevyWorkout + HevyExerciseSet ─────────────────────────────────
            rows = sqlite_conn.execute(sa.text("SELECT * FROM hevy_workouts")).fetchall()
            migrated = 0
            for row in rows:
                row = dict(row._mapping)
                exists = pg.query(HevyWorkout).filter(HevyWorkout.id == row["id"]).first()
                if not exists:
                    pg.add(HevyWorkout(
                        id=row["id"], user_id=user_id,
                        title=row.get("title"), start_time=row["start_time"],
                        end_time=row.get("end_time"), duration_s=row.get("duration_s"),
                        volume_lbs=row.get("volume_lbs"), raw_json=row.get("raw_json"),
                    ))
                    migrated += 1
            pg.flush()
            print(f"  HevyWorkout: {migrated}/{len(rows)} migrated")

            set_rows = sqlite_conn.execute(sa.text("SELECT * FROM hevy_exercise_sets")).fetchall()
            set_migrated = 0
            for row in set_rows:
                row = dict(row._mapping)
                exists = pg.query(HevyExerciseSet).filter(HevyExerciseSet.id == row["id"]).first()
                if not exists:
                    pg.add(HevyExerciseSet(
                        id=row["id"], user_id=user_id,
                        workout_id=row["workout_id"], exercise_name=row["exercise_name"],
                        set_index=row.get("set_index"), weight_lbs=row.get("weight_lbs"),
                        reps=row.get("reps"), rpe=row.get("rpe"), set_type=row.get("set_type"),
                    ))
                    set_migrated += 1
            print(f"  HevyExerciseSet: {set_migrated}/{len(set_rows)} migrated")

            # ── TrainingPlan ──────────────────────────────────────────────────
            rows = sqlite_conn.execute(sa.text("SELECT * FROM training_plans")).fetchall()
            migrated = 0
            for row in rows:
                row = dict(row._mapping)
                exists = pg.query(TrainingPlan).filter(
                    TrainingPlan.user_id == user_id, TrainingPlan.week_start == row["week_start"]
                ).first()
                if not exists:
                    pg.add(TrainingPlan(
                        user_id=user_id, week_start=row["week_start"],
                        plan_json=row["plan_json"], plan_markdown=row.get("plan_markdown"),
                        context_hash=row.get("context_hash"), is_active=row.get("is_active", True),
                    ))
                    migrated += 1
            print(f"  TrainingPlan: {migrated}/{len(rows)} migrated")

            # ── MealPlan ──────────────────────────────────────────────────────
            rows = sqlite_conn.execute(sa.text("SELECT * FROM meal_plans")).fetchall()
            migrated = 0
            for row in rows:
                row = dict(row._mapping)
                exists = pg.query(MealPlan).filter(
                    MealPlan.user_id == user_id, MealPlan.week_start == row["week_start"]
                ).first()
                if not exists:
                    pg.add(MealPlan(
                        user_id=user_id, week_start=row["week_start"],
                        plan_json=row["plan_json"], calorie_target=row.get("calorie_target"),
                        is_active=row.get("is_active", True),
                    ))
                    migrated += 1
            print(f"  MealPlan: {migrated}/{len(rows)} migrated")

            # ── NutritionLog ──────────────────────────────────────────────────
            rows = sqlite_conn.execute(sa.text("SELECT * FROM nutrition_logs")).fetchall()
            migrated = 0
            for row in rows:
                row = dict(row._mapping)
                pg.add(NutritionLog(
                    user_id=user_id, date=row["date"], meal_type=row["meal_type"],
                    name=row["name"], description=row.get("description"),
                    kcal=row["kcal"], protein_g=row["protein_g"],
                    carbs_g=row["carbs_g"], fat_g=row["fat_g"],
                    source=row.get("source", "web"),
                ))
                migrated += 1
            print(f"  NutritionLog: {migrated}/{len(rows)} migrated")

            # ── GarminDailyCache → DailyHealthCache ───────────────────────────
            try:
                rows = sqlite_conn.execute(sa.text("SELECT * FROM garmin_daily_cache")).fetchall()
                migrated = 0
                for row in rows:
                    row = dict(row._mapping)
                    exists = pg.query(DailyHealthCache).filter(
                        DailyHealthCache.user_id == user_id,
                        DailyHealthCache.date == row["date"],
                        DailyHealthCache.source == "garmin",
                    ).first()
                    if not exists:
                        pg.add(DailyHealthCache(
                            user_id=user_id, date=row["date"], source="garmin",
                            sleep_duration_hours=row.get("sleep_duration_hours"),
                            sleep_score=row.get("sleep_score"),
                            deep_min=row.get("deep_min"), rem_min=row.get("rem_min"),
                            light_min=row.get("light_min"), steps=row.get("steps"),
                            resting_hr=row.get("resting_hr"),
                        ))
                        migrated += 1
                print(f"  DailyHealthCache (garmin): {migrated}/{len(rows)} migrated")
            except Exception:
                print("  DailyHealthCache: no garmin_daily_cache table found (OK)")

            # ── CoachConversation ─────────────────────────────────────────────
            rows = sqlite_conn.execute(sa.text("SELECT * FROM coach_conversations")).fetchall()
            migrated = 0
            for row in rows:
                row = dict(row._mapping)
                pg.add(CoachConversation(
                    user_id=user_id, session_id=row["session_id"],
                    role=row["role"], content=row["content"],
                ))
                migrated += 1
            print(f"  CoachConversation: {migrated}/{len(rows)} migrated")

            # ── OAuthToken ────────────────────────────────────────────────────
            rows = sqlite_conn.execute(sa.text("SELECT * FROM oauth_tokens")).fetchall()
            migrated = 0
            for row in rows:
                row = dict(row._mapping)
                exists = pg.query(OAuthToken).filter(
                    OAuthToken.user_id == user_id, OAuthToken.service == row["service"]
                ).first()
                if not exists:
                    pg.add(OAuthToken(
                        user_id=user_id, service=row["service"],
                        access_token=row["access_token"], refresh_token=row.get("refresh_token"),
                        expires_at=row.get("expires_at"), athlete_id=row.get("athlete_id"),
                    ))
                    migrated += 1
            print(f"  OAuthToken: {migrated}/{len(rows)} migrated")

            # ── HealthInsight ─────────────────────────────────────────────────
            rows = sqlite_conn.execute(sa.text("SELECT * FROM health_insights")).fetchall()
            migrated = 0
            for row in rows:
                row = dict(row._mapping)
                pg.add(HealthInsight(
                    user_id=user_id, insight_type=row["insight_type"],
                    content_md=row["content_md"], data_snapshot=row.get("data_snapshot"),
                    is_read=row.get("is_read", False),
                ))
                migrated += 1
            print(f"  HealthInsight: {migrated}/{len(rows)} migrated")

            # ── WeeklyCheckin ─────────────────────────────────────────────────
            rows = sqlite_conn.execute(sa.text("SELECT * FROM weekly_checkins")).fetchall()
            migrated = 0
            for row in rows:
                row = dict(row._mapping)
                exists = pg.query(WeeklyCheckin).filter(
                    WeeklyCheckin.user_id == user_id, WeeklyCheckin.week_start == row["week_start"]
                ).first()
                if not exists:
                    pg.add(WeeklyCheckin(
                        user_id=user_id, week_start=row["week_start"],
                        training_adherence=row.get("training_adherence"),
                        energy_level=row.get("energy_level"),
                        sleep_quality=row.get("sleep_quality"),
                        diet_adherence=row.get("diet_adherence"),
                        stress_level=row.get("stress_level"),
                        notes=row.get("notes"),
                    ))
                    migrated += 1
            print(f"  WeeklyCheckin: {migrated}/{len(rows)} migrated")

            # ── Supplement + SupplementLog ────────────────────────────────────
            try:
                rows = sqlite_conn.execute(sa.text("SELECT * FROM supplements")).fetchall()
                id_map = {}
                for row in rows:
                    row = dict(row._mapping)
                    new_sup = Supplement(
                        user_id=user_id, name=row["name"],
                        dosage=row.get("dosage"), notes=row.get("notes"),
                        is_active=row.get("is_active", True),
                    )
                    pg.add(new_sup)
                    pg.flush()
                    id_map[row["id"]] = new_sup.id
                print(f"  Supplement: {len(rows)} migrated")

                log_rows = sqlite_conn.execute(sa.text("SELECT * FROM supplement_logs")).fetchall()
                for row in log_rows:
                    row = dict(row._mapping)
                    new_id = id_map.get(row["supplement_id"])
                    if new_id:
                        pg.add(SupplementLog(user_id=user_id, supplement_id=new_id, date=row["date"]))
                print(f"  SupplementLog: {len(log_rows)} migrated")
            except Exception as e:
                print(f"  Supplements: {e}")

        pg.commit()
        print("\nMigration complete.")

    except Exception as e:
        pg.rollback()
        raise e
    finally:
        pg.close()


if __name__ == "__main__":
    migrate()
