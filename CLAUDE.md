# Health Coach App — CLAUDE.md

Personal health coaching web app for Sandeep Rao. Combines Claude AI with Strava, Garmin, and Hevy integrations to generate training plans, meal plans, and health insights. Includes a remote MCP server so Claude on mobile/desktop can log meals and query health data.

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

---

## Architecture

```
backend/          FastAPI + SQLAlchemy (SQLite)
  main.py         App init, CORS, router registration, MCP routes, /api/settings/status
  config.py       Pydantic Settings — all secrets loaded from root .env
  dependencies.py verify_token() FastAPI dependency (JWT validation)
  mcp_server.py   Remote MCP server (13 tools, SSE transport, API key auth)
  database/
    engine.py     SQLite engine (WAL mode), init_db(), seed on first run
    models.py     14 ORM models
  routers/        HTTP layer only — no business logic
    auth.py       Google OAuth flow + JWT issuance (public, no auth required)
    nutrition.py  Meal plans, food log (GET+POST), nutritionist chat
    coach.py      Training plans, coach chat, data sync
  services/       All business logic and external API calls
    claude_service.py  All Claude AI calls — plans, chat, parse_meal_description()
  prompts/        Claude system prompts as Python string constants
    nutrition_system.py  Contains NUTRITION_SYSTEM_PROMPT + NUTRITIONIST_CHAT_SYSTEM
  schemas/        Pydantic request/response models

frontend/         React 19 + TypeScript + Vite + Tailwind CSS v4
  src/api/        One Axios client per domain; client.ts injects JWT on every request
  src/pages/      Login, Dashboard, Coach, Nutrition, HealthAdvisor, Settings
    Nutrition.tsx 4 tabs: Meal Plan | Food Log | Shopping List | Nutritionist
  src/components/
    auth/         ProtectedRoute.tsx — redirects to /login if no valid token
    layout/       Sidebar with Google profile photo + logout button
    shared/       MarkdownRenderer uses react-markdown + remark-gfm
  src/types/      All TypeScript interfaces in index.ts
```

---

## Authentication (Google OAuth + JWT)

The app requires sign-in via Google OAuth before accessing any page.

### Flow
1. User visits any route → `ProtectedRoute` checks `localStorage("auth_token")` → redirects to `/login` if missing/expired
2. User clicks "Continue with Google" → frontend calls `GET /api/auth/google/url` → redirects to Google
3. Google redirects to `GET /api/auth/google/callback` (public, no JWT) → backend exchanges code for user info → issues a JWT → 302 redirect to `http://localhost:5173/auth/callback?token=<jwt>`
4. `AuthCallback.tsx` stores the token in `localStorage` and navigates to `/`
5. All subsequent API calls include `Authorization: Bearer <token>` via the Axios interceptor

### JWT details
- Signed with `JWT_SECRET_KEY` (HS256), expires after `JWT_EXPIRE_DAYS` days (default: 30)
- Payload contains: `email`, `name`, `picture`, `sub`, `exp`
- Decoded client-side in `getStoredUser()` (no signature verification needed — trust is on the backend)
- `verify_token()` in `backend/dependencies.py` validates the token on every protected route

### Route protection in main.py
```python
# Public — no JWT
app.include_router(auth.router)
app.get("/api/strava/auth/callback")   # called by Strava's servers, no JWT available
app.add_route("/mcp/sse", sse_endpoint)        # API key auth, not JWT
app.add_route("/mcp/messages", messages_endpoint, methods=["POST"])

# Protected — all require valid JWT
_auth = [Depends(verify_token)]
app.include_router(weight.router, dependencies=_auth)
app.include_router(strava.router, dependencies=_auth)
# ... all other routers
```

### Critical auth gotchas
- **React StrictMode fires effects twice** — `AuthCallback.tsx` uses a `handled = useRef(false)` guard to prevent the second effect invocation from running after the URL has already changed. Never remove this guard.
- **Always use the Axios `client`** for API calls in React components — never raw `fetch()`. Raw `fetch()` does not include the JWT header, causing silent 401 failures (the `.catch(() => {})` pattern swallows the error and leaves state null).
- **JWT token in redirect URL must be URL-encoded** — the backend uses `urllib.parse.quote(token, safe='')` before embedding in the redirect URL.
- **Use 302, not 307 for OAuth redirects** — 307 preserves HTTP method but can behave unexpectedly in some browser/proxy setups. All `RedirectResponse` in `auth.py` use `status_code=302`.

---

## Database

SQLite at `backend/health.db`. **Never delete health.db** — it contains Sandeep's weight logs, DEXA history, and synced activities.

**Seeded on first `init_db()` call** (skipped if records already exist):
- DEXA baseline: 2026-03-13, 181.5 lbs, 28.4% BF, 123.9 lbs lean mass, visceral fat 1.38 lbs
- VO2 max baseline: 2026-03-13, 45.0
- User profile: Sandeep Rao, DOB 1979-11-11, height 68 in, goal 18% BF + VO2 50 by 2026-12-31, 2200 kcal/day

**All 14 models:**

| Table | Model | Notes |
|-------|-------|-------|
| `weight_logs` | `WeightLog` | Daily weight entries |
| `dexa_scans` | `DexaScan` | Body composition scans |
| `vo2max_logs` | `Vo2MaxLog` | VO2 max measurements |
| `strava_activities` | `StravaActivity` | Synced cardio |
| `hevy_workouts` | `HevyWorkout` | Synced strength sessions |
| `hevy_exercise_sets` | `HevyExerciseSet` | Individual sets |
| `training_plans` | `TrainingPlan` | Claude-generated weekly plans |
| `meal_plans` | `MealPlan` | Claude-generated weekly meal plans |
| `nutrition_logs` | `NutritionLog` | Logged meals (source: "web" or "mcp") |
| `health_insights` | `HealthInsight` | Claude-generated health reports |
| `coach_conversations` | `CoachConversation` | Chat history — reused by both coach (session "default") and nutritionist (session "nutrition-default") |
| `oauth_tokens` | `OAuthToken` | Strava OAuth tokens |
| `garmin_daily_cache` | `GarminDailyCache` | Cached Garmin daily summaries |
| `user_profile` | `UserProfile` | Goals, calorie target, preferences |

To add a new table: add model to `database/models.py`, it is created automatically by `Base.metadata.create_all()` on startup.

### NutritionLog model
```python
class NutritionLog(Base):
    __tablename__ = "nutrition_logs"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    date        = Column(Date, nullable=False, index=True)   # not unique — multiple meals per day
    meal_type   = Column(String(20), nullable=False)         # breakfast/lunch/dinner/snack/dessert
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)                # original text the user typed
    kcal        = Column(Integer, nullable=False)
    protein_g   = Column(Float, nullable=False)
    carbs_g     = Column(Float, nullable=False)
    fat_g       = Column(Float, nullable=False)
    source      = Column(String(20), default="mcp")          # "web" or "mcp"
    logged_at   = Column(DateTime, default=datetime.utcnow)
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
All prompts use Python f-string `{placeholder}` injection — edit the prompt files, not the service:

| File | Prompt constant | Key constraints |
|------|----------------|----------------|
| `coach_system.py` | `COACH_SYSTEM_PROMPT`, `COACH_CHAT_SYSTEM` | Tonal-only (cable machine, 0–200 lbs). Upper A = horizontal push + vertical pull. Upper B = incline/overhead + horizontal pull. Lower A = quad-dominant. Lower B = hip-dominant. Never repeat movement patterns between A and B. |
| `nutrition_system.py` | `NUTRITION_SYSTEM_PROMPT`, `NUTRITIONIST_CHAT_SYSTEM` | Vegetarian + eggs. Bobby Parish philosophy. Cook-once rule. `NUTRITIONIST_CHAT_SYSTEM` injects today's food log + active meal plan summary + calorie target on every message. |
| `health_advisor_system.py` | `HEALTH_ADVISOR_SYSTEM_PROMPT` | Peter Attia (Outlive) + Andrew Huberman framework. VO2 max as longevity predictor. |

### Claude functions in claude_service.py

| Function | Description |
|----------|-------------|
| `generate_training_plan()` | Two-call split, context hash caching |
| `generate_meal_plan()` | Two-call split (Mon–Thu / Fri–Sun) |
| `chat_with_coach()` | Tool-use loop (up to 5 rounds), Hevy + Strava tools |
| `chat_with_nutritionist()` | Single call; injects food log + meal plan as context |
| `parse_meal_description()` | Single call, returns JSON `{name, meal_type, kcal, protein_g, carbs_g, fat_g}` |
| `generate_health_insights()` | Single large call with full Garmin data |

### Context hash caching (training plans)
`generate_training_plan()` builds a hash from current stats + recent training + config string (`f"{s}s{c}c{r}r"`). If the hash matches the stored plan, the cached plan is returned. Changing strength/cardio/rest days forces a regeneration because the config string changes.

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
The Food Log tab uses the currently selected `foodLogDate` state (ISO string, defaults to today). The Meal Plan tab day tabs use the **current calendar week's Monday** to compute dates — not the meal plan's `week_start`, which may be from a previous week.

### Nutritionist chat storage
Reuses `CoachConversation` table with `session_id = "nutrition-default"` (coach uses `"default"`).

---

## MCP Remote Server

`backend/mcp_server.py` exposes 13 tools over HTTP+SSE. Mounted in `main.py` before the JWT block (public routes, but API-key authenticated):

```python
app.add_route("/mcp/sse", sse_endpoint)
app.add_route("/mcp/messages", messages_endpoint, methods=["POST"])
```

### Auth
`GET /mcp/sse?key=<MCP_API_KEY>` — key validated before stream is opened; 401 if wrong or missing.

### Claude Desktop setup (bypasses OAuth requirement)
Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "health-coach": {
      "command": "npx",
      "args": ["-y", "mcp-remote@latest", "https://<host>/mcp/sse?key=<MCP_API_KEY>"]
    }
  }
}
```
Claude Desktop's "Add Custom Integration" UI requires OAuth 2.0 (MCP 2025-03-26 spec). Use `mcp-remote` via config file instead to use the API key SSE approach.

### 13 MCP tools

| Tool | What it does |
|------|-------------|
| `log_meal` | INSERT into NutritionLog; Claude estimates macros before calling |
| `get_nutrition_log` | NutritionLog rows for a date + daily totals |
| `get_meal_plan_for_day` | Active MealPlan meals for a given day name |
| `get_todays_workout` | Active TrainingPlan exercises for today's weekday |
| `get_recent_workouts` | HevyWorkout + HevyExerciseSet summary for last N days |
| `get_exercise_stats` | Per-week max weight + estimated 1RM for a named exercise |
| `get_health_metrics` | GarminDailyCache: steps, sleep, resting HR for last N days |
| `get_health_summary` | Latest weight + DEXA + VO2 max + last 7 days Garmin |
| `get_health_recommendations` | Latest HealthInsight content |
| `log_weight` | Upsert into WeightLog |
| `sync_data` | Calls hevy_service.sync_workouts() + strava_service.sync_activities() |
| `generate_meal_plan` | Calls claude_service.generate_meal_plan() via asyncio.to_thread() |
| `generate_training_plan` | Calls claude_service.generate_training_plan() via asyncio.to_thread() |

### Starlette compatibility
Both endpoints return `_AlreadySentResponse` (a no-op `Response` subclass) because the MCP SDK writes the HTTP response directly via the ASGI `send` callable. Without this, Starlette tries to call `await None(scope, receive, send)` and raises a `TypeError`.

---

## External Integrations

### Strava
- OAuth2 flow: `/api/strava/auth/url` (protected) → user redirects to Strava → Strava redirects to `/api/strava/auth/callback` (public)
- **The Strava callback MUST be public** — it is called by Strava's servers after OAuth, no JWT is available. It is registered directly on `app` in `main.py` before the protected routers, NOT inside `strava.router`. If you ever move it back into `strava.router`, it will be JWT-protected and Strava OAuth will break.
- Tokens stored in `OAuthToken` table (`service="strava"`), auto-refreshed
- Syncs to `StravaActivity` table; accessible from dashboard activity feed

### Garmin (MFA-enabled)
Garmin account has MFA and it **cannot be disabled**. Login uses a threading approach:
1. `POST /api/garmin/login` → spawns login thread, returns `{"status": "mfa_required"}` or `{"status": "ok"}`
2. Frontend shows OTP input; user submits `POST /api/garmin/verify-mfa` with `{"otp": "123456"}`
3. Login thread receives OTP via threading event and completes authentication
4. Session tokens persisted to directory set by `GARMIN_SESSION_DIR` env var (garth format) and reused on restart

If saved tokens exist and are valid, `login(tokenstore=)` restores the session silently — no MFA needed.

#### Garmin token persistence — critical for Railway
**Always set `GARMIN_SESSION_DIR=/data/garmin_session` in Railway environment variables.** Without this, tokens are stored in the ephemeral container filesystem and wiped on every redeploy. The `/data` volume is Railway's persistent storage.

#### How `_get_client()` works
`client.login(tokenstore=token_dir)` does three things: loads token files from disk, refreshes the OAuth2 token if expired, and sets `client.display_name` (required for URL construction — every garminconnect API URL includes `/displayName/`). **Never replace this with `garth.load()` directly** — that skips the display_name setup and all API calls will return 401.

#### `verify-mfa` must return HTTP 400, not 401
If MFA verification fails, return `400 Bad Request`. A 401 triggers the Axios interceptor which redirects to `/login`, breaking the MFA flow.

#### Token import endpoint
`POST /api/garmin/import-tokens` accepts `{"oauth1": {...}, "oauth2": {...}}` (raw garth token JSON) and writes them to `GARMIN_SESSION_DIR`. Useful for bootstrapping Railway when the IP is rate-limited:
```bash
curl -X POST https://<railway-host>/api/garmin/import-tokens \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d "{\"oauth1\": $(cat backend/garmin_session/oauth1_token.json), \"oauth2\": $(cat backend/garmin_session/oauth2_token.json)}"
```

### Hevy
Uses direct REST API calls to `api.hevyapp.com/v1` via `backend/services/hevy_api_client.py`:
- `HevyAPIClient` makes httpx calls with `api-key` header
- Methods: `get_workouts()`, `get_exercises()`, `get_exercise_progress()`, `get_routines()`
- Config: `HEVY_API_KEY` in `.env`
- The old `hevy_mcp_client.py` (Node.js subprocess) was replaced because Node.js is not available on Railway

---

## Frontend Patterns

### Always use the Axios client — never raw fetch()
Every API call in every React component must use `import client from "../api/client"` — not the native `fetch()` API. The Axios client (`src/api/client.ts`) attaches `Authorization: Bearer <token>` to every request and redirects to `/login` on 401. Raw `fetch()` calls will silently return 401 and leave component state null.

### Markdown rendering
All Claude-generated content (training plans, health insights, chat responses) is rendered via `MarkdownRenderer.tsx` which uses `react-markdown` + `remark-gfm`. The `remark-gfm` plugin is **required** for tables — without it, pipe characters render as raw text.

### API clients
Each domain has its own file in `src/api/`. The base client (`client.ts`) points to `http://localhost:8000`. When adding a new endpoint, add it to the corresponding API file, not inline in the component.

### Page-level state
Pages manage their own loading/error/data state with `useState` + `useEffect`. There is no global fetch cache. Zustand (`appStore.ts`) is available for cross-page state if needed.

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
ALLOWED_EMAIL=your.email@gmail.com     # leave empty to allow any Google account

ANTHROPIC_API_KEY=sk-ant-...           # Required for all AI features
STRAVA_CLIENT_ID=                      # Required for Strava sync
STRAVA_CLIENT_SECRET=
STRAVA_REDIRECT_URI=http://localhost:8000/api/strava/auth/callback
GARMIN_EMAIL=                          # Required for sleep/HRV/body battery data
GARMIN_PASSWORD=
GARMIN_SESSION_DIR=./garmin_session    # Railway: /data/garmin_session
HEVY_API_KEY=                          # Required for strength training data in Coach chat
MCP_API_KEY=                           # Required for Claude mobile/desktop MCP integration
RESEND_API_KEY=                        # Required for PDF email delivery
DATABASE_URL=sqlite:///./health.db
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ORIGINS=http://localhost:5173
FRONTEND_URL=http://localhost:5173
```

`GET /api/settings/status` returns which integrations are configured + the `mcp_api_key` (shown in Settings page under Mobile Access).

---

## Key Constraints — Do Not Violate

1. **Tonal only**: Every exercise in a generated training plan must be performable on the Tonal smart gym (cable/pulley system). No free barbells, no dumbbells, no machines not available on Tonal.
2. **Vegetarian + eggs**: Meal plans must never include meat or seafood.
3. **max_tokens=8192**: This is the model's hard limit. Never lower it. If responses still truncate, split the prompt further.
4. **Two-call pattern**: Do not try to generate a full 7-day plan or full training week in a single API call — it will truncate.
5. **Cook-once rule**: In meal plans, Tuesday–Sunday lunch must be the previous night's dinner (prefixed with "Leftover: "). Monday lunch is standalone.
6. **Context hash**: If you add new fields to the training plan generation (e.g., new user prefs), include them in the hash string or cached stale plans will be returned.
7. **Don't mock the DB**: The SQLite database contains real user data. Integration tests and dev work should use the real DB.
8. **Strava callback stays public**: `/api/strava/auth/callback` must never be inside a JWT-protected router. Keep it registered directly on `app` in `main.py`.
9. **Always use Axios client**: Never use raw `fetch()` in React components. The Axios client is the only way to ensure the JWT is sent.
10. **Food Log dates use current week**: The Food Log tab computes dates from the current calendar week's Monday — never from `parsedPlan.week_start`, which may be from a previous week.

---

## Adding New Features

### API Integration
When working with external APIs (Garmin, Hevy, Strava), always inspect the actual API response structure before writing parsing code. Use a test call first, print the response, then build the handler.

### New API endpoint
1. Add Pydantic schema to `backend/schemas/<domain>.py`
2. Add route to `backend/routers/<domain>.py` (HTTP logic only)
3. Add business logic to `backend/services/<domain>_service.py` or `claude_service.py`
4. Add API function to `frontend/src/api/<domain>.ts`
5. Add TypeScript type to `frontend/src/types/index.ts` if needed
6. If the endpoint must be public (e.g., called by a third-party OAuth redirect), register it directly on `app` in `main.py` before the `_auth` block — do NOT add it to a router that uses `dependencies=_auth`

### New Claude feature
1. Add/edit system prompt in `backend/prompts/`
2. Add a function to `backend/services/claude_service.py` following the `_call_claude_json()` pattern
3. If response is large, split into two calls and merge results
4. Always validate that `stop_reason != "max_tokens"` — raise `ValueError` if it does

### New MCP tool
1. Add tool definition to `list_tools()` in `mcp_server.py`
2. Add handler function `_<tool_name>(args)` that uses `SessionLocal()` / `try: ... / finally: db.close()`
3. Add dispatch case to `call_tool()` in `mcp_server.py`
4. If the tool calls Claude API (slow), wrap with `await asyncio.to_thread(...)` to avoid blocking the event loop
