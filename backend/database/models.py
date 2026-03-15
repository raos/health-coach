from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, Float, String, Date, DateTime, Text, Boolean, ForeignKey
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class WeightLog(Base):
    __tablename__ = "weight_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True)
    weight_lbs = Column(Float, nullable=False)
    notes = Column(Text)
    source = Column(String(20), default="manual")
    created_at = Column(DateTime, default=datetime.utcnow)


class DexaScan(Base):
    __tablename__ = "dexa_scans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_date = Column(Date, nullable=False)
    total_weight_lbs = Column(Float, nullable=False)
    body_fat_pct = Column(Float, nullable=False)
    fat_mass_lbs = Column(Float, nullable=False)
    lean_mass_lbs = Column(Float, nullable=False)
    bone_mass_lbs = Column(Float)
    visceral_fat_lbs = Column(Float)
    ag_ratio = Column(Float)
    almi = Column(Float)       # Appendicular Lean Mass Index kg/m²
    ffmi = Column(Float)       # Fat-Free Mass Index kg/m²
    t_score = Column(Float)    # Bone density T-score
    facility = Column(String(100))
    notes = Column(Text)
    raw_pdf_path = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Vo2MaxLog(Base):
    __tablename__ = "vo2max_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    vo2max = Column(Float, nullable=False)
    source = Column(String(20), default="garmin")
    created_at = Column(DateTime, default=datetime.utcnow)


class StravaActivity(Base):
    __tablename__ = "strava_activities"

    id = Column(Integer, primary_key=True)  # Strava activity ID
    name = Column(String(255), nullable=False)
    activity_type = Column(String(50))
    start_date = Column(DateTime, nullable=False)
    distance_m = Column(Float)
    moving_time_s = Column(Integer)
    elapsed_time_s = Column(Integer)
    total_elevation = Column(Float)
    average_hr = Column(Integer)
    max_hr = Column(Integer)
    average_speed = Column(Float)
    kudos_count = Column(Integer)
    raw_json = Column(Text)
    synced_at = Column(DateTime, default=datetime.utcnow)


class HevyWorkout(Base):
    __tablename__ = "hevy_workouts"

    id = Column(String(100), primary_key=True)  # Hevy UUID
    title = Column(String(255))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    duration_s = Column(Integer)
    volume_lbs = Column(Float)
    raw_json = Column(Text)
    synced_at = Column(DateTime, default=datetime.utcnow)

    exercise_sets = relationship("HevyExerciseSet", back_populates="workout", cascade="all, delete-orphan")


class HevyExerciseSet(Base):
    __tablename__ = "hevy_exercise_sets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workout_id = Column(String(100), ForeignKey("hevy_workouts.id"), nullable=False)
    exercise_name = Column(String(255), nullable=False)
    set_index = Column(Integer)
    weight_lbs = Column(Float)
    reps = Column(Integer)
    rpe = Column(Float)
    set_type = Column(String(20))  # 'normal' | 'warmup' | 'dropset'

    workout = relationship("HevyWorkout", back_populates="exercise_sets")


class TrainingPlan(Base):
    __tablename__ = "training_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    week_start = Column(Date, nullable=False)
    plan_json = Column(Text, nullable=False)
    plan_markdown = Column(Text)
    context_hash = Column(String(64))
    is_active = Column(Boolean, default=True)


class MealPlan(Base):
    __tablename__ = "meal_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    week_start = Column(Date, nullable=False)
    plan_json = Column(Text, nullable=False)
    calorie_target = Column(Integer)
    is_active = Column(Boolean, default=True)


class HealthInsight(Base):
    __tablename__ = "health_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    insight_type = Column(String(50), nullable=False)
    content_md = Column(Text, nullable=False)
    data_snapshot = Column(Text)
    is_read = Column(Boolean, default=False)


class CoachConversation(Base):
    __tablename__ = "coach_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service = Column(String(50), nullable=False, unique=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    expires_at = Column(Integer)  # Unix timestamp
    athlete_id = Column(String(50))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserProfile(Base):
    __tablename__ = "user_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), default="Sandeep Rao")
    dob = Column(Date, default=date(1979, 11, 11))
    height_inches = Column(Float, default=68.0)  # 5'8" — update if different
    bf_goal_pct = Column(Float, default=18.0)
    vo2max_goal = Column(Float, default=50.0)
    goal_date = Column(Date, default=date(2026, 12, 31))
    calorie_target = Column(Integer, default=2200)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
