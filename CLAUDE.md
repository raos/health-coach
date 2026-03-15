# Health Coach App — CLAUDE.md

Personal health coaching web app for Sandeep Rao. Combines Claude AI with Strava, Garmin, and Hevy integrations to generate training plans, meal plans, and health insights.

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
  main.py         App init, CORS, router registration, /api/settings/status
  config.py       Pydantic Settings — all secrets loaded from root .env
  dependencies.py verify_token() FastAPI dependency (JWT validation)
  database/
    engine.py     SQLite engine (WAL mode), init_db(), seed on first run
    models.py     11 ORM models
  routers/        HTTP layer only — no business logic
    auth.py       Google OAuth flow + JWT issuance (public, no auth required)
  services/       All business logic and external API calls
  prompts/        Claude system prompts as Python string constants
  schemas/        Pydantic request/response models

frontend/         React 19 + TypeScript + Vite + Tailwind CSS v4
  src/api/        One Axios client per domain; client.ts injects JWT on every request
  src/pages/      6 route pages (Login, Dashboard, Coach, Nutrition, HealthAdvisor, Settings)
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
app.get("/api/strava/auth/callback")   # Strava callback — called by Strava, no JWT available

# Protected — all require valid JWT
_auth = [Depends(verify_token)]
app.include_router(weight.router, dependencies=_auth)
app.include_router(strava.router, dependencies=_auth)
# ... all other routers
```

### One-time Google Cloud setup
1. Google Cloud Console → APIs & Services → Credentials → Create OAuth 2.0 Client ID
2. Application type: **Web application**
3. Authorized redirect URI: `http://localhost:8000/api/auth/google/callback`
4. Add to `.env`:
   ```ini
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-secret
   JWT_SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
   ALLOWED_EMAIL=your.email@gmail.com   # optional but recommended
   ```

### Critical auth gotchas
- **React StrictMode fires effects twice** — `AuthCallback.tsx` uses a `handled = useRef(false)` guard to prevent the second effect invocation from running after the URL has already changed. Never remove this guard.
- **Always use the Axios `client`** for API calls in React components — never raw `fetch()`. Raw `fetch()` does not include the JWT header, causing silent 401 failures (the `.catch(() => {})` pattern swallows the error and leaves state null). This was the root cause of Garmin/Hevy showing "Not configured" after auth was added.
- **JWT token in redirect URL must be URL-encoded** — the backend uses `urllib.parse.quote(token, safe='')` before embedding in the redirect URL.
- **Use 302, not 307 for OAuth redirects** — 307 preserves HTTP method but can behave unexpectedly in some browser/proxy setups. All `RedirectResponse` in `auth.py` use `status_code=302`.

---

## Database

SQLite at `backend/health.db`. **Never delete health.db** — it contains Sandeep's weight logs, DEXA history, and synced activities.

**Seeded on first `init_db()` call** (skipped if records already exist):
- DEXA baseline: 2026-03-13, 181.5 lbs, 28.4% BF, 123.9 lbs lean mass, visceral fat 1.38 lbs
- VO2 max baseline: 2026-03-13, 45.0
- User profile: Sandeep Rao, DOB 1979-11-11, height 68 in, goal 18% BF + VO2 50 by 2026-12-31, 2200 kcal/day

**Key models**: `WeightLog`, `DexaScan`, `Vo2MaxLog`, `StravaActivity`, `HevyWorkout`, `HevyExerciseSet`, `TrainingPlan`, `MealPlan`, `HealthInsight`, `CoachConversation`, `OAuthToken`, `UserProfile`.

To add a new table: add model to `database/models.py`, it is created automatically by `Base.metadata.create_all()` on startup.

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

| File | Key constraints |
|------|----------------|
| `coach_system.py` | **Tonal-only** (cable machine, 0–200 lbs). Upper A = horizontal push + vertical pull. Upper B = incline/overhead + horizontal pull. Lower A = quad-dominant. Lower B = hip-dominant. Never repeat movement patterns between A and B sessions. Eugene Teo + Jeff Nippard philosophy. |
| `nutrition_system.py` | Vegetarian + eggs. Bobby Parish ingredient philosophy (no seed oils, no artificial additives). Cook-once rule: dinner = next day's lunch (Tuesday–Sunday). Breakfast = 3 quick options (overnight oats / protein smoothie / eggs+toast). All ingredients available at Whole Foods, Trader Joe's, or Indian grocery. |
| `health_advisor_system.py` | Peter Attia (Outlive) + Andrew Huberman framework. VO2 max as longevity predictor. Sections: Sleep Quality, Cardiovascular Health, Body Composition, Recovery, Key Recommendations. |

### Context hash caching (training plans)
`generate_training_plan()` builds a hash from current stats + recent training + config string (`f"{s}s{c}c{r}r"`). If the hash matches the stored plan, the cached plan is returned. Changing strength/cardio/rest days forces a regeneration because the config string changes.

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
4. Session tokens persisted to `backend/garmin_session/` (garth format) and reused on restart

If garmin_session exists and tokens are valid, login succeeds without MFA (`{"status": "ok"}`).

### Hevy
Uses the `@vreippainen/hevy-mcp-server` npm package via stdio MCP protocol:
- Client in `backend/services/hevy_mcp_client.py`
- Communicates via newline-delimited JSON-RPC 2.0 to a subprocess
- MCP tool responses return `{"workouts": [...], "totalWorkouts": N}` — always extract `.get("workouts", [])`, not the raw result
- A singleton `_hevy_client_instance` is used in `claude_service.py` to avoid spawning a new subprocess per tool call
- Config: `HEVY_API_KEY` in `.env` (not email/password — those legacy fields are ignored)

---

## Claude AI Coach Chat (tool use)

`chat_with_coach()` in `claude_service.py` runs a **tool-use loop** (up to 5 rounds). It defines 4 Hevy tools (`hevy_get_workouts`, `hevy_get_exercises`, `hevy_get_exercise_progress`, `hevy_get_routines`) and passes raw MCP results back to Claude. The last 20 turns from `CoachConversation` are included as context.

---

## Frontend Patterns

### Always use the Axios client — never raw fetch()
Every API call in every React component must use `import client from "../api/client"` — not the native `fetch()` API. The Axios client (`src/api/client.ts`) attaches `Authorization: Bearer <token>` to every request and redirects to `/login` on 401. Raw `fetch()` calls will silently return 401 and leave component state null.

### Markdown rendering
All Claude-generated content (training plans, health insights, chat responses) is rendered via `MarkdownRenderer.tsx` which uses `react-markdown` + `remark-gfm`. The `remark-gfm` plugin is **required** for tables — without it, pipe characters render as raw text. Custom Tailwind styles are applied to `table`, `th`, `td`, `ul`, `ol`, `blockquote` elements inside the component.

### API clients
Each domain has its own file in `src/api/`. The base client (`client.ts`) points to `http://localhost:8000`. When adding a new endpoint, add it to the corresponding API file, not inline in the component.

### Page-level state
Pages manage their own loading/error/data state with `useState` + `useEffect`. There is no global fetch cache — data is refetched on mount or on user action. Zustand (`appStore.ts`) is available for cross-page state if needed.

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
HEVY_API_KEY=                          # Required for strength training data in Coach chat
DATABASE_URL=sqlite:///./health.db
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ORIGINS=http://localhost:5173
FRONTEND_URL=http://localhost:5173
```

`GET /api/settings/status` returns which integrations are configured (checked by Settings page).

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

---

## Adding New Features

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
