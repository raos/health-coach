# Goal Trajectory Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dashboard card that shows weight and BF% actual vs. required vs. projected trajectories, with a "weeks ahead/behind" status badge and expandable charts.

**Architecture:** A new `GET /api/dashboard/goal-projection` endpoint computes all three trajectory lines in a new `backend/services/dashboard_service.py` using pure-Python linear regression on the last 8 weeks of data. The frontend `GoalTrajectoryCard.tsx` shows a compact summary by default and expands to two stacked Recharts `LineChart` components.

**Tech Stack:** FastAPI + SQLAlchemy (backend), React 19 + TypeScript + Recharts 3.8 (frontend), Alembic (migrations), pytest (backend unit tests)

---

## File Map

| File | Change |
|------|--------|
| `backend/database/models.py` | Add `body_fat_pct` to `WeightLog`; add `weight_goal_lbs` to `UserProfile` |
| `backend/alembic/versions/<hash>.py` | Auto-generated migration |
| `backend/schemas/weight.py` | Add `body_fat_pct: Optional[float]` to `WeightLogCreate` and `WeightLogResponse` |
| `backend/routers/weight.py` | Update upsert to persist `body_fat_pct` |
| `backend/services/dashboard_service.py` | **Create** — pure projection math: `_linear_regression`, `_date_to_x`, `_compute_trajectory`, `get_goal_projection` |
| `backend/routers/dashboard.py` | Add `GET /goal-projection` route |
| `backend/tests/test_dashboard_service.py` | **Create** — unit tests for pure math functions |
| `frontend/src/types/index.ts` | Add `TrajectoryPoint`, `MetricTrajectory`, `GoalProjection`; add `body_fat_pct?` to `WeightLog`; add `weight_goal_lbs?` to `UserProfile` |
| `frontend/src/api/dashboard.ts` | Add `getDashboardGoalProjection()` |
| `frontend/src/api/weight.ts` | Add `body_fat_pct?` param to `logWeight()` |
| `frontend/src/components/dashboard/GoalTrajectoryCard.tsx` | **Create** — compact + expandable chart card |
| `frontend/src/components/dashboard/QuickMetricsLog.tsx` | Add optional BF% field to Weight tab |
| `frontend/src/pages/Dashboard.tsx` | Fetch projection, render `GoalTrajectoryCard` |
| `frontend/src/pages/Settings.tsx` | Add `weight_goal_lbs` input to Goals section |

---

## Task 1: Schema Changes + Migration

**Files:**
- Modify: `backend/database/models.py`
- Create: `backend/alembic/versions/<hash>_add_body_fat_pct_and_weight_goal.py` (auto-generated)

- [ ] **Step 1: Add `body_fat_pct` to `WeightLog` in `models.py`**

In `backend/database/models.py`, find the `WeightLog` class (currently ends at line 97). Add one line after `source`:

```python
class WeightLog(Base):
    __tablename__ = "weight_logs"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_weight_logs_user_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    date = Column(Date, nullable=False)
    weight_lbs = Column(Float, nullable=False)
    body_fat_pct = Column(Float, nullable=True)   # ← add this line
    notes = Column(Text)
    source = Column(String(20), default="manual")
    created_at = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: Add `weight_goal_lbs` to `UserProfile` in `models.py`**

In the `UserProfile` class (starts at line 269), add after the `bf_goal_pct` line:

```python
    bf_goal_pct = Column(Float, nullable=True)
    weight_goal_lbs = Column(Float, nullable=True)   # ← add this line
    vo2max_goal = Column(Float, nullable=True)
```

- [ ] **Step 3: Generate the Alembic migration**

```bash
cd backend && alembic revision --autogenerate -m "add body_fat_pct to weight_logs and weight_goal_lbs to user_profile"
```

Review the generated file in `backend/alembic/versions/`. It should contain two `op.add_column` calls.

- [ ] **Step 4: Run the migration**

```bash
cd backend && alembic upgrade head
```

Expected: no errors. Confirm with:
```bash
cd backend && python -c "from database.engine import get_db; from database.models import WeightLog; db = next(get_db()); print([c.name for c in WeightLog.__table__.columns])"
```
Expected output includes `body_fat_pct`.

- [ ] **Step 5: Commit**

```bash
git add backend/database/models.py backend/alembic/versions/
git commit -m "feat: add body_fat_pct to weight_logs and weight_goal_lbs to user_profile"
```

---

## Task 2: Extend Weight Log Schema + Endpoint

**Files:**
- Modify: `backend/schemas/weight.py`
- Modify: `backend/routers/weight.py`

- [ ] **Step 1: Update `WeightLogCreate` and `WeightLogResponse` schemas**

Replace the entire contents of `backend/schemas/weight.py`:

```python
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class WeightLogCreate(BaseModel):
    date: date
    weight_lbs: float
    body_fat_pct: Optional[float] = None
    notes: Optional[str] = None
    source: str = "manual"


class WeightLogResponse(BaseModel):
    id: int
    date: date
    weight_lbs: float
    body_fat_pct: Optional[float]
    notes: Optional[str]
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Update the upsert in `weight.py` to persist `body_fat_pct`**

In `backend/routers/weight.py`, replace the upsert block inside `log_weight()`. The existing entry update currently has three field assignments; add the `body_fat_pct` assignment:

```python
    if existing:
        existing.weight_lbs = payload.weight_lbs
        if payload.body_fat_pct is not None:
            existing.body_fat_pct = payload.body_fat_pct
        existing.notes = payload.notes
        existing.source = payload.source
        db.commit()
        db.refresh(existing)
        return existing
```

(Only update `body_fat_pct` when the caller provides it, to avoid overwriting a previously-set value with `None`.)

The new entry creation line `entry = WeightLog(user_id=user_id, **payload.model_dump())` already handles the new field — no change needed.

- [ ] **Step 3: Verify manually via Swagger**

Start the backend:
```bash
cd backend && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000/docs → `POST /api/weight/log` with:
```json
{"date": "2026-04-10", "weight_lbs": 168.0, "body_fat_pct": 21.5}
```
Expected response includes `"body_fat_pct": 21.5`.

- [ ] **Step 4: Commit**

```bash
git add backend/schemas/weight.py backend/routers/weight.py
git commit -m "feat: accept optional body_fat_pct when logging weight"
```

---

## Task 3: Projection Service (Backend Math)

**Files:**
- Create: `backend/services/dashboard_service.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_dashboard_service.py`

- [ ] **Step 1: Create the tests directory and `__init__.py`**

```bash
mkdir -p backend/tests && touch backend/tests/__init__.py
```

- [ ] **Step 2: Write failing tests for the math functions**

Create `backend/tests/test_dashboard_service.py`:

```python
from datetime import date, timedelta
import pytest

# These imports will fail until Step 3 creates the service
from services.dashboard_service import _linear_regression, _compute_trajectory


def test_linear_regression_perfect_fit():
    """Points on y = 2x + 1 should give exact coefficients."""
    points = [(1.0, 3.0), (2.0, 5.0), (3.0, 7.0)]
    slope, intercept = _linear_regression(points)
    assert abs(slope - 2.0) < 1e-9
    assert abs(intercept - 1.0) < 1e-9


def test_linear_regression_flat():
    """All same y-value → slope = 0."""
    points = [(1.0, 5.0), (2.0, 5.0), (3.0, 5.0)]
    slope, intercept = _linear_regression(points)
    assert abs(slope) < 1e-9
    assert abs(intercept - 5.0) < 1e-9


def test_linear_regression_degenerate_same_x():
    """All same x → returns slope=0, intercept=mean."""
    points = [(1.0, 3.0), (1.0, 5.0), (1.0, 7.0)]
    slope, intercept = _linear_regression(points)
    assert slope == 0.0
    assert abs(intercept - 5.0) < 1e-9


def test_compute_trajectory_returns_none_for_empty():
    assert _compute_trajectory([], 160.0, date.today() + timedelta(weeks=20)) is None


def test_compute_trajectory_structure():
    today = date.today()
    goal_date = today + timedelta(weeks=20)
    # 11 weekly data points, trending down 0.5 lbs/week
    logs = [(today - timedelta(weeks=i), 175.0 - (10 - i) * 0.5) for i in range(10, -1, -1)]
    result = _compute_trajectory(logs, 160.0, goal_date)
    assert result is not None
    assert len(result["actual"]) == 11
    assert len(result["required"]) == 2
    assert result["projected"] is not None
    assert isinstance(result["weeks_delta"], int)
    assert result["goal"] == 160.0
    assert result["current"] == pytest.approx(175.0, abs=1.0)


def test_compute_trajectory_ahead_of_schedule():
    """If trending faster than required, weeks_delta should be positive."""
    today = date.today()
    goal_date = today + timedelta(weeks=20)
    # Losing 2 lbs/week, only need 10 lbs total → done in ~5 weeks, 15 weeks ahead
    logs = [(today - timedelta(weeks=i), 170.0 - (10 - i) * 2.0) for i in range(10, -1, -1)]
    result = _compute_trajectory(logs, 160.0, goal_date)
    assert result is not None
    assert result["weeks_delta"] > 0


def test_compute_trajectory_behind_schedule():
    """If trending slower than required, weeks_delta should be negative."""
    today = date.today()
    goal_date = today + timedelta(weeks=8)
    # Almost no progress — losing 0.1 lbs/week, need 10 lbs total
    logs = [(today - timedelta(weeks=i), 170.0 - (10 - i) * 0.1) for i in range(10, -1, -1)]
    result = _compute_trajectory(logs, 160.0, goal_date)
    assert result is not None
    assert result["weeks_delta"] < 0


def test_compute_trajectory_fewer_than_3_recent_points_no_projection():
    today = date.today()
    goal_date = today + timedelta(weeks=20)
    logs = [(today - timedelta(days=3), 168.0), (today - timedelta(days=1), 167.5)]
    result = _compute_trajectory(logs, 160.0, goal_date, lookback_weeks=8)
    assert result is not None
    assert result["projected"] is None
    assert result["weeks_delta"] == 0
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_dashboard_service.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name '_linear_regression' from 'services.dashboard_service'`

- [ ] **Step 4: Create `backend/services/dashboard_service.py`**

```python
from datetime import date, timedelta
from typing import Optional
import uuid

from sqlalchemy.orm import Session


def _linear_regression(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Ordinary least-squares. Returns (slope, intercept) for y = slope*x + intercept."""
    n = len(points)
    sx = sum(x for x, _ in points)
    sy = sum(y for _, y in points)
    sxx = sum(x * x for x, _ in points)
    sxy = sum(x * y for x, y in points)
    denom = n * sxx - sx * sx
    if denom == 0:
        return 0.0, sy / n
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def _date_to_x(d: date) -> float:
    """Convert date to a float (days since 2000-01-01) for regression."""
    return float((d - date(2000, 1, 1)).days)


def _compute_trajectory(
    logs: list[tuple[date, float]],
    goal_value: float,
    goal_date: date,
    lookback_weeks: int = 8,
) -> Optional[dict]:
    """
    Compute actual / required / projected trajectory for one metric.

    Args:
        logs: List of (date, value) tuples, unsorted.
        goal_value: Target value to reach by goal_date.
        goal_date: Target date.
        lookback_weeks: How many weeks of recent data to use for regression.

    Returns None if logs is empty. Otherwise returns:
        {
            actual: [{"date": "YYYY-MM-DD", "value": float}, ...],
            required: [two-point straight line from first log to goal],
            projected: [two-point projection from today to goal_date] or None,
            current: float,
            goal: float,
            weeks_delta: int (positive = ahead, negative = behind),
        }
    """
    if not logs:
        return None

    today = date.today()
    logs_sorted = sorted(logs, key=lambda t: t[0])
    first_date, first_value = logs_sorted[0]
    _current_date, current_value = logs_sorted[-1]

    actual = [{"date": str(d), "value": round(v, 2)} for d, v in logs_sorted]

    required = [
        {"date": str(first_date), "value": round(first_value, 2)},
        {"date": str(goal_date), "value": round(goal_value, 2)},
    ]

    # Regression on recent data
    cutoff = today - timedelta(weeks=lookback_weeks)
    recent = [(d, v) for d, v in logs_sorted if d >= cutoff]
    projected = None
    weeks_delta = 0

    if len(recent) >= 3:
        points = [(_date_to_x(d), v) for d, v in recent]
        slope, intercept = _linear_regression(points)

        today_x = _date_to_x(today)
        goal_x = _date_to_x(goal_date)
        projected_today = slope * today_x + intercept
        projected_at_goal = slope * goal_x + intercept

        projected = [
            {"date": str(today), "value": round(projected_today, 2)},
            {"date": str(goal_date), "value": round(projected_at_goal, 2)},
        ]

        # weeks_delta: solve slope*x + intercept = goal_value for x
        if abs(slope) > 1e-9:
            crossing_x = (goal_value - intercept) / slope
            crossing_date = date(2000, 1, 1) + timedelta(days=int(crossing_x))
            weeks_delta = round((goal_date - crossing_date).days / 7)

    return {
        "actual": actual,
        "required": required,
        "projected": projected,
        "current": round(current_value, 2),
        "goal": round(goal_value, 2),
        "weeks_delta": weeks_delta,
    }


def get_goal_projection(db: Session, user_id: uuid.UUID) -> dict:
    """Return projection data for weight and BF% toward the user's goal date."""
    from database.models import WeightLog, UserProfile

    profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
    if not profile or not profile.goal_date:
        return {"goal_date": None, "weight": None, "bf_pct": None}

    goal_date = profile.goal_date

    weight_result = None
    if profile.weight_goal_lbs:
        weight_logs = (
            db.query(WeightLog)
            .filter(WeightLog.user_id == user_id)
            .order_by(WeightLog.date)
            .all()
        )
        weight_result = _compute_trajectory(
            [(w.date, w.weight_lbs) for w in weight_logs],
            profile.weight_goal_lbs,
            goal_date,
        )

    bf_result = None
    if profile.bf_goal_pct:
        bf_logs = (
            db.query(WeightLog)
            .filter(WeightLog.user_id == user_id, WeightLog.body_fat_pct.isnot(None))
            .order_by(WeightLog.date)
            .all()
        )
        bf_result = _compute_trajectory(
            [(w.date, w.body_fat_pct) for w in bf_logs],
            profile.bf_goal_pct,
            goal_date,
        )

    return {
        "goal_date": str(goal_date),
        "weight": weight_result,
        "bf_pct": bf_result,
    }
```

- [ ] **Step 5: Run tests and confirm they pass**

```bash
cd backend && source venv/bin/activate && python -m pytest tests/test_dashboard_service.py -v
```

Expected:
```
PASSED tests/test_dashboard_service.py::test_linear_regression_perfect_fit
PASSED tests/test_dashboard_service.py::test_linear_regression_flat
PASSED tests/test_dashboard_service.py::test_linear_regression_degenerate_same_x
PASSED tests/test_dashboard_service.py::test_compute_trajectory_returns_none_for_empty
PASSED tests/test_dashboard_service.py::test_compute_trajectory_structure
PASSED tests/test_dashboard_service.py::test_compute_trajectory_ahead_of_schedule
PASSED tests/test_dashboard_service.py::test_compute_trajectory_behind_schedule
PASSED tests/test_dashboard_service.py::test_compute_trajectory_fewer_than_3_recent_points_no_projection
8 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/services/dashboard_service.py backend/tests/
git commit -m "feat: add goal projection service with linear regression"
```

---

## Task 4: Goal Projection API Route

**Files:**
- Modify: `backend/routers/dashboard.py`

- [ ] **Step 1: Add the import and route to `dashboard.py`**

At the top of `backend/routers/dashboard.py`, add the import after the existing imports:

```python
from services import dashboard_service
```

Then add this route at the end of the file:

```python
@router.get("/goal-projection")
def get_goal_projection(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_user_id),
):
    return dashboard_service.get_goal_projection(db, user_id)
```

- [ ] **Step 2: Verify via Swagger**

With backend running, open http://localhost:8000/docs → `GET /api/dashboard/goal-projection`.

Expected response shape (values will vary):
```json
{
  "goal_date": "2026-09-01",
  "weight": {
    "actual": [{"date": "2025-10-01", "value": 175.0}],
    "required": [{"date": "2025-10-01", "value": 175.0}, {"date": "2026-09-01", "value": 160.0}],
    "projected": [{"date": "2026-04-10", "value": 168.0}, {"date": "2026-09-01", "value": 160.5}],
    "current": 168.0,
    "goal": 160.0,
    "weeks_delta": 5
  },
  "bf_pct": null
}
```

If `weight_goal_lbs` isn't set yet, both will be `null`. That's expected at this stage.

- [ ] **Step 3: Commit**

```bash
git add backend/routers/dashboard.py
git commit -m "feat: add GET /api/dashboard/goal-projection endpoint"
```

---

## Task 5: TypeScript Types

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add `body_fat_pct?` to `WeightLog` interface**

In `frontend/src/types/index.ts`, update the `WeightLog` interface (currently lines 1–8):

```typescript
export interface WeightLog {
  id: number;
  date: string;
  weight_lbs: number;
  body_fat_pct?: number | null;
  notes?: string;
  source: string;
  created_at: string;
}
```

- [ ] **Step 2: Add `weight_goal_lbs?` to `UserProfile` interface**

In the `UserProfile` interface (around line 79), add after `bf_goal_pct`:

```typescript
  bf_goal_pct: number | null;
  weight_goal_lbs?: number | null;
  vo2max_goal: number | null;
```

- [ ] **Step 3: Add the three new trajectory interfaces**

At the end of `frontend/src/types/index.ts`, add:

```typescript
export interface TrajectoryPoint {
  date: string;
  value: number;
}

export interface MetricTrajectory {
  actual: TrajectoryPoint[];
  required: TrajectoryPoint[];
  projected: TrajectoryPoint[] | null;
  current: number;
  goal: number;
  weeks_delta: number;
}

export interface GoalProjection {
  goal_date: string | null;
  weight: MetricTrajectory | null;
  bf_pct: MetricTrajectory | null;
}
```

- [ ] **Step 4: Confirm TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors related to the new types.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add GoalProjection TypeScript types"
```

---

## Task 6: Frontend API Functions

**Files:**
- Modify: `frontend/src/api/dashboard.ts`
- Modify: `frontend/src/api/weight.ts`

- [ ] **Step 1: Add `getDashboardGoalProjection()` to `dashboard.ts`**

In `frontend/src/api/dashboard.ts`, add the import at the top:

```typescript
import type { DashboardSummary, GoalProgress, ActivityFeedItem, WeightLog, Vo2MaxLog, GoalProjection } from "../types";
```

Then add the new function after `getWorkoutHeatmap`:

```typescript
export async function getDashboardGoalProjection(): Promise<GoalProjection> {
  const res = await client.get<GoalProjection>("/api/dashboard/goal-projection");
  return res.data;
}
```

- [ ] **Step 2: Update `logWeight()` in `weight.ts` to accept `body_fat_pct`**

Replace the `logWeight` function in `frontend/src/api/weight.ts`:

```typescript
export async function logWeight(
  date: string,
  weight_lbs: number,
  notes?: string,
  body_fat_pct?: number | null,
): Promise<WeightLog> {
  const res = await client.post("/api/weight/log", { date, weight_lbs, notes, body_fat_pct: body_fat_pct ?? null });
  return res.data;
}
```

- [ ] **Step 3: Confirm TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/dashboard.ts frontend/src/api/weight.ts
git commit -m "feat: add getDashboardGoalProjection API function and extend logWeight"
```

---

## Task 7: GoalTrajectoryCard Component

**Files:**
- Create: `frontend/src/components/dashboard/GoalTrajectoryCard.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/dashboard/GoalTrajectoryCard.tsx`:

```tsx
import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer,
} from "recharts";
import type { GoalProjection, MetricTrajectory, TrajectoryPoint } from "../../types";

interface Props {
  data: GoalProjection;
}

function badgeClass(weeks: number): string {
  if (weeks >= 2) return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
  if (weeks >= 0) return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200";
  return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
}

function badgeLabel(weeks: number): string {
  if (weeks === 0) return "on track";
  const abs = Math.abs(weeks);
  return weeks > 0 ? `${abs} wk${abs === 1 ? "" : "s"} ahead` : `${abs} wk${abs === 1 ? "" : "s"} behind`;
}

// Merge actual + required + projected arrays into Recharts-compatible data by date
function buildChartData(metric: MetricTrajectory): Array<Record<string, number | string>> {
  const map = new Map<string, Record<string, number | string>>();

  for (const p of metric.actual) {
    map.set(p.date, { date: p.date, actual: p.value });
  }
  for (const p of metric.required) {
    const existing = map.get(p.date) ?? { date: p.date };
    map.set(p.date, { ...existing, required: p.value });
  }
  if (metric.projected) {
    for (const p of metric.projected) {
      const existing = map.get(p.date) ?? { date: p.date };
      map.set(p.date, { ...existing, projected: p.value });
    }
  }

  return Array.from(map.values()).sort((a, b) =>
    (a.date as string).localeCompare(b.date as string)
  );
}

function StatBox({
  label,
  current,
  goal,
  unit,
  weeksDelta,
}: {
  label: string;
  current: number;
  goal: number;
  unit: string;
  weeksDelta: number;
}) {
  return (
    <div className="flex-1 border border-gray-200 dark:border-gray-700 rounded-lg p-3 text-center">
      <div className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-1">
        {label}
      </div>
      <div className="text-xl font-bold text-gray-900 dark:text-gray-100">
        {current.toFixed(1)}
        <span className="text-sm font-normal text-gray-500 dark:text-gray-400 ml-1">{unit}</span>
      </div>
      <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">
        goal {goal.toFixed(1)}{unit}
      </div>
      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badgeClass(weeksDelta)}`}>
        {badgeLabel(weeksDelta)}
      </span>
    </div>
  );
}

function TrajectoryChart({
  metric,
  color,
  unit,
  today,
}: {
  metric: MetricTrajectory;
  color: string;
  unit: string;
  today: string;
}) {
  const chartData = buildChartData(metric);

  return (
    <ResponsiveContainer width="100%" height={160}>
      <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10 }}
          tickFormatter={(v: string) => v.slice(5)}   // "MM-DD"
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10 }}
          width={38}
          tickFormatter={(v: number) => `${v.toFixed(0)}${unit}`}
          domain={["auto", "auto"]}
        />
        <Tooltip
          formatter={(v: number) => [`${v.toFixed(1)}${unit}`]}
          labelFormatter={(l: string) => l}
        />
        <ReferenceLine x={today} stroke="#94a3b8" strokeDasharray="4 2" label={{ value: "Today", fontSize: 9, fill: "#94a3b8" }} />
        <Line dataKey="actual" stroke={color} strokeWidth={2} dot={false} name="Actual" connectNulls={false} />
        <Line dataKey="required" stroke="#94a3b8" strokeWidth={1.5} strokeDasharray="5 3" dot={false} name="Required" connectNulls />
        {metric.projected && (
          <Line dataKey="projected" stroke={color} strokeWidth={1.5} strokeDasharray="5 3" dot={false} name="Projected" connectNulls />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}

export default function GoalTrajectoryCard({ data }: Props) {
  const [expanded, setExpanded] = useState(false);

  const hasWeight = data.weight !== null;
  const hasBf = data.bf_pct !== null;

  if (!hasWeight && !hasBf) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100 mb-2">Goal Trajectory</h3>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Set your weight goal and goal date in{" "}
          <a href="/settings" className="text-blue-600 hover:underline">Settings → Goals</a> to see your trajectory.
        </p>
      </div>
    );
  }

  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-900 dark:text-gray-100">Goal Trajectory</h3>
        {data.goal_date && (
          <span className="text-xs text-gray-500 dark:text-gray-400">by {data.goal_date}</span>
        )}
      </div>

      {/* Compact stat boxes */}
      <div className="flex gap-3 mb-3">
        {hasWeight && (
          <StatBox
            label="Weight"
            current={data.weight!.current}
            goal={data.weight!.goal}
            unit="lbs"
            weeksDelta={data.weight!.weeks_delta}
          />
        )}
        {hasBf && (
          <StatBox
            label="Body Fat"
            current={data.bf_pct!.current}
            goal={data.bf_pct!.goal}
            unit="%"
            weeksDelta={data.bf_pct!.weeks_delta}
          />
        )}
      </div>

      {/* Expand toggle */}
      <button
        onClick={() => setExpanded((e) => !e)}
        className="w-full flex items-center justify-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline py-1"
      >
        {expanded ? <><ChevronUp className="w-3 h-3" /> Hide charts</> : <><ChevronDown className="w-3 h-3" /> Show charts</>}
      </button>

      {/* Expanded charts */}
      {expanded && (
        <div className="mt-3 space-y-4">
          {hasWeight && (
            <div>
              <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Weight (lbs)</div>
              <TrajectoryChart metric={data.weight!} color="#3b82f6" unit="lbs" today={today} />
            </div>
          )}
          {hasBf && (
            <div>
              <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Body Fat (%)</div>
              <TrajectoryChart metric={data.bf_pct!} color="#f97316" unit="%" today={today} />
            </div>
          )}
          <div className="flex items-center gap-4 text-xs text-gray-400">
            <span className="flex items-center gap-1"><span className="inline-block w-4 h-0.5 bg-gray-400"></span> Actual</span>
            <span className="flex items-center gap-1"><span className="inline-block w-4 h-0.5 border-t-2 border-dashed border-gray-400"></span> Required</span>
            <span className="flex items-center gap-1"><span className="inline-block w-4 h-0.5 border-t-2 border-dashed border-blue-400"></span> Projected</span>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Confirm TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/dashboard/GoalTrajectoryCard.tsx
git commit -m "feat: create GoalTrajectoryCard component"
```

---

## Task 8: Wire GoalTrajectoryCard into Dashboard

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Add the import and state**

At the top of `Dashboard.tsx`, add to the existing component imports:

```typescript
import GoalTrajectoryCard from "../components/dashboard/GoalTrajectoryCard";
```

Add to the existing API imports line:

```typescript
import { getDashboardSummary, getWeightTrend, getActivityFeed, getGoalProgress, getWorkoutHeatmap, getDashboardGoalProjection } from "../api/dashboard";
```

Add to the existing types import line:

```typescript
import type { DashboardSummary, WeightLog, ActivityFeedItem, GoalProgress as GoalProgressType, UserProfile, GoalProjection } from "../types";
```

- [ ] **Step 2: Add state and fetch**

After `const [heatmapData, setHeatmapData] = useState<WorkoutDay[]>([]);` (line 29), add:

```typescript
const [goalProjection, setGoalProjection] = useState<GoalProjection | null>(null);
```

In the `fetchAll` function, extend the `Promise.all` to include the new fetch and destructure it:

```typescript
const [s, wt, af, gp, hm, proj] = await Promise.all([
  getDashboardSummary(),
  getWeightTrend(90),
  getActivityFeed(10),
  getGoalProgress(),
  getWorkoutHeatmap(12),
  getDashboardGoalProjection(),
]);
setSummary(s);
setWeightTrend(wt);
setActivities(af);
setGoalProgress(gp);
setHeatmapData(hm);
setGoalProjection(proj);
```

- [ ] **Step 3: Render the card**

In the JSX right column (after `<Vo2GaugeCard ... />` and before `<QuickMetricsLog .../>`), add:

```tsx
{goalProjection && <GoalTrajectoryCard data={goalProjection} />}
```

The right column section becomes:

```tsx
{/* Right column: Goal Progress → VO2 Trend → Goal Trajectory → Quick Weight Log */}
<div className="flex flex-col gap-4">
  <GoalProgress ... />
  {currentVO2 !== null && hasVO2Goal && (
    <Vo2GaugeCard ... />
  )}
  {goalProjection && <GoalTrajectoryCard data={goalProjection} />}
  <QuickMetricsLog onLogged={fetchAll} />
</div>
```

- [ ] **Step 4: Start the app and verify the card appears**

```bash
# Terminal 1
cd backend && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2
cd frontend && npm run dev
```

Open http://localhost:5173 and verify:
- GoalTrajectoryCard appears in the right column
- If `weight_goal_lbs` is not set, it shows the "Set your goals" message with Settings link
- No console errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: wire GoalTrajectoryCard into Dashboard"
```

---

## Task 9: Add BF% Input to Weight Log Widget

**Files:**
- Modify: `frontend/src/components/dashboard/QuickMetricsLog.tsx`

- [ ] **Step 1: Add BF% state and update weight submission**

In `QuickMetricsLog.tsx`, add state for the optional BF% field (after `const [weight, setWeight] = useState(""); `):

```typescript
const [weightBfPct, setWeightBfPct] = useState("");
```

Update the weight submission block inside `handleSubmit`:

```typescript
if (tab === "weight") {
  if (!weight || isNaN(Number(weight))) { setError("Enter a valid weight"); return; }
  const bfPct = weightBfPct && !isNaN(Number(weightBfPct)) ? Number(weightBfPct) : null;
  await logWeight(today, Number(weight), undefined, bfPct);
  setWeight("");
  setWeightBfPct("");
}
```

- [ ] **Step 2: Add the optional BF% input to the weight tab JSX**

Replace the weight tab JSX block (currently lines 99–104):

```tsx
{tab === "weight" && (
  <div className="space-y-2">
    <div className="flex items-center gap-2">
      <input type="number" step="0.1" placeholder="Weight" value={weight}
        onChange={(e) => setWeight(e.target.value)} className={inputCls} />
      <span className="text-sm text-gray-500 dark:text-gray-400 font-medium">lbs</span>
    </div>
    <div className="flex items-center gap-2">
      <input type="number" step="0.1" min="5" max="50" placeholder="Body fat % (optional)" value={weightBfPct}
        onChange={(e) => setWeightBfPct(e.target.value)} className={inputCls} />
      <span className="text-sm text-gray-500 dark:text-gray-400 font-medium">%</span>
    </div>
  </div>
)}
```

- [ ] **Step 3: Verify in browser**

Open http://localhost:5173 → Dashboard → "Log Today" widget → Weight tab.
- Weight input is present
- Body fat % optional input is below it
- Submit with weight only: response should include `body_fat_pct: null`
- Submit with both: verify via Swagger `GET /api/weight/history` that `body_fat_pct` is persisted

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/dashboard/QuickMetricsLog.tsx
git commit -m "feat: add optional BF% input to weight log widget"
```

---

## Task 10: Add Weight Goal to Settings Page

**Files:**
- Modify: `frontend/src/pages/Settings.tsx`

- [ ] **Step 1: Change the Goals grid from 3 to 2 columns and add Weight Goal field**

Find the Goals section in `Settings.tsx` (around line 744). Replace the `grid-cols-3` div with a 2-column grid that includes the new Weight Goal field:

```tsx
{/* Goals */}
<div>
  <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 mb-3">Goals</h3>
  <div className="grid grid-cols-2 gap-4">
    <div>
      <label className={labelClass}>Body Fat Goal (%)</label>
      <input
        type="number"
        value={profileForm.bf_goal_pct ?? ""}
        onChange={(e) => handleFieldChange("bf_goal_pct", e.target.value ? parseFloat(e.target.value) : null)}
        step="0.1" min="5" max="50"
        className={inputClass}
      />
    </div>
    <div>
      <label className={labelClass}>Weight Goal (lbs)</label>
      <input
        type="number"
        value={(profileForm as any).weight_goal_lbs ?? ""}
        onChange={(e) => handleFieldChange("weight_goal_lbs", e.target.value ? parseFloat(e.target.value) : null)}
        step="0.1" min="80" max="400"
        className={inputClass}
      />
    </div>
    <div>
      <label className={labelClass}>VO&#8322; Max Goal</label>
      <input
        type="number"
        value={profileForm.vo2max_goal ?? ""}
        onChange={(e) => handleFieldChange("vo2max_goal", e.target.value ? parseFloat(e.target.value) : null)}
        step="1" min="20" max="90"
        className={inputClass}
      />
    </div>
    <div>
      <label className={labelClass}>Goal Date</label>
      <input
        type="date"
        value={profileForm.goal_date ?? ""}
        onChange={(e) => handleFieldChange("goal_date", e.target.value)}
        className={inputClass}
      />
    </div>
  </div>
</div>
```

Note: `(profileForm as any).weight_goal_lbs` is needed because `profileForm` is typed as `UserProfile` which we've updated to include `weight_goal_lbs?`. If TypeScript complains, use `profileForm.weight_goal_lbs` directly — the `UserProfile` interface now includes that field.

- [ ] **Step 2: Confirm TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Verify in browser**

Open http://localhost:5173 → Settings → Profile tab → scroll to Goals section.
- Four fields: BF% Goal, Weight Goal, VO2 Max Goal, Goal Date
- Enter a weight goal (e.g. 160) and save
- Return to Dashboard — `GoalTrajectoryCard` should now show the weight trajectory with actual data

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Settings.tsx
git commit -m "feat: add Weight Goal field to Settings Goals section"
```

---

## End-to-End Verification

- [ ] Set `weight_goal_lbs` in Settings (e.g. 160) and ensure `goal_date` and `bf_goal_pct` are also set
- [ ] Log a weight entry from the Dashboard with an optional BF% value
- [ ] Confirm `GET /api/dashboard/goal-projection` via Swagger returns non-null `weight` and `bf_pct` objects
- [ ] Open Dashboard — GoalTrajectoryCard shows compact stat boxes with status badges
- [ ] Click "Show charts" — both charts render with historical + projected lines and "Today" marker
- [ ] Log weight from the weight tab with no BF% — `body_fat_pct` is null in response, previously-set BF% on a prior log is unaffected
- [ ] Run backend tests: `cd backend && python -m pytest tests/test_dashboard_service.py -v` — 8 passed
