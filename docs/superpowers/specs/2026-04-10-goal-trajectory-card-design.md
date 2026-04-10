# Goal Trajectory Card — Design Spec

**Date:** 2026-04-10  
**Status:** Approved

---

## Problem

Sandeep tracks weight and body fat % toward a goal date. The dashboard shows raw numbers and a weight trend chart, but there is no visualization of whether he is on track to hit his goals. There's no answer to "will I get there in time?"

## Solution

A dashboard card that shows actual trajectory vs. required pace and projects where he'll land by goal date — with a clear "weeks ahead/behind" status at a glance.

---

## Design Decisions

| Question | Decision |
|----------|----------|
| Metrics to project | Weight + Body Fat % |
| BF% data entry | Optional field when logging weight (manual, nullable) |
| Card layout | Compact summary (always visible) + expandable charts |
| Chart time range | History + future: actual data from first log, projection from today to goal date |
| Projection math location | Backend — dedicated `GET /api/dashboard/goal-projection` endpoint |

---

## Data Model Changes

**`WeightLog` model** — add one nullable column:
```python
body_fat_pct = Column(Float, nullable=True)
```

**`UserProfile` model** — add one nullable column:
```python
weight_goal_lbs = Column(Float, nullable=True)
```

Both changes require an Alembic migration. Nullable so existing data is unaffected.

---

## API

### `GET /api/dashboard/goal-projection`

Returns pre-computed projection data for both metrics.

**Response shape:**
```json
{
  "goal_date": "2026-09-01",
  "weight": {
    "actual": [{"date": "2025-10-01", "value": 175.0}, ...],
    "required": [{"date": "2025-10-01", "value": 175.0}, {"date": "2026-09-01", "value": 160.0}],
    "projected": [{"date": "2026-04-10", "value": 168.0}, {"date": "2026-07-15", "value": 160.0}],
    "current": 168.0,
    "goal": 160.0,
    "weeks_delta": 7
  },
  "bf_pct": { "...same shape..." }
}
```

**Projection logic:**
- **Required line** — straight line from (earliest log date, earliest value) → (goal_date, goal_value)
- **Projected line** — linear regression on last 8 weeks of actual data, extrapolated to goal_date
- **`weeks_delta`** — where projected line crosses goal value vs. goal_date, in weeks. Positive = ahead, negative = behind.

**Edge cases:**
- Goal or goal_date not set → return `null` for that metric
- Fewer than 3 data points → `projected: null`

### `POST /api/weight/log` (extended)

Accepts optional `body_fat_pct: float | null` in the request body.

---

## Frontend

### `GoalTrajectoryCard.tsx` — new component

**Collapsed state (always visible):**
- Two stat boxes side-by-side: Weight and Body Fat %
- Each: current value, goal value, status badge
- Badge colors: green (≥2 weeks ahead), yellow (0–2 weeks), red (behind)

**Expanded state:**
- Two stacked Recharts `LineChart` components
- Each has 3 lines:
  - Solid — actual historical data
  - Dashed grey (`#94a3b8`) — required linear path
  - Dashed colored — projected path
- `<ReferenceLine>` vertical "Today" marker
- X-axis: from first log date to goal_date

### Dashboard changes
- `GoalTrajectoryCard` placed after the VO2 Max gauge card
- Weight log quick-entry widget gets optional "Body Fat % (optional)" number input

### Settings page changes
- "Weight Goal (lbs)" number input added to Profile tab alongside existing BF% goal field

---

## Verification

1. `alembic upgrade head` — no errors
2. Log weight + BF% from dashboard widget — appears in `weight_logs.body_fat_pct`
3. Set weight goal in Settings — `user_profile.weight_goal_lbs` saved
4. `GET /api/dashboard/goal-projection` via Swagger — all three lines returned with correct shape
5. Dashboard — card renders collapsed with correct values and badges
6. Expand card — charts show history + projection with Today marker
7. Edge case: no `weight_goal_lbs` set → `weight: null`, card shows "Set your goals in Settings"
