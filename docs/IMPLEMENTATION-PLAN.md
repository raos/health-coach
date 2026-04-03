# Multi-Tenant Implementation Plan

**Branch:** `feature/multi-tenant`  
**Base:** `main`  
**PRD:** [PRD-multi-tenant.md](PRD-multi-tenant.md)  
**Validation:** All phases must work on `localhost` before merging to `main`

---

## Branch Setup

- [ ] Create branch: `git checkout -b feature/multi-tenant`
- [ ] Push to remote: `git push -u origin feature/multi-tenant`
- [ ] Verify `main` is unchanged: `git log --oneline main -5`

---

## Phase 1 — Database Foundation (PostgreSQL + Alembic + User Model)

**Goal:** Swap SQLite for PostgreSQL locally, introduce Alembic migrations, and create the `User` table. No app functionality changes yet — this is pure infrastructure.

### 1.1 Local PostgreSQL Setup
- [ ] Install PostgreSQL locally if not present (`brew install postgresql@16`)
- [ ] Create local database: `createdb health_coach_dev`
- [ ] Add `DATABASE_URL=postgresql://localhost/health_coach_dev` to `.env`
- [ ] Remove `DATABASE_URL=sqlite:///./health.db` from `.env`

### 1.2 Backend Dependencies
- [ ] Add `psycopg2-binary==2.9.10` to `requirements.txt`
- [ ] Add `alembic==1.14.0` to `requirements.txt`
- [ ] Add `uuid` support note (PostgreSQL native UUID type)
- [ ] Run `pip install -r requirements.txt` in the virtualenv

### 1.3 SQLAlchemy Engine Update (`backend/database/engine.py`)
- [ ] Update `create_engine()` call to use `DATABASE_URL` from config (already reads from env, but remove WAL-mode SQLite pragma)
- [ ] Remove SQLite-specific `PRAGMA journal_mode=WAL` event listener
- [ ] Keep `Base.metadata.create_all(bind=engine)` for now (Alembic will take over after Phase 1)

### 1.4 Alembic Initialization
- [ ] Run `cd backend && alembic init alembic` to create `alembic/` directory
- [ ] Edit `alembic/env.py`:
  - Import `Base` from `database.models`
  - Set `target_metadata = Base.metadata`
  - Read `DATABASE_URL` from environment via `config.py`
- [ ] Edit `alembic.ini`: set `sqlalchemy.url` to `%(DATABASE_URL)s` (read from env)

### 1.5 New Database Models (`backend/database/models.py`)
- [ ] Add `import uuid` and PostgreSQL `UUID` type imports
- [ ] Add `User` model:
  - `id`: UUID PK (default `uuid.uuid4`)
  - `email`: String UNIQUE NOT NULL
  - `name`: String NOT NULL
  - `picture`: String nullable
  - `auth_provider`: String (`google` or `magic_link`)
  - `is_active`: Boolean default `True`
  - `is_admin`: Boolean default `False`
  - `last_logout_at`: DateTime nullable
  - `deleted_at`: DateTime nullable
  - `created_at`: DateTime default `utcnow`
- [ ] Add `InviteCode` model:
  - `id`: UUID PK
  - `code`: String UNIQUE NOT NULL
  - `created_by`: UUID FK → `users.id`
  - `used_by`: UUID FK → `users.id` nullable
  - `used_at`: DateTime nullable
  - `expires_at`: DateTime nullable
  - `max_uses`: Integer default 1
  - `use_count`: Integer default 0
- [ ] Add `MagicLinkToken` model:
  - `id`: UUID PK
  - `email`: String NOT NULL
  - `token`: String UNIQUE NOT NULL
  - `expires_at`: DateTime NOT NULL
  - `used`: Boolean default `False`
- [ ] Add `UserConsent` model:
  - `id`: UUID PK
  - `user_id`: UUID FK → `users.id` NOT NULL
  - `consent_version`: String NOT NULL
  - `consented_at`: DateTime NOT NULL
  - `ip_address`: String
  - `user_agent`: String
- [ ] Add `AuditLog` model:
  - `id`: UUID PK
  - `user_id`: UUID FK → `users.id` nullable
  - `action`: String NOT NULL
  - `ip_address`: String
  - `metadata_json`: JSON nullable
  - `created_at`: DateTime default `utcnow`

### 1.6 First Alembic Migration
- [ ] Run `alembic revision --autogenerate -m "initial_postgres_schema"` to generate migration
- [ ] Review generated migration file in `alembic/versions/` — ensure all existing tables + new User/InviteCode/etc. tables are included
- [ ] Run `alembic upgrade head`
- [ ] Verify all tables created in `health_coach_dev` with `psql health_coach_dev -c "\dt"`

### 1.7 Seed Sandeep's User Row
- [ ] Update `database/engine.py` seed function:
  - Create a `User` row for Sandeep (email from `ALLOWED_EMAIL` or `ADMIN_EMAIL` env var)
  - Set `is_admin = True`
  - Capture the UUID
  - Assign that UUID to all seeded rows (UserProfile, DexaScan, Vo2MaxLog)
- [ ] Run app: `uvicorn main:app --reload` — verify it starts without errors
- [ ] Verify seed data exists: check `users` table has one row

**Validation checkpoint:** App starts, connects to PostgreSQL, all tables exist, seed row present.

---

## Phase 2 — User Identity Layer (Auth + JWT + user_id in all tables)

**Goal:** Wire `user_id` into the JWT, add `user_id` FK to all 15 data tables, and update `verify_token()` to return `user_id`. No query filtering yet — that comes in Phase 3.

### 2.1 Config Changes (`backend/config.py`)
- [ ] Add `admin_email: str = ""` setting
- [ ] Remove `allowed_email: str = ""` (or keep temporarily for backwards-compat, mark deprecated)
- [ ] Add `google_fit_client_id: str = ""`
- [ ] Add `google_fit_client_secret: str = ""`
- [ ] Add `google_fit_redirect_uri: str = ""`

### 2.2 User table FK on all data tables (`backend/database/models.py`)
Add `user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)` (nullable for migration safety) to each:
- [ ] `WeightLog`
- [ ] `DexaScan`
- [ ] `Vo2MaxLog`
- [ ] `StravaActivity`
- [ ] `HevyWorkout`
- [ ] `HevyExerciseSet`
- [ ] `TrainingPlan`
- [ ] `MealPlan`
- [ ] `HealthInsight`
- [ ] `CoachConversation`
- [ ] `OAuthToken`
- [ ] `GarminDailyCache` (will be renamed in Phase 5)
- [ ] `NutritionLog`
- [ ] `WeeklyCheckin`
- [ ] `UserProfile`

### 2.3 New UserProfile fields (`backend/database/models.py`)
- [ ] `mcp_api_key`: String nullable (UUID, generated at account creation)
- [ ] `hevy_api_key`: String nullable (moved from env var)
- [ ] `training_days_strength`: Integer default 3
- [ ] `training_days_cardio`: Integer default 2
- [ ] `training_days_rest`: Integer default 2
- [ ] `training_days_mobility`: Integer default 0
- [ ] `preferred_exercises`: Text nullable (JSON array)
- [ ] `exercises_to_avoid`: Text nullable (JSON array with reasons)
- [ ] `dietary_preference`: String default `"vegetarian"` (omnivore/vegetarian/vegan/pescatarian/other)
- [ ] `preferred_cuisines`: Text nullable (JSON array)
- [ ] `weekly_email_enabled`: Boolean default True
- [ ] `weekly_email_cc`: String nullable
- [ ] `onboarding_complete`: Boolean default False
- [ ] `invite_code_used`: String nullable

### 2.4 Alembic Migration — Add user_id FKs + new profile fields
- [ ] Run `alembic revision --autogenerate -m "add_user_id_fks_and_profile_fields"`
- [ ] Review generated migration — confirm all 15 `user_id` columns and new `user_profile` columns appear
- [ ] Run `alembic upgrade head`

### 2.5 Data Migration — Assign Sandeep's user_id to existing rows
- [ ] Write a one-time migration script `scripts/migrate_assign_user_ids.py`:
  - Fetch Sandeep's `User.id` from DB
  - `UPDATE weight_logs SET user_id = <sandeep_uuid> WHERE user_id IS NULL`
  - Repeat for all 15 tables
  - Also set `user_profile.mcp_api_key = str(uuid.uuid4())` for Sandeep's row
  - Set `user_profile.onboarding_complete = True` for Sandeep (he doesn't need the wizard)
  - Set `user_profile.dietary_preference = 'vegetarian'`
- [ ] Run the script: `python scripts/migrate_assign_user_ids.py`
- [ ] Verify all rows have `user_id` set

### 2.6 Make user_id NOT NULL + fix unique constraints
- [ ] Write Alembic migration `"make_user_id_not_null_and_fix_constraints"`:
  - `ALTER TABLE weight_logs ALTER COLUMN user_id SET NOT NULL`
  - Repeat for all 15 tables
  - `DROP CONSTRAINT uq_weight_logs_date; ADD CONSTRAINT uq_weight_logs_user_date UNIQUE (user_id, date)`
  - `DROP CONSTRAINT uq_garmin_daily_cache_date; ADD CONSTRAINT uq_garmin_daily_cache_user_date UNIQUE (user_id, date)`
  - `DROP CONSTRAINT uq_weekly_checkins_week_start; ADD CONSTRAINT uq_weekly_checkins_user_week_start UNIQUE (user_id, week_start)`
  - `DROP CONSTRAINT uq_oauth_tokens_service; ADD CONSTRAINT uq_oauth_tokens_user_service UNIQUE (user_id, service)`
- [ ] Run `alembic upgrade head`

### 2.7 JWT + Auth Updates (`backend/routers/auth.py`, `backend/dependencies.py`)
- [ ] Update `auth.py` Google OAuth callback:
  - After validating invite code (Phase 4 — skip for now, accept all Google logins)
  - Look up or create `User` row by email
  - If new user: set `is_admin = True` if email matches `ADMIN_EMAIL` env var
  - Issue JWT with `user_id` (str(UUID)) in payload alongside existing claims
- [ ] Update `dependencies.py` `verify_token()`:
  - Extract `user_id` from JWT payload
  - Return `TokenData(user_id=UUID(...), email=..., name=..., is_admin=...)`
  - Reject tokens issued before `User.last_logout_at` (add DB lookup)
- [ ] Add `get_current_user()` dependency that returns the full `User` row
- [ ] Add `require_admin()` dependency that calls `get_current_user()` and raises 403 if not admin

**Validation checkpoint:** Login with Google, decode the JWT in browser DevTools → confirm `user_id` field is present.

---

## Phase 3 — Query Isolation (All Routers Filtered by user_id)

**Goal:** Every DB query in every router is now filtered by the `user_id` from the JWT. After this phase, two different Google accounts will see completely separate data.

### 3.1 Router: `weight.py`
- [ ] Add `user_id: UUID = Depends(verify_token)` parameter (extract from `TokenData`)
- [ ] `GET /api/weight` — filter by `user_id`
- [ ] `POST /api/weight` — set `user_id` on new row
- [ ] `GET /api/weight/latest` — filter by `user_id`

### 3.2 Router: `profile.py`
- [ ] `GET /api/profile` — filter `UserProfile` by `user_id`; remove `.first()` singleton pattern
- [ ] `PUT /api/profile` — filter by `user_id` before update
- [ ] Ensure `mcp_api_key` is returned in the profile response schema

### 3.3 Router: `dashboard.py`
- [ ] All queries (WeightLog, HevyWorkout, StravaActivity, UserProfile, TrainingPlan, MealPlan) — filter by `user_id`

### 3.4 Router: `coach.py`
- [ ] `GET /api/coach/plan` — filter TrainingPlan by `user_id`
- [ ] `POST /api/coach/plan/generate` — pass `user_id` to `generate_training_plan()`; filter context queries by `user_id`
- [ ] `GET /api/coach/chat` + `POST /api/coach/chat` — filter `CoachConversation` by `user_id`
- [ ] `POST /api/coach/sync` — scope sync to `user_id`

### 3.5 Router: `nutrition.py`
- [ ] `GET /api/nutrition/plan` — filter `MealPlan` by `user_id`
- [ ] `POST /api/nutrition/plan/generate` — pass `user_id` to `generate_meal_plan()`
- [ ] `GET /api/nutrition/log` + `POST /api/nutrition/log` — filter `NutritionLog` by `user_id`
- [ ] `GET /api/nutrition/chat` + `POST /api/nutrition/chat` — filter `CoachConversation` (session `nutrition-default`) by `user_id`
- [ ] Email endpoints (shopping list, PDF) — use requesting user's profile for name/email; remove hardcoded "Sandeep and Preetha"

### 3.6 Router: `checkin.py`
- [ ] `POST /api/checkin` — set `user_id`; upsert using `(user_id, week_start)` unique constraint
- [ ] `GET /api/checkin` — filter by `user_id`

### 3.7 Router: `dexa.py`
- [ ] All queries — filter by `user_id`
- [ ] `POST /api/dexa` — set `user_id` on new row

### 3.8 Router: `garmin.py`
- [ ] `GET /api/garmin/daily` — filter `GarminDailyCache` by `user_id`
- [ ] `POST /api/garmin/paste-data` — set `user_id` on upserted row
- [ ] `POST /api/garmin/login` — scope Garmin session to `user_id` (session dir = `GARMIN_SESSION_DIR/<user_id>/`)
- [ ] `POST /api/garmin/verify-mfa` — pass `user_id` to identify which user's session is being completed

### 3.9 Router: `strava.py`
- [ ] `GET /api/strava/activities` — filter `StravaActivity` by `user_id`
- [ ] OAuth token storage — scope `OAuthToken` to `user_id`
- [ ] Strava callback: read `state` param to identify `user_id` (encode `user_id` into state when building auth URL)

### 3.10 Router: `hevy.py`
- [ ] All queries — filter by `user_id`
- [ ] Hevy sync: fetch `hevy_api_key` from `UserProfile` (by `user_id`) instead of config

### 3.11 Router: `health_advisor.py`
- [ ] Filter `HealthInsight`, `GarminDailyCache`, `UserProfile` by `user_id`

### 3.12 Router: `supplements.py`
- [ ] Filter `Supplement`, `SupplementLog` by `user_id`
- [ ] `POST` endpoints — set `user_id`

### 3.13 Router: `email.py`
- [ ] `POST /api/email/weekly-summary` — generate summary for requesting user only (no longer implicit single user)

### 3.14 MCP Server (`backend/mcp_server.py`)
- [ ] `_get_user_id_from_key(api_key)` helper: query `UserProfile.mcp_api_key` → return `user_id`
- [ ] SSE endpoint: validate key → look up `user_id` → store in connection context
- [ ] All 14 tool handlers: accept `user_id` param, filter all DB queries with it
- [ ] MCP tools that call Claude: pass `user_id` to service functions

### 3.15 Claude Service (`backend/services/claude_service.py`)
- [ ] `generate_training_plan(user_id, ...)` — add `user_id` to context hash prefix; fetch `UserProfile` by `user_id`
- [ ] `generate_meal_plan(user_id, ...)` — fetch `UserProfile` by `user_id`
- [ ] `chat_with_coach(user_id, ...)` — filter conversation history by `user_id`
- [ ] `chat_with_nutritionist(user_id, ...)` — filter by `user_id`

**Validation checkpoint:** Log in as Sandeep → generate a training plan. Verify data is correct and unchanged. (A second user test comes in Phase 4 after invite codes are wired.)

---

## Phase 4 — Auth Flows (Invite Codes + Magic Link + Onboarding Wizard)

**Goal:** New users can sign up via invite code. The onboarding wizard collects their profile. Magic link login works as an alternative to Google OAuth.

### 4.1 Invite Code Backend
- [ ] `POST /api/admin/invite-codes` — generate a new code (admin only); accepts `{ expires_at?, max_uses? }`
- [ ] `GET /api/admin/invite-codes` — list all codes with status (admin only)
- [ ] `DELETE /api/admin/invite-codes/{code}` — revoke unused code (admin only)
- [ ] Helper `validate_invite_code(code, db)` — checks exists, not expired, not exhausted; raises `HTTPException(400)` on failure; increments `use_count` and sets `used_by` / `used_at` on success
- [ ] Google OAuth callback (`auth.py`): after user info is fetched, check if invite code was passed (via `state` param or `code` query param on the pre-auth screen); call `validate_invite_code()`; create `User` row; redirect to onboarding

### 4.2 Magic Link Backend
- [ ] `POST /api/auth/magic-link/request` — accepts `{ email, invite_code }`; validates invite code; generates UUID token; stores in `MagicLinkToken` (15-min expiry); sends email via Resend
- [ ] `GET /api/auth/magic-link/verify?token=<uuid>` — validates token (not expired, not used); creates `User` row if new; marks token used; issues JWT; redirects to `/auth/callback?token=<jwt>`

### 4.3 Consent Recording
- [ ] After invite code validated and `User` row created: create `UserConsent` row with `consent_version = "v1.0"`, IP, user agent
- [ ] `AuditLog` entry: action `"consent_given"`

### 4.4 Onboarding Wizard Backend
- [ ] `GET /api/profile/onboarding-status` — returns `{ onboarding_complete: bool }`
- [ ] Existing `PUT /api/profile` endpoint handles all wizard form saves — no new endpoint needed; just ensure `onboarding_complete` can be set to `true`
- [ ] `POST /api/profile/complete-onboarding` — sets `onboarding_complete = true`, creates `UserProfile` if not exists, creates `AuditLog` entry `"onboarding_complete"`
- [ ] Auto-generate `mcp_api_key` on first `UserProfile` creation (if null)

### 4.5 Welcome Email
- [ ] On account creation: send welcome email via Resend with app URL + onboarding instructions
- [ ] Email template: plain HTML, personalized with user name

### 4.6 Frontend: Login Page Updates (`frontend/src/pages/Login.tsx`)
- [ ] Add invite code input field (shown below the Google sign-in button)
- [ ] Add "Sign in with email (magic link)" tab/toggle
- [ ] Magic link tab: email input + invite code input + submit → calls `POST /api/auth/magic-link/request`
- [ ] Show success message: "Check your email for a login link"
- [ ] Error states: invalid invite code, expired invite code, email not recognized

### 4.7 Frontend: Onboarding Wizard (`frontend/src/pages/Onboarding.tsx`)
- [ ] 5-step wizard with progress indicator (step 1 of 5)
- [ ] **Step 1 (Welcome + Consent):** Name, DOB, height, measurement system; Privacy Policy + ToS links; explicit consent checkbox — disabled "Next" until checked
- [ ] **Step 2 (Goals):** BF% goal, VO2 max goal, goal date, current weight (required), current BF% (optional)
- [ ] **Step 3 (Training Prefs):** Training device (Tonal/Gym/Bodyweight radio), strength/cardio/rest/mobility days; preferred exercises textarea; exercises to avoid textarea
- [ ] **Step 4 (Nutrition Prefs):** Dietary preference dropdown, calorie target, preferred cuisines (chips/tags), breakfast/lunch/dinner prefs
- [ ] **Step 5 (Integrations):** Connect Strava button, Hevy API key input, Garmin connect button, Google Fit button, Apple Health instructions; "Skip all" button
- [ ] Each step saves to `PUT /api/profile` on "Next"; back navigation preserves state
- [ ] Final step: calls `POST /api/profile/complete-onboarding`, redirects to Dashboard

### 4.8 Frontend: ProtectedRoute Update (`frontend/src/components/auth/ProtectedRoute.tsx`)
- [ ] After token check: call `GET /api/profile/onboarding-status`
- [ ] If `onboarding_complete = false` → redirect to `/onboarding`
- [ ] Exception: `/onboarding` route itself must NOT redirect (avoid infinite loop)

### 4.9 Frontend: App.tsx Routing
- [ ] Add `/onboarding` route inside `ProtectedRoute`
- [ ] Add `/magic-link-sent` confirmation page (simple static page)
- [ ] Add `/auth/magic-link/verify` route (same pattern as `/auth/callback` — extracts JWT, stores, redirects)

**Validation checkpoint:**
- Generate an invite code via `curl` or the DB directly (admin UI comes in Phase 6)
- Sign in with a second Google account using that invite code
- Verify onboarding wizard appears and works end-to-end
- After completing onboarding, verify the new user lands on Dashboard with empty data (no bleed from Sandeep's account)

---

## Phase 5 — Per-User Integrations

**Goal:** Strava, Hevy, Garmin, Google Fit, and Apple Health all work per-user with isolated credentials and data.

### 5.1 Strava Per-User OAuth
- [ ] `GET /api/strava/auth/url` — encode `user_id` into OAuth `state` param (sign it with `JWT_SECRET_KEY` or store in a short-lived `OAuthState` table)
- [ ] `GET /api/strava/auth/callback` — decode `state` to get `user_id`; store `OAuthToken` with that `user_id`
- [ ] `GET /api/strava/status` — check if requesting user has a Strava token
- [ ] Strava sync service: accept `user_id`, fetch that user's token, sync to `StravaActivity` with `user_id`

### 5.2 Hevy Per-User API Key
- [ ] Settings page: text input for Hevy API key → saves to `UserProfile.hevy_api_key` via `PUT /api/profile`
- [ ] `hevy_service.py` / `hevy_api_client.py`: accept `api_key` parameter; remove read from `config.hevy_api_key`
- [ ] Hevy sync router: fetch `UserProfile.hevy_api_key` for the requesting user before syncing
- [ ] `GET /api/hevy/status` — return whether user has a Hevy API key configured

### 5.3 Garmin Per-User Sessions
- [ ] Session directory: `{GARMIN_SESSION_DIR}/{user_id}/` instead of flat `GARMIN_SESSION_DIR`
- [ ] `POST /api/garmin/login`: create user-scoped session dir; scope thread state to `user_id`
- [ ] `POST /api/garmin/verify-mfa`: look up thread by `user_id`
- [ ] `POST /api/garmin/import-tokens`: write tokens to user-scoped dir
- [ ] `POST /api/garmin/paste-data`: set `user_id` on upserted `GarminDailyCache` row
- [ ] `GET /api/garmin/status` — return whether user has a Garmin session

### 5.4 Rename GarminDailyCache → DailyHealthCache
- [ ] Rename model class: `GarminDailyCache` → `DailyHealthCache`, table name `daily_health_cache`
- [ ] Add `source` column: String default `"garmin"` (garmin / google_fit / apple_health / manual)
- [ ] Write Alembic migration: rename table, add column, update unique constraint to `(user_id, date, source)`
- [ ] Update all references: `garmin.py` router, `claude_service.py`, `weekly_summary_service.py`, `mcp_server.py`, dashboard router
- [ ] Run `alembic upgrade head`

### 5.5 Google Fit Integration
- [ ] Register OAuth app in Google Cloud Console; add `GOOGLE_FIT_CLIENT_ID`, `GOOGLE_FIT_CLIENT_SECRET`, `GOOGLE_FIT_REDIRECT_URI` to `.env`
- [ ] New router `backend/routers/google_fit.py`:
  - `GET /api/google-fit/auth/url` — build OAuth URL with `user_id` in state
  - `GET /api/google-fit/auth/callback` (public) — exchange code, store token in `OAuthToken(service="google_fit")`
  - `POST /api/google-fit/sync` — trigger manual sync for requesting user
  - `GET /api/google-fit/status` — connection status
- [ ] New service `backend/services/google_fit_service.py`:
  - `sync_daily_data(user_id, date)` — call `fitness.googleapis.com/fitness/v1/users/me/dataset:aggregate`
  - Parse steps, sleep duration, resting HR from response
  - Upsert into `DailyHealthCache` with `source = "google_fit"`
- [ ] Register router in `main.py`
- [ ] Settings page: "Connect Google Fit" button

### 5.6 Apple Health Webhook
- [ ] New router endpoint in `backend/routers/health_data.py`:
  - `POST /api/health/apple-health/webhook` (public, no JWT)
  - Auth: `X-MCP-Key: <mcp_api_key>` header → look up user
  - Accept HealthKit JSON payload from Health Auto Export app
  - Parse: `StepCount`, `SleepAnalysis`, `RestingHeartRate`, `HeartRateVariabilitySDNN`, `BodyMass`
  - Upsert into `DailyHealthCache` with `source = "apple_health"`
- [ ] Register in `main.py` as a public route (before the JWT block)
- [ ] Settings page: show webhook URL + MCP key + setup instructions for Health Auto Export

**Validation checkpoint:**
- Connect Strava with your own account → verify activities appear
- Enter Hevy API key → verify workouts sync
- Paste Garmin data → verify it appears under your user only
- Confirm a second test user sees none of your health data

---

## Phase 6 — Admin Panel

**Goal:** A `/admin` UI page for managing users and invite codes. Accessible only to admin accounts.

### 6.1 Admin API Endpoints (`backend/routers/admin.py`)
- [ ] `GET /api/admin/users` — list all users (id, email, name, joined, onboarding_complete, is_active, integrations)
- [ ] `PATCH /api/admin/users/{user_id}` — toggle `is_active`; set `is_admin`
- [ ] `GET /api/admin/invite-codes` — list all codes with status
- [ ] `POST /api/admin/invite-codes` — generate code; accepts `{ expires_at?, max_uses? }`
- [ ] `DELETE /api/admin/invite-codes/{code}` — revoke
- [ ] `GET /api/admin/usage` — per-user counts of training plans, meal plans, AI messages
- [ ] `GET /api/admin/audit-log` — paginated audit log; optional filter `?user_id=`
- [ ] All routes: `Depends(require_admin)`
- [ ] Register in `main.py` with `dependencies=[Depends(require_admin)]`

### 6.2 Admin Frontend (`frontend/src/pages/Admin.tsx`)
- [ ] Protected route — redirect to `/` if JWT `is_admin` is not `true`
- [ ] **Users tab:** Table with columns: email, name, joined, onboarding, active toggle, integrations badges
- [ ] **Invite Codes tab:**
  - Generate code form: expiry date picker, max uses input
  - Table: code, status (unused/used/expired), used by email, used at
  - Copy-to-clipboard button for each code
  - Revoke button for unused codes
- [ ] **Usage tab:** Per-user row with plan/message counts
- [ ] **Audit Log tab:** Paginated table with user email, action, timestamp, IP

### 6.3 Sidebar Admin Link
- [ ] `Sidebar.tsx`: decode JWT in `localStorage` → if `is_admin === true`, show "Admin" nav item linking to `/admin`
- [ ] `App.tsx`: add `/admin` route inside `ProtectedRoute`

### 6.4 Frontend API Client
- [ ] Add `frontend/src/api/admin.ts` with typed functions for all admin endpoints

**Validation checkpoint:** Log in as Sandeep → see Admin link in sidebar → generate an invite code → copy it → use it to sign up a second Google account → see both users in the Users tab.

---

## Phase 7 — Claude Prompts (Dynamic Per-User Context)

**Goal:** All hardcoded "Sandeep Rao", "Tonal", "vegetarian + eggs" references in prompts are replaced with runtime user profile values.

### 7.1 Coach Prompts (`backend/prompts/coach_system.py`)
- [ ] `COACH_SYSTEM_PROMPT`: replace hardcoded "Sandeep Rao" with `{user_name}`
- [ ] Replace "Tonal smart gym (cable/pulley system only)" block with a conditional block:
  - If `training_device == "tonal"` → current Tonal cable-only constraint text
  - If `training_device == "gym"` → "Standard gym equipment: barbells, dumbbells, cable machines, machines"
  - If `training_device == "bodyweight"` → "Bodyweight only. No equipment."
- [ ] Add `{preferred_exercises}` injection: "User enjoys: {list}"
- [ ] Add `{exercises_to_avoid}` injection: "Avoid these exercises (user injury/preference): {list}"
- [ ] Add `{strength_days}`, `{cardio_days}`, `{rest_days}`, `{mobility_days}` injections
- [ ] `COACH_CHAT_SYSTEM`: same name/device/prefs injections

### 7.2 Nutrition Prompts (`backend/prompts/nutrition_system.py`)
- [ ] `NUTRITION_SYSTEM_PROMPT`: replace "Sandeep Rao, age 46" with `{user_name}, age {user_age}`
- [ ] Replace hardcoded "vegetarian + eggs" with `{dietary_preference}` block:
  - `vegetarian` → current vegetarian constraint
  - `vegan` → vegan constraint (no dairy, no eggs)
  - `omnivore` → no dietary restrictions
  - `pescatarian` → no meat but fish/seafood OK
- [ ] Replace hardcoded calorie target with `{calorie_target}`
- [ ] Add `{preferred_cuisines}` injection
- [ ] `NUTRITIONIST_CHAT_SYSTEM`: same injections + existing food log + meal plan context

### 7.3 Health Advisor Prompts (`backend/prompts/health_advisor_system.py`)
- [ ] Replace "Sandeep Rao" with `{user_name}`
- [ ] Inject `{user_age}` computed from DOB

### 7.4 Claude Service Updates (`backend/services/claude_service.py`)
- [ ] `generate_training_plan(user_id, ...)`: fetch `UserProfile` by `user_id`; build device/exercise prompt block; inject all new fields
- [ ] `generate_meal_plan(user_id, ...)`: inject dietary preference, cuisines, meal prefs
- [ ] Context hash for training plan: prefix with `user_id` + include `training_device`, `preferred_exercises`, `exercises_to_avoid`
- [ ] `chat_with_coach()`, `chat_with_nutritionist()`: inject user profile fields into system prompt

**Validation checkpoint:**
- Create a second user with "gym" device and "omnivore" diet
- Generate training plan → confirm no Tonal-specific exercises appear
- Generate meal plan → confirm no vegetarian restriction
- Generate Sandeep's training plan → confirm Tonal constraint still applies

---

## Phase 8 — Privacy & Account Management

**Goal:** Users can export their data, delete their account, and manage conversation history. All GDPR mechanisms work end-to-end.

### 8.1 Data Export (`backend/routers/account.py`)
- [ ] `GET /api/account/data-export` — gather all rows for `user_id` across all tables
  - Serialize to JSON per category
  - ZIP with `zipfile` module + `README.txt`
  - Return as `StreamingResponse` with `Content-Disposition: attachment; filename=health_data.zip`
- [ ] `AuditLog` entry: action `"data_export"`

### 8.2 Account Deletion
- [ ] `DELETE /api/account` — soft-delete: set `User.deleted_at = utcnow()`, `User.is_active = False`
- [ ] Garmin session directory deleted immediately on soft-delete
- [ ] `AuditLog` entry: action `"account_delete_requested"`
- [ ] Scheduled job in `main.py` APScheduler: daily check for users where `deleted_at < now() - 30 days` → hard purge all rows + delete `User` row
- [ ] `POST /api/account/cancel-deletion` — if within 30-day window, clear `deleted_at` and reactivate

### 8.3 Conversation History Clear
- [ ] `DELETE /api/coach/chat/history` — delete all `CoachConversation` rows for `user_id` where `session_id = "default"`
- [ ] `DELETE /api/nutrition/chat/history` — delete where `session_id = "nutrition-default"`

### 8.4 Logout + Session Revocation
- [ ] `POST /api/auth/logout` — set `User.last_logout_at = utcnow()`
- [ ] `verify_token()` in `dependencies.py`: after decoding JWT, check `iat` (issued-at) against `User.last_logout_at`; reject if token was issued before logout
- [ ] Frontend: logout button calls `POST /api/auth/logout` before clearing localStorage

### 8.5 Privacy Settings UI (Settings page)
- [ ] Add "Privacy" section to `Settings.tsx`:
  - Weekly email toggle → saves to `UserProfile.weekly_email_enabled`
  - Optional CC email field → saves to `UserProfile.weekly_email_cc`
  - "Clear AI conversation history" button (with confirmation)
  - "Download my data" button → triggers `GET /api/account/data-export`
  - "Delete account" button → danger zone, opens confirmation modal requiring typing "DELETE"
- [ ] On account deletion: redirect to `/login` with `?message=account_deletion_scheduled`

### 8.6 Placeholder Legal Pages
- [ ] `frontend/src/pages/Privacy.tsx` — static placeholder Privacy Policy page
- [ ] `frontend/src/pages/Terms.tsx` — static placeholder Terms of Service page
- [ ] Add public routes `/privacy` and `/terms` in `App.tsx` (outside `ProtectedRoute`)
- [ ] Add footer to login page and onboarding Step 1 with links to both

**Validation checkpoint:**
- Click "Download my data" → receive a ZIP with JSON files for all categories
- Click "Delete account" → type DELETE → confirm → get redirected to login
- Log back in with same account → get a "your account is scheduled for deletion" message (not a normal login)
- Logout → try to use the old JWT in Swagger → get 401

---

## Phase 9 — Weekly Summary + Email Per-User

**Goal:** The APScheduler weekly email fires for every user who has opted in, with their own personalized data.

### 9.1 Weekly Summary Service Update (`backend/services/weekly_summary_service.py`)
- [ ] `send_weekly_summary()` → refactor to `send_weekly_summary_for_user(user_id, db)`
- [ ] Add top-level `send_all_weekly_summaries(db)`: query all users with `weekly_email_enabled = True` and `is_active = True`; call `send_weekly_summary_for_user()` for each
- [ ] All data-gathering functions in the service: add `user_id` filter to every query
- [ ] Email recipient: `UserProfile.email` (or `User.email`)
- [ ] Email CC: `UserProfile.weekly_email_cc` (if set)
- [ ] Email subject/body: use `User.name` instead of hardcoded "Sandeep"

### 9.2 Scheduler Update (`backend/main.py`)
- [ ] Change APScheduler job from `send_weekly_summary()` → `send_all_weekly_summaries(db)`

### 9.3 Manual Trigger Update (`backend/routers/email.py`)
- [ ] `POST /api/email/weekly-summary` — trigger summary for requesting user only (uses `user_id` from JWT)

**Validation checkpoint:**
- `curl -X POST /api/email/weekly-summary -H "Authorization: Bearer <sandeep_token>"` → Sandeep receives email
- `curl -X POST /api/email/weekly-summary -H "Authorization: Bearer <test_user_token>"` → test user receives their own email (different data, different recipient)

---

## Phase 10 — Settings Page Cleanup + Final Polish

**Goal:** Settings page is fully per-user. All remaining hardcoded references are cleaned up. App is ready for a second real user.

### 10.1 Settings Page Integration Status (`frontend/src/pages/Settings.tsx`)
- [ ] Strava section: show connection status fetched from `GET /api/strava/status`
- [ ] Garmin section: show per-user connection status
- [ ] Hevy section: show API key input (pre-fill if already set); save via `PUT /api/profile`
- [ ] Google Fit section: show "Connect Google Fit" button + disconnect option
- [ ] Apple Health section: show webhook URL (`https://<host>/api/health/apple-health/webhook`) + user's MCP key; setup instructions collapsible
- [ ] MCP section: show user-specific SSE URL using `UserProfile.mcp_api_key`

### 10.2 Remove All Remaining Hardcoded References
- [ ] `backend/routers/nutrition.py`: remove all "Sandeep and Preetha" references; use dynamic user email + CC
- [ ] `backend/database/engine.py`: remove hardcoded `name="Sandeep Rao"`, `dob=date(1979,11,11)` from seed defaults (seed only creates the User row; UserProfile is created during onboarding)
- [ ] `backend/config.py`: add deprecation note on `allowed_email`; confirm removal is safe

### 10.3 `.env` Updates for Local Dev
- [ ] Add `ADMIN_EMAIL=<sandeep_email>` to `.env`
- [ ] Remove `ALLOWED_EMAIL` (or leave empty — the new code ignores it)
- [ ] Add `GOOGLE_FIT_CLIENT_ID`, `GOOGLE_FIT_CLIENT_SECRET`, `GOOGLE_FIT_REDIRECT_URI` (can be blank until Google Fit is needed)

### 10.4 MCP Server — Per-User Key in Response
- [ ] `GET /api/settings/status` endpoint: include `mcp_api_key` from the requesting user's `UserProfile` (already done for single user; confirm it returns the per-user key now)

### 10.5 Supplement Logs (`backend/routers/supplements.py`)
- [ ] Verify `user_id` filtering is applied to `Supplement` and `SupplementLog` (may have been missed in Phase 3)

### 10.6 CLAUDE.md Update
- [ ] Update `CLAUDE.md` to reflect new multi-user architecture, Alembic workflow, and new env vars

**Validation checkpoint (full end-to-end):**
1. Sandeep logs in → all existing data is intact
2. Generate an invite code via Admin panel
3. Second Google account signs up with invite code
4. Second user completes onboarding (gym, omnivore, different calorie target)
5. Second user generates a training plan → no Tonal exercises
6. Second user generates a meal plan → no vegetarian restriction
7. Second user connects their own Strava
8. Sandeep's dashboard shows only Sandeep's data
9. Second user's dashboard shows only their data
10. Both users get separate weekly summary emails
11. Second user downloads their data → ZIP contains only their rows
12. Admin panel shows both users

---

## Phase 11 — Railway Deployment Prep

**Goal:** App is ready to deploy to Railway with PostgreSQL. No SQLite. Alembic runs on every deploy.

### 11.1 Railway PostgreSQL
- [ ] Provision Railway PostgreSQL addon in the project
- [ ] Copy `DATABASE_URL` from Railway dashboard into Railway environment variables
- [ ] Set `GARMIN_SESSION_DIR=/data/garmin_sessions` in Railway env vars
- [ ] Set `ADMIN_EMAIL=<sandeep_email>` in Railway env vars
- [ ] Remove `ALLOWED_EMAIL` from Railway env vars

### 11.2 railway.toml
- [ ] Add `[deploy] releaseCommand = "alembic upgrade head"` to `railway.toml`
- [ ] Verify `Procfile` or start command is `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 11.3 Data Migration from Production SQLite
- [ ] Export current `health.db` data to JSON: `python scripts/export_sqlite_data.py`
- [ ] Import into Railway PostgreSQL: `python scripts/import_to_postgres.py --url <railway_db_url>`
- [ ] Verify Sandeep's data is intact in Railway Postgres

### 11.4 Vercel
- [ ] No changes needed for Vercel frontend deployment
- [ ] Confirm `VITE_API_URL` points to Railway backend URL

**Final validation:** Deploy to Railway → sign in via Railway URL → confirm all data present → generate a training plan → receive weekly summary email.

---

## Summary Checklist

| Phase | Description | Status |
|-------|-------------|--------|
| Branch | Create `feature/multi-tenant` branch | ☐ |
| Phase 1 | PostgreSQL + Alembic + User model | ☐ |
| Phase 2 | user_id FK on all tables + JWT changes | ☐ |
| Phase 3 | All router queries filtered by user_id | ☐ |
| Phase 4 | Invite codes + magic link + onboarding wizard | ☐ |
| Phase 5 | Per-user integrations (Strava, Hevy, Garmin, Google Fit, Apple Health) | ☐ |
| Phase 6 | Admin panel (UI + API) | ☐ |
| Phase 7 | Dynamic Claude prompts per user | ☐ |
| Phase 8 | Privacy: data export, account deletion, logout revocation | ☐ |
| Phase 9 | Per-user weekly summary emails | ☐ |
| Phase 10 | Settings cleanup + final polish + CLAUDE.md | ☐ |
| Phase 11 | Railway deployment with PostgreSQL | ☐ |

---

## Notes

- **Never merge to `main` until full end-to-end validation on localhost is complete**
- **Never delete `health.db`** until Railway Postgres import is verified
- Each phase should be committed separately so rollback is clean: `git commit -m "phase-N: description"`
- When testing with a second user: use a different Google account or a test Gmail; the invite code gate is enforced from Phase 4 onwards
- The `alembic/` directory must be committed to the branch so Railway can run migrations
