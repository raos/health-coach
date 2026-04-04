#!/usr/bin/env python3
"""
Migration: single-user schema → multi-tenant schema
Run from the project root:  python backend/scripts/migrate_to_multitenant.py

What this does:
  1. Recreates the `users` table with UUID PK + new columns (was empty / integer PK)
  2. Creates the admin user row (m.sandeep.rao@gmail.com) sourced from user_profile
  3. Adds `user_id` column to every data table and backfills with admin UUID
  4. Recreates `oauth_tokens` with the new UNIQUE (user_id, service) constraint
  5. Adds all missing multi-tenant columns to `user_profile`
  6. Migrates `garmin_daily_cache` → `daily_health_cache` (new table name in models.py)

After running this script, restart the backend server.
`init_db()` will then create the remaining new tables (invite_codes, audit_logs, etc.).
"""
import sqlite3
import uuid
from datetime import datetime
import sys
import os

# Run from the project root
DB_PATH = "backend/health.db"

if not os.path.exists(DB_PATH):
    print(f"ERROR: DB not found at {DB_PATH}. Run from the project root.")
    sys.exit(1)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = OFF;")

# ── Determine admin user from user_profile ────────────────────────────────────
profile_row = conn.execute("SELECT * FROM user_profile WHERE id = 1;").fetchone()
ADMIN_EMAIL = (profile_row["email"] or "").strip() if profile_row else ""
ADMIN_NAME = (profile_row["name"] or "Sandeep Rao").strip() if profile_row else "Sandeep Rao"

if not ADMIN_EMAIL:
    # Fallback in case email column is empty
    ADMIN_EMAIL = "m.sandeep.rao@gmail.com"
    print(f"Warning: user_profile.email was empty, defaulting to {ADMIN_EMAIL}")

ADMIN_UUID = str(uuid.uuid4())
ADMIN_MCP_KEY = str(uuid.uuid4())

print(f"Admin email : {ADMIN_EMAIL}")
print(f"Admin name  : {ADMIN_NAME}")
print(f"Admin UUID  : {ADMIN_UUID}")
print(f"Admin MCP   : {ADMIN_MCP_KEY}")
print()

# ── 1. Recreate users table (was empty, old integer PK) ───────────────────────
print("1. Recreating users table with UUID PK...")
conn.execute("DROP TABLE IF EXISTS users;")
conn.execute("""
CREATE TABLE users (
    id TEXT NOT NULL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    picture TEXT,
    auth_provider VARCHAR(20) NOT NULL DEFAULT 'google',
    is_active BOOLEAN NOT NULL DEFAULT 1,
    is_admin BOOLEAN NOT NULL DEFAULT 0,
    last_logout_at DATETIME,
    deleted_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
""")
conn.execute("""
INSERT INTO users (id, email, name, auth_provider, is_active, is_admin, created_at)
VALUES (?, ?, ?, 'google', 1, 1, ?)
""", (ADMIN_UUID, ADMIN_EMAIL, ADMIN_NAME, datetime.utcnow().isoformat()))
print(f"   Created admin user: {ADMIN_EMAIL} ({ADMIN_UUID})")

# ── 2. Add user_id to data tables + backfill ─────────────────────────────────
DATA_TABLES = [
    "weight_logs", "dexa_scans", "vo2max_logs",
    "strava_activities", "hevy_workouts", "hevy_exercise_sets",
    "training_plans", "meal_plans", "nutrition_logs",
    "health_insights", "coach_conversations",
    "weekly_checkins", "supplement_logs", "supplements",
]
print("\n2. Adding user_id to data tables...")
for table in DATA_TABLES:
    # Check if table exists first
    exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,)
    ).fetchone()
    if not exists:
        print(f"   {table}: table does not exist, skipping")
        continue
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT;")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            print(f"   {table}: ERROR adding column — {e}")
            continue
    count = conn.execute(f"SELECT COUNT(*) FROM {table};").fetchone()[0]
    conn.execute(f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL;", (ADMIN_UUID,))
    print(f"   {table}: backfilled {count} row(s)")

# ── 3. Recreate oauth_tokens with UNIQUE (user_id, service) ──────────────────
print("\n3. Recreating oauth_tokens...")
old_tokens = conn.execute("SELECT * FROM oauth_tokens;").fetchall()
conn.execute("DROP TABLE oauth_tokens;")
conn.execute("""
CREATE TABLE oauth_tokens (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    service VARCHAR(50) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at INTEGER,
    athlete_id VARCHAR(50),
    updated_at DATETIME,
    UNIQUE (user_id, service)
);
""")
for row in old_tokens:
    conn.execute("""
        INSERT INTO oauth_tokens
            (user_id, service, access_token, refresh_token, expires_at, athlete_id, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (ADMIN_UUID, row["service"], row["access_token"], row["refresh_token"],
          row["expires_at"], row["athlete_id"], row["updated_at"]))
print(f"   Migrated {len(old_tokens)} token(s) → admin user")

# ── 4. Add missing columns to user_profile ───────────────────────────────────
print("\n4. Adding missing columns to user_profile...")
NEW_PROFILE_COLS = [
    ("user_id",                "TEXT"),
    ("mcp_api_key",            "TEXT"),
    ("hevy_api_key",           "TEXT"),
    ("training_days_strength", "INTEGER DEFAULT 3"),
    ("training_days_cardio",   "INTEGER DEFAULT 2"),
    ("training_days_rest",     "INTEGER DEFAULT 2"),
    ("training_days_mobility", "INTEGER DEFAULT 0"),
    ("preferred_exercises",    "TEXT"),
    ("exercises_to_avoid",     "TEXT"),
    ("dietary_preference",     "TEXT DEFAULT 'vegetarian'"),
    ("preferred_cuisines",     "TEXT"),
    ("weekly_email_enabled",   "BOOLEAN DEFAULT 1"),
    ("weekly_email_cc",        "TEXT"),
    ("onboarding_complete",    "BOOLEAN DEFAULT 0"),
    ("invite_code_used",       "TEXT"),
]
for col_name, col_def in NEW_PROFILE_COLS:
    try:
        conn.execute(f"ALTER TABLE user_profile ADD COLUMN {col_name} {col_def};")
        print(f"   Added: {col_name}")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            print(f"   {col_name}: ERROR — {e}")

conn.execute(
    "UPDATE user_profile SET user_id = ?, onboarding_complete = 1, mcp_api_key = ? WHERE id = 1;",
    (ADMIN_UUID, ADMIN_MCP_KEY),
)
print(f"   Set user_id + onboarding_complete=1 + mcp_api_key on profile row 1")

# ── 5. Migrate garmin_daily_cache → daily_health_cache ───────────────────────
print("\n5. Migrating garmin_daily_cache → daily_health_cache...")
garmin_rows = conn.execute("SELECT * FROM garmin_daily_cache;").fetchall()
existing_tables = {
    r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
}
if "daily_health_cache" not in existing_tables:
    conn.execute("""
    CREATE TABLE daily_health_cache (
        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        date DATE NOT NULL,
        source VARCHAR(30) NOT NULL DEFAULT 'garmin',
        sleep_duration_hours FLOAT,
        sleep_score INTEGER,
        deep_min INTEGER,
        rem_min INTEGER,
        light_min INTEGER,
        steps INTEGER,
        resting_hr INTEGER,
        synced_at DATETIME,
        UNIQUE (user_id, date, source)
    );
    """)
    for row in garmin_rows:
        conn.execute("""
            INSERT OR IGNORE INTO daily_health_cache
                (user_id, date, source, sleep_duration_hours, sleep_score,
                 deep_min, rem_min, light_min, steps, resting_hr, synced_at)
            VALUES (?, ?, 'garmin', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ADMIN_UUID, row["date"], row["sleep_duration_hours"], row["sleep_score"],
              row["deep_min"], row["rem_min"], row["light_min"],
              row["steps"], row["resting_hr"], row["synced_at"]))
    print(f"   Created daily_health_cache, migrated {len(garmin_rows)} row(s)")
else:
    # daily_health_cache exists — just ensure user_id is backfilled
    conn.execute(
        "UPDATE daily_health_cache SET user_id = ? WHERE user_id IS NULL;", (ADMIN_UUID,)
    )
    print("   daily_health_cache already exists; backfilled any NULL user_id rows")

conn.commit()
conn.close()

print(f"""
Migration complete.

  Admin user : {ADMIN_EMAIL}
  Admin UUID : {ADMIN_UUID}
  Admin MCP  : {ADMIN_MCP_KEY}

Next steps:
  1. Restart the backend server — init_db() will create the remaining new
     tables (invite_codes, audit_logs, magic_link_tokens, user_consents).
  2. The admin user ({ADMIN_EMAIL}) can now log in and will be recognized
     as admin (is_admin=True).
  3. To let srao.fitness.journey@gmail.com sign up, log in as admin, go to
     the admin panel, and create an invite code for them.
  4. After signing in, the new user must re-connect Strava via Settings
     (their OAuth token will be linked to their own user_id).
""")
