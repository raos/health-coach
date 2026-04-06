# Health Coach App — CLAUDE.md

Multi-tenant personal health coaching web app. Each user gets their own AI training coach, nutritionist, and health advisor (Claude AI), with per-user Strava, Garmin, Hevy, and Telegram integrations. Includes a per-user remote MCP server so Claude on mobile/desktop can log meals and query health data, and a Telegram bot that reuses the same 14 MCP tools. Invite-only sign-up; admin panel for user management.

---

## Running the App

```bash
# Start both servers (from repo root)
./start.sh

# Or manually:
cd backend && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
cd frontend && npm run dev
```

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs

The `.env` file lives at the **repo root** (`/health/.env`), not inside `backend/`. `config.py` loads it via `env_file="../.env"`.

### Database migrations

```bash
cd backend && alembic upgrade head
```

Alembic manages all schema changes. `init_db()` calls `Base.metadata.create_all()` as a safety net for fresh installs, but migrations are authoritative for existing databases.

---

## Architecture

```
backend/          FastAPI + SQLAlchemy (PostgreSQL)
  main.py         App init, CORS, router registration, MCP routes, /api/settings/status, APScheduler startup
  config.py       Pydantic Settings — all secrets loaded from root .env
  dependencies.py verify_token(), get_user_id(), get_current_user(), require_admin() FastAPI dependencies
  mcp_server.py   Remote MCP server (14 tools, SSE transport, per-user API key auth)
  alembic/        Database migrations
    versions/     Migration scripts (Alembic autogenerate)
  database/
    engine.py     PostgreSQL engine (pool_pre_ping, pool_size=5), init_db()
    models.py     20 ORM models (5 auth/user management + 15 health data)
  routers/        HTTP layer only — no business logic
    auth.py       Google OAuth flow + magic link auth + invite code management + logout
    admin.py      User list, toggle is_active/is_admin, audit log, usage stats (admin only)
    account.py    Data export (ZIP), account deletion, conversation wipe
    nutrition.py  Meal plans, food log (GET+POST), nutritionist chat
    coach.py      Training plans, coach chat, data sync
    checkin.py    Weekly check-in POST/GET endpoints
    email.py      Manual trigger for weekly summary email (POST /api/email/weekly-summary)
    supplements.py Supplement CRUD + daily logging
    body_composition.py Body fat / lean mass logging
    telegram.py   Telegram bot webhook (public) + status/disconnect (protected)
  services/       All business logic and external API calls
    claude_service.py        All Claude AI calls — plans, chat, parse_meal_description()
    weekly_summary_service.py  send_weekly_summary_all_users() — called by scheduler + endpoint
    telegram_service.py      Telegram bot logic + Claude tool-use loop (reuses MCP tools)
  prompts/        Claude system prompts as Python string constants
    nutrition_system.py  Contains NUTRITION_SYSTEM_PROMPT + NUTRITIONIST_CHAT_SYSTEM
  scripts/
    migrate_sqlite_to_postgres.py  One-time SQLite → PostgreSQL data migration
    seed_admin_user.py             Bootstrap admin user row for fresh installs
    setup_telegram_webhook.py      One-time Telegram webhook registration
    garmin_import_json.py          Batch Garmin JSON import from saved files

frontend/         React 19 + TypeScript + Vite + Tailwind CSS v4
  src/api/        One Axios client per domain; client.ts injects JWT on every request
  src/pages/      Login, Onboarding, Dashboard, Coach, Nutrition, HealthAdvisor, Settings, Admin, WeeklyCheckin
    Login.tsx     Google OAuth + magic link tabs; invite code input
    Onboarding.tsx 5-step wizard for new users (personal → goals → training → nutrition → integrations)
    Admin.tsx     User management + invite code generator (is_admin only)
    Nutrition.tsx 4 tabs: Meal Plan | Food Log | Shopping List | Nutritionist
    WeeklyCheckin.tsx 5-point self-assessment ratings (training, energy, sleep, diet, stress) + history
    Settings.tsx  Profile, integrations (Strava, Hevy, Telegram, MCP), data export, account deletion
  src/components/
    auth/         ProtectedRoute.tsx — redirects to /onboarding if onboarding_complete=false
    layout/       Sidebar with Google profile photo + dynamic goals + logout + Admin link (admin only)
    shared/       MarkdownRenderer uses react-markdown + remark-gfm
  src/types/      All TypeScript interfaces in index.ts
```

---

## Authentication (Google OAuth + Magic Link + JWT)

### Auth flows

**Google OAuth** (primary):
1. User visits any route → `ProtectedRoute` checks `localStorage("auth_token")` → redirects to `/login` if missing/expired
2. User enters optional invite code, clicks "Continue with Google" → frontend calls `GET /api/auth/google/url?invite=<code>` → redirects to Google (code encoded in `state`)
3. Google redirects to `GET /api/auth/google/callback` (public) → validates invite code for new users → upserts User + UserProfile → issues JWT → 302 redirect to `FRONTEND_URL/auth/callback?token=<jwt>`
4. `AuthCallback.tsx` stores the token in `localStorage` and navigates to `/`

**Magic link email** (fallback):
1. User enters email + invite code → `POST /api/auth/magic-link/send` → email sent via Resend (15-minute link)
2. User clicks link → `GET /api/auth/magic-link/verify?token=<token>` → marks token used, upserts User + UserProfile, issues JWT → redirect to `FRONTEND_URL/auth/callback?token=<jwt>`

**Logout / session revocation**:
- `POST /api/auth/logout` sets `User.last_logout_at = utcnow()`
- `get_current_user()` compares JWT `iat` against `last_logout_at` — tokens issued before logout are rejected with 401

### JWT details
- Signed with `JWT_SECRET_KEY` (HS256), expires after `JWT_EXPIRE_DAYS` days (default: 30)
- Payload: `user_id` (UUID str), `sub` (same UUID), `email`, `name`, `picture`, `is_admin`, `onboarding_complete`, `exp`, `iat`
- `verify_token()` validates; `get_user_id()` extracts UUID; `get_current_user()` fetches the full User ORM row

### FastAPI dependency chain
```
verify_token()       → validates JWT, returns payload dict
get_user_id()        → Depends(verify_token), returns uuid.UUID
get_current_user()   → Depends(verify_token) + DB, returns User ORM row (checks is_active, session revocation)
require_admin()      → Depends(get_current_user), raises 403 if not is_admin
```

### Invite codes
- New users (non-admin) must supply a valid invite code at sign-up
- Admin creates codes: `POST /api/auth/invite-codes` (or via `/admin` UI)
- Codes support `max_uses`, `expires_days`
- First login with `ADMIN_EMAIL` env var needs no invite code (bootstrap)
- `GET /api/auth/validate-invite?code=<code>` is public — used by login page to check before submit

### Onboarding
New non-admin users have `UserProfile.onboarding_complete = False`. `ProtectedRoute` reads `onboarding_complete` from the JWT and redirects to `/onboarding` until the 5-step wizard is completed.

### Route protection in main.py
```python
# Public — no JWT
app.include_router(auth.router)           # /api/auth/* (OAuth, magic link, invite validation)
app.include_router(telegram.router)       # /api/telegram/webhook (Telegram webhook, secret-validated)
app.get("/api/strava/auth/callback")      # called by Strava's servers; user_id from state param
app.add_route("/mcp/sse", sse_endpoint)   # per-user API key auth, not JWT
app.add_route("/mcp/messages", messages_endpoint, methods=["POST"])
app.add_api_route("/api/garmin/push-data", ...)  # API key auth

# Protected — all require valid JWT
_auth = [Depends(verify_token)]
app.include_router(admin.router, dependencies=_auth)  # admin routes further require require_admin()
app.include_router(account.router, dependencies=_auth)
# ... all other routers
```

### Critical auth gotchas
- **React StrictMode fires effects twice** — `AuthCallback.tsx` uses a `handled = useRef(false)` guard. Never remove it.
- **Always use the Axios `client`** — never raw `fetch()`. Raw `fetch()` does not include the JWT header.
- **JWT token in redirect URL must be URL-encoded** — backend uses `urllib.parse.quote(token, safe='')`.
- **Use 302, not 307 for OAuth redirects**.
- **`verify-mfa` must return HTTP 400, not 401** — 401 triggers the Axios interceptor which redirects to `/login`, breaking the MFA flow.

---

## Database

PostgreSQL. **Never delete the production database** — it contains user data.

Schema changes go through Alembic:
```bash
# After editing models.py:
cd backend && alembic revision --autogenerate -m "description"
alembic upgrade head
```

`Base.metadata.create_all()` in `init_db()` is a safety net for fresh installs only.

### 20 ORM models

**Auth / user management:**

| Table | Model | Notes |
|-------|-------|-------|
| `users` | `User` | UUID PK; `auth_provider`: google/magic_link; `is_admin`, `is_active`, `last_logout_at` |
| `invite_codes` | `InviteCode` | `code` unique; FK `created_by`/`used_by` → users; `max_uses`, `use_count`, `expires_at` |
| `magic_link_tokens` | `MagicLinkToken` | 15-min single-use; `used` bool |
| `user_consents` | `UserConsent` | Privacy Policy consent record per user |
| `audit_logs` | `AuditLog` | Actions: login, logout, account_created, data_export, account_delete_requested, admin_user_update, clear_conversations |

**Health data (all have `user_id` FK → users.id):**

| Table | Model | Notes |
|-------|-------|-------|
| `user_profile` | `UserProfile` | One row per user; `mcp_api_key` (unique, per-user); `hevy_api_key`; `onboarding_complete`; training/nutrition prefs |
| `weight_logs` | `WeightLog` | Unique constraint: (user_id, date) |
| `body_composition_logs` | `BodyCompositionLog` | BF%, lean mass, fat mass |
| `vo2max_logs` | `Vo2MaxLog` | VO2 max measurements |
| `strava_activities` | `StravaActivity` | Composite PK: (id BigInt, user_id UUID) |
| `hevy_workouts` | `HevyWorkout` | Composite PK: (id String, user_id UUID) |
| `hevy_exercise_sets` | `HevyExerciseSet` | FK to (workout_id, user_id) composite |
| `training_plans` | `TrainingPlan` | Claude-generated weekly plans |
| `meal_plans` | `MealPlan` | Claude-generated weekly meal plans |
| `nutrition_logs` | `NutritionLog` | Logged meals (source: "web", "mcp", or "telegram") |
| `health_insights` | `HealthInsight` | Claude-generated health reports |
| `coach_conversations` | `CoachConversation` | Chat history — session "default" (coach) or "nutrition-default" (nutritionist) |
| `oauth_tokens` | `OAuthToken` | Unique constraint: (user_id, service) |
| `daily_health_cache` | `DailyHealthCache` | Unique: (user_id, date, source); aliased as `GarminDailyCache` for backwards compat |
| `supplements` | `Supplement` | User-defined supplement list |
| `supplement_logs` | `SupplementLog` | Daily intake tracking |
| `weekly_checkins` | `WeeklyCheckin` | Weekly self-assessment ratings + notes |

### DailyHealthCache (replaces GarminDailyCache)
`GarminDailyCache = DailyHealthCache` is a backwards-compatible alias at the bottom of `models.py`. New code should use `DailyHealthCache`. The table has a `source` column (`garmin`/`google_fit`/`apple_health`/`manual`) and `sleep_score`, `deep_min`, `rem_min`, `light_min` columns.

### UserProfile key fields
```python
mcp_api_key = Column(String(100), unique=True)   # per-user MCP auth key (auto-generated on account creation)
hevy_api_key = Column(String(100))               # per-user Hevy REST API key
training_days_strength/cardio/rest/mobility      # per-user training schedule
dietary_preference                               # omnivore/vegetarian/vegan/pescatarian/other
preferred_cuisines / preferred_exercises / exercises_to_avoid  # JSON arrays
onboarding_complete = Column(Boolean, default=False)
invite_code_used = Column(String(50))
weekly_email_enabled = Column(Boolean, default=True)
bf_goal_pct = Column(Float)                      # body fat % goal (shown in sidebar)
vo2max_goal = Column(Float)                      # VO2 max goal (shown in sidebar)
goal_date = Column(Date)                         # target date for goals (shown in sidebar)
# Telegram fields (added via Alembic migration 4a3252a537f4)
telegram_chat_id = Column(BigInteger, unique=True, index=True)
telegram_username = Column(String(100))
telegram_connected_at = Column(DateTime)
```

---

## Claude AI Integration

**Model**: `claude-sonnet-4-6` (hardcoded in `claude_service.py`). `max_tokens=8192` is the model maximum — do not reduce it.

### Token limit strategy — critical
Large JSON responses (training plans, meal plans) are split into **two sequential API calls** to avoid truncation:
- Training plan: first half of week → second half + metadata
- Meal plan: Mon–Thu → Fri–Sun + shopping list + weekly notes

Both calls share the same `system` prompt. Results are merged in `generate_training_plan()` / `generate_meal_plan()`. The helper `_call_claude_json()` strips markdown fences and raises `ValueError` on parse failure — routers catch this and return HTTP 500 with a user-readable message.

### System prompts (`backend/prompts/`)
All prompts are dynamically built from `UserProfile` fields — no more hardcoded names or constraints:

| File | Prompt constant | Key behaviour |
|------|----------------|----------------|
| `coach_system.py` | `COACH_SYSTEM_PROMPT`, `COACH_CHAT_SYSTEM` | Equipment from `profile.training_device`; days from `training_days_*`; if device is "tonal" → Tonal-only constraint. Upper A = horizontal push + vertical pull. Upper B = incline/overhead + horizontal pull. Lower A = quad-dominant. Lower B = hip-dominant. Cardio days include 10–15 min core circuit. |
| `nutrition_system.py` | `NUTRITION_SYSTEM_PROMPT`, `NUTRITIONIST_CHAT_SYSTEM` | Dietary type from `profile.dietary_preference`; cuisine prefs from `profile.preferred_cuisines`; Bobby Parish philosophy; cook-once rule. |
| `health_advisor_system.py` | `HEALTH_ADVISOR_SYSTEM_PROMPT` | Peter Attia (Outlive) + Andrew Huberman framework. VO2 max as longevity predictor. |

### Claude functions in claude_service.py

| Function | Description |
|----------|-------------|
| `generate_training_plan(db, user_id)` | Two-call split, context hash caching, reads UserProfile |
| `generate_meal_plan(db, user_id)` | Two-call split (Mon–Thu / Fri–Sun), reads UserProfile for dietary prefs |
| `chat_with_coach(db, user_id, ...)` | Tool-use loop (up to 5 rounds), Hevy + Strava tools |
| `chat_with_nutritionist(db, user_id, ...)` | Single call; injects food log + meal plan as context |
| `parse_meal_description()` | Single call, returns JSON `{name, meal_type, kcal, protein_g, carbs_g, fat_g}` |
| `generate_health_insights(db, user_id)` | Single large call with full Garmin data |

### Context hash caching (training plans)
`generate_training_plan()` builds a hash from current stats + recent training + config string. If you add new `UserProfile` fields to plan generation, include them in the hash string or stale cached plans will be returned.

---

## Nutrition Page (4 tabs)

`frontend/src/pages/Nutrition.tsx` is structured as 4 tabs:

| Tab | Content |
|-----|---------|
| **Meal Plan** | Calorie input + Preferences + Generate/Email buttons; day tabs (Mon–Sun, defaults to today); meal cards with macro pills, macro bar, ingredient scaler |
| **Food Log** | Date navigator (← → today); quick-log textarea (Claude estimates macros via `POST /api/nutrition/log`); logged meals with daily totals |
| **Shopping List** | Checkboxes by category; email checked items |
| **Nutritionist** | Multi-turn chat; `NUTRITIONIST_CHAT_SYSTEM` prompt has today's food log + meal plan injected as context |

### Food Log date computation
Uses the currently selected `foodLogDate` state (ISO string, defaults to today). The Meal Plan tab day tabs use the **current calendar week's Monday** — never from `parsedPlan.week_start`.

### Nutritionist chat storage
Reuses `CoachConversation` table with `session_id = "nutrition-default"` (coach uses `"default"`).

---

## MCP Remote Server

`backend/mcp_server.py` exposes 14 tools over HTTP+SSE. Auth uses per-user `mcp_api_key` stored in `UserProfile` — **not a global env var**.

### Auth
`GET /mcp/sse?key=<user_mcp_api_key>` — backend looks up `UserProfile` by `mcp_api_key`, sets `_current_user_id` ContextVar for the session duration. 401 if key missing or not found.

### User context in MCP tools
All MCP tool handlers call `_get_user_id()` to retrieve the UUID from the `_current_user_id` ContextVar, then filter all DB queries by that UUID.

### Claude Desktop setup
Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "health-coach": {
      "command": "npx",
      "args": ["-y", "mcp-remote@latest", "https://<host>/mcp/sse?key=<USER_MCP_API_KEY>"]
    }
  }
}
```
The full URL with the per-user key is shown in **Settings → Mobile Access (MCP)**.

### 14 MCP tools

| Tool | What it does |
|------|-------------|
| `log_meal` | INSERT into NutritionLog for current user |
| `get_nutrition_log` | NutritionLog rows for a date + daily totals |
| `get_meal_plan_for_day` | Active MealPlan meals for a given day name |
| `get_todays_workout` | Active TrainingPlan exercises for today's weekday |
| `get_recent_workouts` | HevyWorkout + HevyExerciseSet summary for last N days |
| `get_exercise_stats` | Per-week max weight + estimated 1RM for a named exercise |
| `get_health_metrics` | DailyHealthCache: steps, sleep, resting HR for last N days |
| `get_health_summary` | Latest weight + body comp + VO2 max + last 7 days Garmin |
| `get_health_recommendations` | Latest HealthInsight content |
| `log_weight` | Upsert into WeightLog |
| `sync_data` | Calls hevy_service.sync_workouts() + strava_service.sync_activities() |
| `generate_meal_plan` | Calls claude_service.generate_meal_plan() via asyncio.to_thread() |
| `generate_training_plan` | Calls claude_service.generate_training_plan() via asyncio.to_thread() |
| `submit_weekly_checkin` | Upsert into WeeklyCheckin table (ratings + notes) |

### Starlette compatibility
Both endpoints return `_AlreadySentResponse` (a no-op `Response` subclass) because the MCP SDK writes the HTTP response directly via the ASGI `send` callable.

---

## External Integrations

### Strava
- OAuth2 flow: `/api/strava/auth/url` (protected) → user redirects to Strava → Strava redirects to `/api/strava/auth/callback` (public)
- **The Strava callback encodes `user_id` in the `state` parameter** — the public callback reads `state` as a UUID to associate the token with the correct user. Never move this callback into a JWT-protected router.
- Tokens stored in `OAuthToken` table (`service="strava"`), unique per user, auto-refreshed
- Syncs to `StravaActivity` table (composite PK: activity_id + user_id)

### Garmin
Garmin **direct login has been removed** (`garmin_service.py` is now a stub). Data is imported via two endpoints — no credentials needed:

- **`POST /api/garmin/paste-data`** — accepts `{"json_data": "<raw usersummary JSON>"}` pasted from Garmin Connect DevTools. Settings UI has a paste panel.
- **`POST /api/garmin/push-data`** — API key authenticated endpoint for scripted imports (`scripts/garmin_push.py`).

`scripts/garmin_import_json.py` handles batch import from saved `.json` files.

**Sleep extraction:** Uses `bodyBatteryActivityEventList` SLEEP event (started ≥18:00 prior evening) for full overnight duration. Falls back to `sleepingSeconds`.

**Garmin account-level rate limiting (429):** Account-level, not IP-level. Do not suggest IP changes. Paste-data import is the workaround.

### Hevy
Per-user API key stored in `UserProfile.hevy_api_key` (set during onboarding or Settings). Uses `HevyAPIClient` with httpx calls to `api.hevyapp.com/v1`.

### Telegram
Full Telegram bot integration. Users link their account using their `mcp_api_key`.

**Auth flow:**
- `/connect <mcp_api_key>` in Telegram → `telegram_service._find_by_mcp_key()` looks up the profile → saves `telegram_chat_id`, `telegram_username`, `telegram_connected_at` to `UserProfile`
- Deep-link from Settings: `https://t.me/{TELEGRAM_BOT_USERNAME}?start={mcp_api_key}` → bot receives `/start <key>` and auto-connects

**Message handling (`telegram_service.py`):**
- `handle_update()` — dispatches commands vs. natural text
- Commands: `/start`, `/connect`, `/disconnect`, `/help`, `/status`
- Natural text → `run_claude_tool_loop()` — sets `_current_user_id` ContextVar, calls `list_tools()` + `call_tool()` from `mcp_server.py` (same 14 tools), max 10 iterations
- Responses split at 4096-char Telegram limit with paragraph-aware chunking

**Webhook:**
- `POST /api/telegram/webhook` is public; validated by `X-Telegram-Bot-Api-Secret-Token` header against `TELEGRAM_WEBHOOK_SECRET`
- Register once: `cd backend && python scripts/setup_telegram_webhook.py`

**Environment variables:**
```ini
TELEGRAM_BOT_TOKEN=<token from @BotFather>
TELEGRAM_BOT_USERNAME=your_bot_name   # without @
TELEGRAM_WEBHOOK_SECRET=<random string>
```

**Frontend (Settings → Integrations):**
- Shows connection status (connected @username or not connected)
- Deep-link button opens bot directly with auto-connect
- Disconnect button calls `DELETE /api/telegram/disconnect`

---

## Frontend Patterns

### Always use the Axios client — never raw fetch()
Every API call must use `import client from "../api/client"`. Raw `fetch()` does not include the JWT header and will silently return 401.

### Markdown rendering
All Claude-generated content is rendered via `MarkdownRenderer.tsx` (`react-markdown` + `remark-gfm`). `remark-gfm` is **required** for tables.

### ProtectedRoute behaviour
- No `auth_token` in localStorage → redirect to `/login`
- Token present but `onboarding_complete=false` in JWT → redirect to `/onboarding`
- Admin routes (`/admin`) checked by the Admin page itself via `is_admin` from JWT

### Adding a new page
1. Create `frontend/src/pages/NewPage.tsx`
2. Add route inside the `ProtectedRoute` block in `frontend/src/App.tsx`
3. Add nav item to `frontend/src/components/layout/Sidebar.tsx`

---

## Environment Variables

All in `.env` at the **repo root** (not `backend/.env`):

```ini
# Google OAuth + JWT (required for login)
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback
JWT_SECRET_KEY=<random 32-byte hex>
JWT_EXPIRE_DAYS=30

# Multi-tenant admin bootstrap (required)
ADMIN_EMAIL=your.email@gmail.com   # First login gets is_admin=True; no invite code needed
# Legacy single-user gate — ignored when ADMIN_EMAIL is set
ALLOWED_EMAIL=

ANTHROPIC_API_KEY=sk-ant-...           # Required for all AI features

STRAVA_CLIENT_ID=                      # Required for Strava sync
STRAVA_CLIENT_SECRET=
STRAVA_REDIRECT_URI=http://localhost:8000/api/strava/auth/callback

RESEND_API_KEY=                        # Required for magic link auth + email delivery
RESEND_FROM_EMAIL=Health Coach <onboarding@resend.dev>

# Telegram bot (optional)
TELEGRAM_BOT_TOKEN=                    # Token from @BotFather
TELEGRAM_BOT_USERNAME=                 # Bot username without @
TELEGRAM_WEBHOOK_SECRET=               # Random string to validate webhook requests

# Database — PostgreSQL required
DATABASE_URL=postgresql://localhost/health_coach_dev

BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ORIGINS=http://localhost:5173
FRONTEND_URL=http://localhost:5173

# MCP push-data backwards-compat only — per-user keys in UserProfile are primary
MCP_API_KEY=
```

**Removed env vars (no longer in use):**
- `GARMIN_EMAIL`, `GARMIN_PASSWORD`, `GARMIN_SESSION_DIR` — Garmin direct login was removed; use paste-data or push-data
- `HEVY_API_KEY` — per-user; stored in `UserProfile.hevy_api_key`, set during onboarding or Settings
- `SMTP_HOST/PORT/USER/PASSWORD`, `EMAIL_FROM`, `EMAIL_RECIPIENTS_*` — SMTP was replaced by Resend

`GET /api/settings/status` returns integration status + the caller's `mcp_api_key` from their UserProfile. Auto-generates a key if none exists. Also returns `telegram_connected` (bool) and `telegram_bot_username` (for building the deep-link).

---

## Weekly Summary Email

`backend/services/weekly_summary_service.py` → `send_weekly_summary_all_users()`:
- Iterates all active users with `weekly_email_enabled=True`
- For each user: gathers last 7 days of WeightLog, HevyWorkout, NutritionLog, DailyHealthCache
- Computes weight avg + trend, workout list + duration, days logged + avg kcal/protein vs target, avg steps/sleep/resting HR
- Sends HTML email via Resend **only to the user** — no CC
- If profile is not found for a user, logs an error and skips that user (no fallback to admin email)

**Scheduler**: `_start_scheduler()` in `main.py` fires every Sunday 19:30 ET.

**Manual trigger**: `POST /api/email/weekly-summary` (JWT required). JWT is in DevTools → Application → Local Storage → `auth_token`.

---

## Admin Panel

`GET /api/admin/users` — list all users with profile summaries  
`PATCH /api/admin/users/{id}` — toggle `is_active` or `is_admin`  
`GET /api/admin/audit-log` — recent audit log entries  
`GET /api/admin/stats` — usage stats (total users, onboarded, plans generated, integrations connected)  

All admin routes use `require_admin()` dependency. The `/admin` page is only shown in the sidebar for users where `is_admin=true` in the JWT.

**Invite code management** (also admin-only, under `auth.router`):  
`POST /api/auth/invite-codes` — create a code  
`GET /api/auth/invite-codes` — list all codes  

---

## Account & Privacy (GDPR)

`GET /api/account/data-export` — ZIP of all user data as JSON files (excludes `hevy_api_key` and `mcp_api_key`)  
`DELETE /api/account` — soft-delete (sets `deleted_at`, `is_active=False`); hard purge is manual after 30 days  
`DELETE /api/account/conversations` — wipe all coach + nutritionist chat history  

---

## Key Constraints — Do Not Violate

1. **Per-user data isolation**: Every DB query on a health data table **must** filter by `user_id`. Never omit it.
2. **MCP API key is per-user**: Looked up from `UserProfile.mcp_api_key`. `_current_user_id` ContextVar carries the user across MCP tool calls.
3. **Tonal-only when device is "tonal"**: Only apply the Tonal equipment constraint when `profile.training_device == "tonal"`. Other users can use any gym.
4. **max_tokens=8192**: This is the model's hard limit. Never lower it.
5. **Two-call pattern**: Do not generate a full 7-day plan or full training week in a single API call — it will truncate.
6. **Cook-once rule**: In meal plans, Tuesday–Sunday lunch must be the previous night's dinner (prefixed with "Leftover: "). Monday lunch is standalone.
7. **Context hash**: If you add new UserProfile fields to plan generation, include them in the hash or stale plans will be returned.
8. **Don't mock the DB**: The database contains real user data. Integration tests and dev work should use the real DB.
9. **Strava callback stays public**: `/api/strava/auth/callback` must never be inside a JWT-protected router. User identity comes from the `state` param (UUID).
10. **Always use Axios client**: Never use raw `fetch()` in React components.
11. **Food Log dates use current week**: The Food Log tab computes dates from the current calendar week's Monday — never from `parsedPlan.week_start`.
12. **Core exercises on cardio days**: Cardio days include a 10–15 min core circuit using only bodyweight, a 10 lb medicine ball, or a 20 lb plate.
13. **Garmin rate limit is account-level**: The 429 from Garmin is account-level. Do not suggest changing IP/hotspot. Use paste-data import.
14. **Alembic for schema changes**: Never use `Base.metadata.create_all()` as the migration path for an existing database. Always create an Alembic migration.
15. **Admin bootstrap**: The `ADMIN_EMAIL` user needs no invite code on first login. All other new users require one.
16. **Telegram webhook is public**: `/api/telegram/webhook` must stay public (no JWT). It is secured by `X-Telegram-Bot-Api-Secret-Token` header validation against `TELEGRAM_WEBHOOK_SECRET`.
17. **Telegram reuses MCP tools**: The Telegram tool-use loop calls `list_tools()` and `call_tool()` from `mcp_server.py` — do not duplicate tool implementations in `telegram_service.py`.
18. **Weekly summary no CC**: `send_weekly_summary_for_user()` sends only to the user's email. No CC. If profile is missing, log and skip — never fall back to admin email.
19. **Sidebar goals are dynamic**: The BF% goal, VO2 max goal, and goal date in the sidebar footer are fetched live from `UserProfile` via `getProfile()` — not hardcoded.

---

## Adding New Features

### New API endpoint
1. Add Pydantic schema to `backend/schemas/<domain>.py`
2. Add route to `backend/routers/<domain>.py` (HTTP logic only); use `get_user_id` dependency to scope queries
3. Add business logic to `backend/services/<domain>_service.py` or `claude_service.py`
4. Add API function to `frontend/src/api/<domain>.ts`
5. Add TypeScript type to `frontend/src/types/index.ts` if needed
6. If the endpoint must be public, register directly on `app` in `main.py` before the `_auth` block

### New Claude feature
1. Add/edit system prompt in `backend/prompts/`
2. Add function to `backend/services/claude_service.py` following the `_call_claude_json()` pattern
3. If response is large, split into two calls and merge results
4. Always validate that `stop_reason != "max_tokens"` — raise `ValueError` if it does
5. Pull user preferences from `UserProfile` rather than hardcoding them

### New MCP tool
1. Add tool definition to `list_tools()` in `mcp_server.py`
2. Add handler `_<tool_name>(args)` using `_get_user_id()` to scope all DB queries
3. Add dispatch case to `call_tool()`
4. If the tool calls Claude API (slow), wrap with `await asyncio.to_thread(...)`
5. The Telegram bot automatically picks up the new tool — no changes needed in `telegram_service.py`

### Schema change
1. Edit `backend/database/models.py`
2. `cd backend && alembic revision --autogenerate -m "description"`
3. Review the generated migration in `alembic/versions/`
4. `alembic upgrade head`
