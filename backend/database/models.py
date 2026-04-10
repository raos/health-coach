import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, BigInteger, Float, String, Date, DateTime, Text, Boolean,
    ForeignKey, ForeignKeyConstraint, UniqueConstraint, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship

from database.encryption import EncryptedString


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Auth / User management tables
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    picture = Column(Text, nullable=True)
    auth_provider = Column(String(20), nullable=False, default="google")  # google | magic_link
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    last_logout_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), nullable=False, unique=True, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    used_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    max_uses = Column(Integer, default=1, nullable=False)
    use_count = Column(Integer, default=0, nullable=False)


class MagicLinkToken(Base):
    __tablename__ = "magic_link_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), nullable=False, index=True)
    token = Column(String(255), nullable=False, unique=True, index=True)
    invite_code = Column(String(50), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UserConsent(Base):
    __tablename__ = "user_consents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    consent_version = Column(String(20), nullable=False)
    consented_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(Text, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    ip_address = Column(String(50), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ---------------------------------------------------------------------------
# Health data tables (all scoped per user)
# ---------------------------------------------------------------------------

class WeightLog(Base):
    __tablename__ = "weight_logs"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_weight_logs_user_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    date = Column(Date, nullable=False)
    weight_lbs = Column(Float, nullable=False)
    body_fat_pct = Column(Float, nullable=True)
    notes = Column(Text)
    source = Column(String(20), default="manual")
    created_at = Column(DateTime, default=datetime.utcnow)


class BodyCompositionLog(Base):
    __tablename__ = "body_composition_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    date = Column(Date, nullable=False)
    body_fat_pct = Column(Float, nullable=False)
    lean_mass_lbs = Column(Float, nullable=True)
    fat_mass_lbs = Column(Float, nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Vo2MaxLog(Base):
    __tablename__ = "vo2max_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    date = Column(Date, nullable=False)
    vo2max = Column(Float, nullable=False)
    source = Column(String(20), default="garmin")
    created_at = Column(DateTime, default=datetime.utcnow)


class StravaActivity(Base):
    __tablename__ = "strava_activities"

    id = Column(BigInteger, primary_key=True)  # Strava activity ID (64-bit)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True, primary_key=True)
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
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True, primary_key=True)
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
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    workout_id = Column(String(100), nullable=False)
    exercise_name = Column(String(255), nullable=False)
    set_index = Column(Integer)
    weight_lbs = Column(Float)
    reps = Column(Integer)
    rpe = Column(Float)
    set_type = Column(String(20))  # 'normal' | 'warmup' | 'dropset'

    __table_args__ = (
        ForeignKeyConstraint(
            ["workout_id", "user_id"],
            ["hevy_workouts.id", "hevy_workouts.user_id"],
            name="hevy_exercise_sets_workout_user_fkey",
        ),
    )

    workout = relationship("HevyWorkout", back_populates="exercise_sets")


class TrainingPlan(Base):
    __tablename__ = "training_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    week_start = Column(Date, nullable=False)
    plan_json = Column(Text, nullable=False)
    plan_markdown = Column(Text)
    context_hash = Column(String(64))
    is_active = Column(Boolean, default=True)


class MealPlan(Base):
    __tablename__ = "meal_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    week_start = Column(Date, nullable=False)
    plan_json = Column(Text, nullable=False)
    calorie_target = Column(Integer)
    is_active = Column(Boolean, default=True)


class HealthInsight(Base):
    __tablename__ = "health_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    insight_type = Column(String(50), nullable=False)
    content_md = Column(Text, nullable=False)
    data_snapshot = Column(Text)
    is_read = Column(Boolean, default=False)


class CoachConversation(Base):
    __tablename__ = "coach_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    session_id = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' | 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"
    __table_args__ = (UniqueConstraint("user_id", "service", name="uq_oauth_tokens_user_service"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    service = Column(String(50), nullable=False)
    access_token = Column(EncryptedString, nullable=False)
    refresh_token = Column(EncryptedString)
    expires_at = Column(Integer)  # Unix timestamp
    athlete_id = Column(String(50))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DailyHealthCache(Base):
    """One row per user per calendar day — caches health data from Garmin, Google Fit, Apple Health, etc."""
    __tablename__ = "daily_health_cache"
    __table_args__ = (UniqueConstraint("user_id", "date", "source", name="uq_daily_health_user_date_source"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    date = Column(Date, nullable=False, index=True)
    source = Column(String(30), nullable=False, default="garmin")  # garmin | google_fit | apple_health | manual
    sleep_duration_hours = Column(Float)
    sleep_score = Column(Integer)
    deep_min = Column(Integer)
    rem_min = Column(Integer)
    light_min = Column(Integer)
    steps = Column(Integer)
    resting_hr = Column(Integer)
    synced_at = Column(DateTime, default=datetime.utcnow)


# Keep backward-compatible alias so existing code importing GarminDailyCache still works
GarminDailyCache = DailyHealthCache


class UserProfile(Base):
    __tablename__ = "user_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, unique=True, index=True)
    name = Column(String(100), default="")
    dob = Column(Date, nullable=True)
    height_inches = Column(Float, nullable=True)
    bf_goal_pct = Column(Float, nullable=True)
    weight_goal_lbs = Column(Float, nullable=True)
    vo2max_goal = Column(Float, nullable=True)
    goal_date = Column(Date, nullable=True)
    calorie_target = Column(Integer, default=2000)
    email = Column(String(200), default="")
    measurement_system = Column(String(10), default="imperial")
    training_device = Column(String(20), default="gym")
    breakfast_pref = Column(Text, nullable=True)
    lunch_pref = Column(Text, nullable=True)
    dinner_pref = Column(Text, nullable=True)
    # Multi-tenant new fields
    # mcp_api_key stores the encrypted key value (shown to user in Settings).
    # mcp_api_key_lookup stores an HMAC-SHA256 of the plaintext key and is used
    # for all equality lookups — encrypted ciphertexts are not equality-queryable.
    mcp_api_key = Column(EncryptedString, nullable=True, unique=True)
    mcp_api_key_lookup = Column(String(64), nullable=True, unique=True, index=True)
    hevy_api_key = Column(EncryptedString, nullable=True)
    training_days_strength = Column(Integer, default=3)
    training_days_cardio = Column(Integer, default=2)
    training_days_rest = Column(Integer, default=2)
    training_days_mobility = Column(Integer, default=0)
    preferred_exercises = Column(Text, nullable=True)    # JSON array
    exercises_to_avoid = Column(Text, nullable=True)     # JSON array with reasons
    dietary_preference = Column(String(30), default="omnivore")  # omnivore/vegetarian/vegan/pescatarian/other
    preferred_cuisines = Column(Text, nullable=True)     # JSON array
    weekly_email_enabled = Column(Boolean, default=True)
    weekly_email_cc = Column(String(200), nullable=True)
    onboarding_complete = Column(Boolean, default=False)
    invite_code_used = Column(String(50), nullable=True)
    # Telegram Bot
    telegram_chat_id = Column(BigInteger, nullable=True, unique=True, index=True)
    telegram_username = Column(String(100), nullable=True)
    telegram_connected_at = Column(DateTime, nullable=True)
    # Legacy recipients (kept for compat)
    training_plan_recipients = Column(Text, nullable=True)
    meal_plan_recipients = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NutritionLog(Base):
    __tablename__ = "nutrition_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    date = Column(Date, nullable=False, index=True)
    meal_type = Column(String(20), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    kcal = Column(Integer, nullable=False)
    protein_g = Column(Float, nullable=False)
    carbs_g = Column(Float, nullable=False)
    fat_g = Column(Float, nullable=False)
    source = Column(String(20), default="mcp")
    logged_at = Column(DateTime, default=datetime.utcnow)


class Supplement(Base):
    __tablename__ = "supplements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    dosage = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    logs = relationship("SupplementLog", back_populates="supplement", cascade="all, delete-orphan")


class SupplementLog(Base):
    __tablename__ = "supplement_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    supplement_id = Column(Integer, ForeignKey("supplements.id"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    taken_at = Column(DateTime, default=datetime.utcnow)

    supplement = relationship("Supplement", back_populates="logs")


class WeeklyCheckin(Base):
    """Weekly self-assessment bridging objective data with subjective state."""
    __tablename__ = "weekly_checkins"
    __table_args__ = (UniqueConstraint("user_id", "week_start", name="uq_weekly_checkins_user_week"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    week_start = Column(Date, nullable=False, index=True)
    training_adherence = Column(Integer, nullable=True)
    energy_level = Column(Integer, nullable=True)
    sleep_quality = Column(Integer, nullable=True)
    diet_adherence = Column(Integer, nullable=True)
    stress_level = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
