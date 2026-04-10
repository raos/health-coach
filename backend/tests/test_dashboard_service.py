from datetime import date, timedelta
import pytest

# These imports will fail until Step 4 creates the service
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
    # 11 weekly data points, trending down 0.5 lbs/week; most recent (today) is 175.0
    logs = [(today - timedelta(weeks=i), 175.0 - i * 0.5) for i in range(10, -1, -1)]
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
