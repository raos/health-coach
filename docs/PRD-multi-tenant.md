# PRD: Multi-Tenant Health Coach App

**Version:** 1.0  
**Status:** Draft  
**Author:** Sandeep Rao  
**Last Updated:** 2026-04-02  

---

## 1. Executive Summary

The Health Coach App is currently a single-user personal AI coaching platform. This PRD describes the changes needed to make it available to other users while maintaining full data isolation, per-user integrations, and GDPR-compliant data handling.

**Beta strategy:** Invite-only via generated codes. No public sign-up.  
**Deployment:** Railway (backend + PostgreSQL) + Vercel (frontend), same as today.  
**Key principle:** Every piece of data — workouts, meals, health metrics, AI-generated plans, conversations — is scoped to the authenticated user. No data leaks between accounts.

---

## 2. Problem Statement

The current app hardcodes a single user ("Sandeep Rao") at every layer:
- No `user_id` on any database table
- Integrations (Garmin, Hevy, Strava) are per-deployment env vars, not per-user
- Claude prompts reference the user by name with hardcoded dietary and equipment constraints
- The MCP API key gives full access to all data with no user scoping
- `ALLOWED_EMAIL` in config allows exactly one Google account

This makes it impossible to safely onboard any other user without exposing one user's data to another.

---

## 3. Goals

- Full per-user data isolation across all 15 database tables
- Invite-code–gated sign-up (Google OAuth primary, magic link email as fallback)
- Per-user integrations: Strava, Hevy, Garmin, Google Fit, Apple Health
- Per-user MCP API keys for Claude desktop/mobile integration
- Guided 5-step onboarding wizard
- Admin UI to manage users and invite codes
- GDPR-compliant data handling (export, deletion, consent, audit log)
- Migrate database from SQLite to PostgreSQL

## 4. Non-Goals (v1)

- Billing / payments (Stripe)
- Social features (sharing plans, leaderboards, community)
- Native mobile app
- Apple Watch / Fitbit native integrations
- Admin ability to impersonate users
- Rate limiting per user (document cost risk; implement later)
- User-to-user referrals

---

## 5. User Stories

### New User
1. I receive an invite code from the admin.
2. I visit the app, click "Sign in with Google" (or "Email magic link"), and enter my invite code.
3. I am guided through a 5-step onboarding wizard: personal details → goals → training prefs → nutrition prefs → integrations.
4. I land on the Dashboard with a personalized training plan and meal plan ready to generate.
5. I see my own MCP API key in Settings, which I add to Claude desktop to interact with my data via voice/chat.

### Returning User
1. I sign in with Google. My JWT contains my `user_id`.
2. Every page shows only my data: my workouts, my meals, my weight trend.
3. I can update my profile, change my calorie target, and reconnect integrations from Settings.
4. Every Sunday at 7:30 PM ET I receive a personalized weekly summary email.

### Admin (Sandeep)
1. I visit `/admin` (only accessible to my account).
2. I generate invite codes with optional expiry dates and share them with friends.
3. I can see all registered users, their onboarding status, and disable accounts if needed.
4. I can view the audit log for any user.

### Compliance-Conscious User
1. I can download all my data as a ZIP from Settings → Privacy.
2. I can delete my account. All my data is purged within 30 days.
3. I can clear my AI conversation history independently.
4. I agreed to the Privacy Policy and Terms of Service at sign-up; a record of that consent is stored.

---

## 6. Functional Requirements

### 6.1 Authentication & User Management

**Google OAuth (primary)**
- Extend to any Google account (remove `ALLOWED_EMAIL` env var restriction)
- During the OAuth callback: validate invite code entered at sign-up, create `User` row if new, issue JWT
- JWT payload: `user_id` (UUID), `email`, `name`, `picture`, `is_admin`, `exp`

**Magic link email (fallback)**
- User enters email on login page → backend generates a `MagicLinkToken` (UUID, 15-min expiry) → sends link via Resend
- User clicks link → backend validates token, creates `User` row if new (requires invite code in the token or as a query param), issues JWT
- Token is single-use; mark `used = true` after first redemption

**Invite codes**
- Admin generates codes in the Admin UI (optionally with expiry)
- User enters code during sign-up (Google OAuth: shown on a pre-auth screen; magic link: included in the request)
- On first sign-in: validate code → mark `used_by`, `used_at` → proceed
- Used or expired codes return a clear error message

**Session management**
- JWT expiry: 30 days (unchanged)
- Add `User.last_logout_at`; JWTs issued before this timestamp are rejected by `verify_token()`
- Logout button updates `last_logout_at` and clears localStorage token

**Welcome email**
- Sent on first account creation via Resend

---

### 6.2 Guided Onboarding Wizard

Displayed after first sign-in. User cannot access the Dashboard until all 5 steps are complete (`UserProfile.onboarding_complete = false`). `ProtectedRoute` checks this flag and redirects to `/onboarding` if needed.

**Step 1: Welcome & Consent**
- Confirm name (pre-filled from Google), date of birth, height, measurement system (imperial/metric)
- Display Privacy Policy and Terms of Service links
- Explicit consent checkbox: "I consent to the collection and processing of my health data as described in the Privacy Policy"
- Consent record saved to `UserConsent` table before any health data is written

**Step 2: Goals**
- Target body fat % (optional)
- VO2 max goal (optional)
- Goal date
- Current weight (required — seeds first weight log entry)
- Current body fat % (optional — seeds first DEXA baseline if provided)

**Step 3: Training Preferences**
- Training device: Tonal / Gym / Bodyweight
- Days per week: Strength training, Cardio, Rest, Mobility
- Preferred exercises (free text, e.g., "I like squats and pull-ups")
- Exercises to avoid (free text, e.g., "No overhead press — shoulder impingement")

**Step 4: Nutrition Preferences**
- Dietary preference: Omnivore / Vegetarian / Vegan / Pescatarian / Gluten-free / Other
- Calorie target (kcal/day)
- Preferred cuisines (multi-select or free text: Mediterranean, South Indian, Mexican, etc.)
- Breakfast preferences (free text)
- Lunch preferences (free text)
- Dinner preferences (free text)

**Step 5: Integrations (all optional)**
- **Strava**: "Connect Strava" button → OAuth flow
- **Hevy**: Text input for API key
- **Garmin**: "Connect Garmin" → triggers existing MFA flow
- **Google Fit**: "Connect Google Fit" → OAuth flow
- **Apple Health**: Instructions for configuring Health Auto Export webhook
- "Skip all for now" → can connect later in Settings

After step 5: set `onboarding_complete = true`, redirect to Dashboard.

---

### 6.3 User Profile & Settings

The Settings page already handles most profile fields. Extend it with:

**New profile fields**
| Field | Type | Notes |
|-------|------|-------|
| `training_days_strength` | Integer | Days/week |
| `training_days_cardio` | Integer | Days/week |
| `training_days_rest` | Integer | Days/week |
| `training_days_mobility` | Integer | Days/week |
| `preferred_exercises` | Text (JSON array) | |
| `exercises_to_avoid` | Text (JSON array) | With reason |
| `dietary_preference` | String enum | omnivore/vegetarian/vegan/pescatarian/other |
| `preferred_cuisines` | Text (JSON array) | |
| `weekly_email_enabled` | Boolean | Default true |
| `weekly_email_cc` | String | Optional CC address |
| `onboarding_complete` | Boolean | Set after wizard |
| `mcp_api_key` | String (UUID) | Auto-generated; shown in Settings |
| `hevy_api_key` | String | User-entered; moved from env var |
| `invite_code_used` | String | FK to InviteCode |

**Privacy settings section (new)**
- Toggle: "Receive weekly summary email"
- Optional CC email address
- Button: "Clear AI conversation history"
- Button: "Export my data" → triggers ZIP download
- Button: "Delete my account" → confirmation dialog requiring user to type "DELETE"

---

### 6.4 Training Plans

- Add `user_id` FK to `TrainingPlan` table
- Claude prompt: dynamically inject user's name, training device, preferred exercises, and exercises to avoid
  - If `training_device = "tonal"` → current Tonal cable-only constraint applies
  - If `training_device = "gym"` → allow free weights, barbells, dumbbells, cables
  - If `training_device = "bodyweight"` → bodyweight only
- Context hash must include `user_id` prefix to prevent cross-user cache collisions

---

### 6.5 Nutrition

- Add `user_id` FK to `MealPlan` and `NutritionLog` tables
- Claude prompt: inject user's dietary preference, calorie target, cuisine prefs, meal prefs
  - Vegetarian constraint is only applied if `dietary_preference` is vegetarian/vegan
  - Cook-once rule (Tuesday–Sunday lunch = prior night's leftover) remains default; can be disabled by user preference
- Weekly summary email: per-user, respects `weekly_email_enabled` and `weekly_email_cc`
- Remove all hardcoded "Sandeep and Preetha" references from `routers/nutrition.py`

---

### 6.6 Health Metrics & Integrations

All integrations are per-user. Credentials are stored in user-scoped tables, not environment variables.

**Strava**
- `OAuthToken` table: add `user_id` FK; change `unique(service)` → `unique(user_id, service)`
- Add `state` param to Strava OAuth URL encoding `user_id` (as a signed JWT or opaque token in a short-lived `oauth_state` table)
- Callback reads `state` to identify which user completed the OAuth flow
- Strava callback endpoint remains public (called by Strava's servers)

**Hevy**
- `UserProfile.hevy_api_key`: user pastes their own Hevy API key in Settings
- `hevy_service.py`: accept `api_key` parameter instead of reading from `config`
- All Hevy sync calls pass the user's key

**Garmin**
- Session directories: `GARMIN_SESSION_DIR/<user_id>/`
- Login / MFA flow already uses threading; scope the thread state by `user_id`
- Paste-data fallback: add `user_id` to upsert logic in `routers/garmin.py`

**Google Fit**
- New OAuth 2.0 integration, same pattern as Strava
- `OAuthToken` table: `service = "google_fit"`, scoped to `user_id`
- New service: `backend/services/google_fit_service.py`
  - `sync_daily_data(user_id, date)`: fetches steps, sleep, resting HR from `fitness.googleapis.com`
  - Writes to `daily_health_cache` with `source = "google_fit"`
- Add to Settings page: "Connect Google Fit" button

**Apple Health (webhook bridge)**
- No Apple REST API exists for web apps; use a webhook bridge instead
- `POST /api/health/apple-health/webhook` — public endpoint, authenticated via `X-MCP-Key: <mcp_api_key>` header
- Accepts HealthKit-format JSON payloads (as produced by Health Auto Export iOS app)
- Parses: steps, sleep duration, resting heart rate, HRV, body weight
- Stores in `daily_health_cache` with `source = "apple_health"`
- Settings page: show webhook URL + user's MCP key with setup instructions for Health Auto Export

**daily_health_cache (renamed from garmin_daily_cache)**
- Add `user_id` FK
- Add `source` column: `garmin` / `google_fit` / `apple_health` / `manual`
- Change `unique(date)` → `unique(user_id, date, source)`

---

### 6.7 MCP Server (per-user)

- Each user has a unique `mcp_api_key` (UUID) generated at account creation, stored on `UserProfile`
- `GET /mcp/sse?key=<key>`: look up user by `mcp_api_key`, extract `user_id`, inject into all tool calls
- All 14 MCP tool handlers receive `user_id` and filter every DB query with it
- Apple Health webhook also reuses `mcp_api_key` for authentication (see §6.6)
- Settings page: display the user's personal MCP SSE URL:
  ```
  https://<host>/mcp/sse?key=<user_mcp_api_key>
  ```
- Key is treated as a secret: masked in UI by default, revealed on click, never logged

---

### 6.8 Admin Panel

Route: `/admin` — accessible only to users where `is_admin = true` in their JWT. The first admin is designated via `ADMIN_EMAIL` env var (backend sets `is_admin = true` on that user's row at login).

**Users tab**
- Table: email, name, joined date, onboarding complete, last active, integrations connected
- Toggle: enable / disable account (sets `User.is_active = false`)
- Button: view audit log for user

**Invite Codes tab**
- Generate new invite code (optional: expiry date, single-use or multi-use)
- Table: all codes, status (unused / used / expired), used by, used at
- Button: revoke / delete unused codes

**Usage tab**
- Per-user: # training plans generated, # meal plans generated, # AI messages sent, # integrations connected
- Useful for understanding Claude API cost per user

**Audit Log tab**
- Global audit log with filter by user
- Shows: login events, data exports, account deletions, integration connects/disconnects, consent granted

---

### 6.9 Email & Notifications

- **Weekly summary**: APScheduler loops over all users with `weekly_email_enabled = true`; sends each user a personalized summary
- **Magic link**: Resend delivers login link to user's email
- **Welcome email**: Sent on account creation; includes link to complete onboarding
- **Data export ready**: Email notification when ZIP export is ready to download (if generation is async)
- All emails use Resend (already integrated); email templates are HTML (already built for weekly summary)

---

## 7. Privacy & Compliance

Health data is **special category personal data** under GDPR Article 9, CCPA, and equivalent regulations.

### 7.1 Legal Basis & Consent

- Explicit consent is required before any health data is collected (GDPR Art. 9(2)(a))
- Consent gate is in Onboarding Step 1, before any data is saved
- `UserConsent` table records: `user_id`, `consent_version`, `consented_at`, `ip_address`, `user_agent`
- When Privacy Policy is updated, `consent_version` is incremented; users are prompted to re-consent on next login
- Each third-party integration (Google Fit, Apple Health, Strava) has a separate consent disclosure at connect time

### 7.2 Right of Access (GDPR Art. 15)

- `GET /api/account/data-export` — generates a ZIP containing all user data
- Contents: profile, weight logs, DEXA scans, VO2 max logs, workouts, nutrition logs, meal plans, training plans, health metrics, conversation history, weekly check-ins
- Format: JSON files per category + `README.txt` describing each file
- Must be fulfilled within 30 days of request; no fee charged

### 7.3 Right to Erasure (GDPR Art. 17)

- `DELETE /api/account` — initiates account deletion
- Soft-delete: sets `User.deleted_at = now()`, disables login immediately
- Hard purge: 30 days after `deleted_at`, a scheduled job cascades deletes all rows tied to `user_id` across all tables
- Garmin session directory for the user is deleted at soft-delete time
- UI: confirmation dialog requires typing "DELETE" before submitting

### 7.4 Data Portability (GDPR Art. 20)

- Same endpoint as Right of Access (`/api/account/data-export`)
- Machine-readable JSON/CSV format
- Users can export individual categories (e.g., just nutrition logs) via query parameters

### 7.5 Data Minimization & Retention

- No third-party analytics without explicit consent (no Google Analytics, Mixpanel, etc.)
- Data retained while account is active; purged 30 days after deletion
- Users can clear coach/nutritionist conversation history independently from Settings

### 7.6 Security

- Database encryption at rest: Railway PostgreSQL (encryption enabled by default)
- All traffic over HTTPS (Railway enforces)
- MCP API keys: treated as secrets — never logged, masked in UI, displayed once
- JWT invalidation: `User.last_logout_at` — tokens issued before this are rejected
- Garmin credentials (email/password): never stored in the database; only garth session tokens on disk

### 7.7 User-Facing Legal Documents

| Route | Content |
|-------|---------|
| `/privacy` | Privacy Policy — what data is collected, why, retention period, who has access, user rights |
| `/terms` | Terms of Service |

Both are linked in the consent checkbox at sign-up and in the footer.

### 7.8 Audit Logging

- `AuditLog` table: every login, data export, account deletion, consent given, integration connected
- Retained minimum 90 days
- Viewable per-user in Admin panel

### 7.9 Regional Scope

| Regulation | Applicability | Approach |
|-----------|--------------|---------|
| GDPR (EU/EEA) | If any invited user is EU-based | All technical mechanisms above satisfy requirements; defer DPA and SCCs until needed |
| HIPAA (US) | App is not a covered entity (not a healthcare provider/insurer); HIPAA-aligned practices are good hygiene | Follow minimum-necessary and access-control principles |
| CCPA (California) | Access, deletion, opt-out of sale | Covered by data export and deletion; no data is sold |

---

## 8. Technical Architecture

### 8.1 New Database Tables

```
User
  id               UUID PK
  email            String UNIQUE
  name             String
  picture          String (nullable)
  auth_provider    Enum(google, magic_link)
  is_active        Boolean default=true
  is_admin         Boolean default=false
  last_logout_at   DateTime (nullable)
  deleted_at       DateTime (nullable)
  created_at       DateTime

InviteCode
  id               UUID PK
  code             String UNIQUE
  created_by       UUID FK User
  used_by          UUID FK User (nullable)
  used_at          DateTime (nullable)
  expires_at       DateTime (nullable)

MagicLinkToken
  id               UUID PK
  email            String
  token            String UNIQUE
  expires_at       DateTime
  used             Boolean default=false

UserConsent
  id               UUID PK
  user_id          UUID FK User
  consent_version  String
  consented_at     DateTime
  ip_address       String
  user_agent       String

AuditLog
  id               UUID PK
  user_id          UUID FK User (nullable)
  action           String
  ip_address       String
  metadata         JSON (nullable)
  created_at       DateTime
```

### 8.2 Modified Tables

| Table | Changes |
|-------|---------|
| `user_profile` | Add `user_id` UUID FK; add all new fields from §6.3; remove singleton pattern |
| `weight_logs` | Add `user_id`; change `unique(date)` → `unique(user_id, date)` |
| `garmin_daily_cache` → `daily_health_cache` | Add `user_id`, `source` column; change `unique(date)` → `unique(user_id, date, source)` |
| `weekly_checkins` | Add `user_id`; change `unique(week_start)` → `unique(user_id, week_start)` |
| `oauth_tokens` | Add `user_id`; change `unique(service)` → `unique(user_id, service)` |
| `training_plans` | Add `user_id` |
| `meal_plans` | Add `user_id` |
| `nutrition_logs` | Add `user_id` |
| `hevy_workouts` | Add `user_id` |
| `hevy_exercise_sets` | Add `user_id` |
| `strava_activities` | Add `user_id` |
| `health_insights` | Add `user_id` |
| `coach_conversations` | Add `user_id` |
| `dexa_scans` | Add `user_id` |
| `vo2max_logs` | Add `user_id` |

### 8.3 Auth Layer Changes

- `backend/dependencies.py`: `verify_token()` returns `TokenData` with `user_id: UUID`, plus existing `email`, `name`, `is_admin`
- Add `get_current_user()` dependency that fetches the `User` row (used for admin-only routes)
- JWT creation in `auth.py`: include `user_id` and `is_admin` in payload
- Remove `ALLOWED_EMAIL` env var; add `ADMIN_EMAIL` env var (sets `is_admin=true` on that account)

### 8.4 Router Layer Changes

Every protected router:
- Receives `user_id` from `Depends(verify_token)`
- Filters every DB query with `.filter(Model.user_id == user_id)`
- Removes all `.first()` singleton queries

Affected routers: `auth`, `coach`, `nutrition`, `checkin`, `weight`, `dashboard`, `profile`, `garmin`, `strava`, `hevy`, `dexa`, `health_advisor`, `supplements`, `email`

### 8.5 Claude Prompts

All prompts in `backend/prompts/` must be updated to remove hardcoded references:

| File | Change |
|------|--------|
| `coach_system.py` | Replace "Sandeep Rao, Tonal" with `{user_name}`, `{training_device}`; inject `{preferred_exercises}`, `{exercises_to_avoid}` |
| `nutrition_system.py` | Replace "Sandeep Rao, vegetarian + eggs" with `{user_name}`, `{dietary_preference}`, `{preferred_cuisines}`, meal prefs |
| `health_advisor_system.py` | Replace "Sandeep Rao" with `{user_name}` |

Device-specific prompt logic:
- `tonal` → current cable-only Tonal constraint
- `gym` → free weights, barbells, dumbbells, cable machines
- `bodyweight` → bodyweight only, no equipment

### 8.6 MCP Server Changes

- `mcp_server.py`: `_get_user_id_from_key(key)` → queries `UserProfile.mcp_api_key`, returns `user_id`
- All 14 tool handlers: accept `user_id` arg, pass to every DB query
- Apple Health webhook: new route added (`/api/health/apple-health/webhook`)

### 8.7 Frontend Changes

| File | Change |
|------|--------|
| `src/App.tsx` | Add `/onboarding` and `/admin` routes inside `ProtectedRoute` |
| `src/components/auth/ProtectedRoute.tsx` | After token check, fetch profile; redirect to `/onboarding` if `onboarding_complete = false` |
| `src/pages/Onboarding.tsx` | New 5-step wizard component |
| `src/pages/Admin.tsx` | New admin panel (users, invite codes, usage, audit log) |
| `src/pages/Settings.tsx` | Add: Hevy API key input, user-specific MCP URL, privacy settings section (export, delete, conversation clear) |
| `src/components/layout/Sidebar.tsx` | Add "Admin" nav item, visible only if `is_admin = true` in decoded JWT |
| `src/pages/Login.tsx` | Add magic link option; add invite code input |

### 8.8 Database Migration Strategy

Use **Alembic** for all schema changes.

**Migration sequence:**
1. Add `User`, `InviteCode`, `MagicLinkToken`, `UserConsent`, `AuditLog` tables
2. Add `user_id` columns (nullable) to all 15 affected tables
3. Seed migration: create Sandeep's `User` row; assign all existing rows' `user_id` to Sandeep's UUID
4. Make `user_id` NOT NULL on all tables
5. Drop old unique constraints; add compound unique constraints
6. Rename `garmin_daily_cache` to `daily_health_cache`; add `source` column
7. Add all new `UserProfile` fields with defaults

**Alembic setup:**
```bash
cd backend
pip install alembic
alembic init alembic
# Configure alembic.ini and env.py to use DATABASE_URL
alembic revision --autogenerate -m "multi_tenant_phase1"
alembic upgrade head
```

---

## 9. Deployment Changes

### Railway (backend + PostgreSQL)

- Provision Railway PostgreSQL addon; set `DATABASE_URL` env var
- Remove `DATABASE_URL=sqlite:///./health.db` from `.env`
- Add `ADMIN_EMAIL=sandeeprao@...` env var
- Garmin session dirs: `GARMIN_SESSION_DIR=/data/garmin_sessions` (token files go in `<dir>/<user_id>/`)
- `railway.toml`: add release command `alembic upgrade head`

### Vercel (frontend)

- No changes. Static React build; all env is `VITE_API_URL`.

---

## 10. New Environment Variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string (replaces SQLite) |
| `ADMIN_EMAIL` | Email of the initial admin user; `is_admin` set on first login |
| `GOOGLE_FIT_CLIENT_ID` | Google Fit OAuth client |
| `GOOGLE_FIT_CLIENT_SECRET` | Google Fit OAuth secret |
| `GOOGLE_FIT_REDIRECT_URI` | Google Fit OAuth callback |

**Removed:**
| Variable | Why |
|----------|-----|
| `ALLOWED_EMAIL` | Replaced by invite code system |
| `HEVY_API_KEY` | Moved to per-user `UserProfile.hevy_api_key` |

---

## 11. Open Questions (Deferred)

| Question | Notes |
|----------|-------|
| Should AI conversation history be retained forever or auto-purged after N days? | Recommend 90-day default with user override |
| Should Claude API costs be metered per user? | Consider adding a usage counter per user for observability; rate limits are v2 |
| Should onboarding support editing prior steps before final submission? | Yes — wizard should allow back navigation without losing state |
| Consent re-prompting: what triggers a new consent version? | Any material change to the Privacy Policy; increment `consent_version` string in code |
| Should the admin be able to generate invite codes with multi-use (e.g., 5 uses per code)? | Add `max_uses` field to `InviteCode` as optional |
| Privacy Policy and Terms of Service content | Must be drafted separately; legal language is out of scope for this PRD |

---

## 12. Acceptance Criteria

A feature is complete when:

1. A new user can sign up using an invite code (Google OAuth path).
2. A new user can sign up using a magic link email (invite code required).
3. The 5-step onboarding wizard completes and sets `onboarding_complete = true`.
4. The new user can generate a training plan and meal plan tailored to their prefs.
5. The new user's data is completely invisible to Sandeep's account and vice versa.
6. The new user can connect their own Strava account (OAuth token stored with their `user_id`).
7. The new user's MCP API key works in Claude desktop, scoped to only their data.
8. The weekly summary email goes to each user separately, with correct data.
9. Sandeep's existing data (weight logs, workouts, meal plans) is intact after migration.
10. Admin panel shows all users, allows generating invite codes, and shows audit log.
11. A user can download all their data as a ZIP.
12. A user can delete their account; all their data is purged after 30 days.
13. All queries in all routers are filtered by `user_id`; no cross-user data leakage (verified by manual testing with 2 accounts).
