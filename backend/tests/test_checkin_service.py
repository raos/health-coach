"""Unit tests for services/checkin_service.py."""
from datetime import date, timedelta
import pytest

from services.checkin_service import _monday_of_week, upsert_weekly_checkin
from database.models import WeeklyCheckin


class TestMondayOfWeek:
    """Test the _monday_of_week helper function."""

    def test_monday_returns_itself(self):
        """Monday should return itself."""
        d = date(2026, 4, 6)  # Monday
        assert _monday_of_week(d) == d

    def test_wednesday_returns_previous_monday(self):
        """Wednesday should return the Monday of that week."""
        d = date(2026, 4, 8)  # Wednesday
        assert _monday_of_week(d) == date(2026, 4, 6)

    def test_sunday_returns_previous_monday(self):
        """Sunday should return the Monday of that week."""
        d = date(2026, 4, 12)  # Sunday
        assert _monday_of_week(d) == date(2026, 4, 6)

    def test_tuesday_returns_previous_monday(self):
        """Tuesday should return the Monday of that week."""
        d = date(2026, 4, 7)  # Tuesday
        assert _monday_of_week(d) == date(2026, 4, 6)

    def test_monday_of_new_year_cross_boundary(self):
        """Test year boundary — Sunday Jan 4 should give Monday Dec 29."""
        d = date(2026, 1, 4)  # Sunday Jan 4, 2026
        assert _monday_of_week(d) == date(2025, 12, 29)


class TestUpsertWeeklyCheckinValidation:
    """Test validation of ratings (must be 1-5 or None)."""

    def test_valid_ratings_all_5(self, test_user, db):
        """All ratings at upper bound should be accepted."""
        user, _ = test_user
        result = upsert_weekly_checkin(
            db, user.id,
            training_adherence=5,
            energy_level=5,
            sleep_quality=5,
            diet_adherence=5,
            stress_level=5,
        )
        assert result.training_adherence == 5
        assert result.energy_level == 5

    def test_valid_ratings_all_1(self, test_user, db):
        """All ratings at lower bound should be accepted."""
        user, _ = test_user
        result = upsert_weekly_checkin(
            db, user.id,
            training_adherence=1,
            energy_level=1,
            sleep_quality=1,
            diet_adherence=1,
            stress_level=1,
        )
        assert result.training_adherence == 1

    def test_valid_ratings_mixed(self, test_user, db):
        """Mixed valid ratings should be accepted."""
        user, _ = test_user
        result = upsert_weekly_checkin(
            db, user.id,
            training_adherence=3,
            energy_level=4,
            sleep_quality=2,
            diet_adherence=5,
            stress_level=1,
        )
        assert result.training_adherence == 3
        assert result.energy_level == 4

    def test_training_adherence_zero_raises(self, test_user, db):
        """training_adherence=0 should raise ValueError."""
        user, _ = test_user
        with pytest.raises(ValueError, match="training_adherence"):
            upsert_weekly_checkin(db, user.id, training_adherence=0)

    def test_energy_level_six_raises(self, test_user, db):
        """energy_level=6 should raise ValueError."""
        user, _ = test_user
        with pytest.raises(ValueError, match="energy_level"):
            upsert_weekly_checkin(db, user.id, energy_level=6)

    def test_sleep_quality_negative_raises(self, test_user, db):
        """sleep_quality=-1 should raise ValueError."""
        user, _ = test_user
        with pytest.raises(ValueError, match="sleep_quality"):
            upsert_weekly_checkin(db, user.id, sleep_quality=-1)

    def test_diet_adherence_invalid_string_raises(self, test_user, db):
        """Non-integer (type error) should be handled by Python."""
        user, _ = test_user
        # This will raise TypeError, not ValueError, but that's OK for type validation
        with pytest.raises((ValueError, TypeError)):
            upsert_weekly_checkin(db, user.id, diet_adherence="not_a_number")

    def test_stress_level_out_of_bounds_raises(self, test_user, db):
        """stress_level=10 should raise ValueError."""
        user, _ = test_user
        with pytest.raises(ValueError, match="stress_level"):
            upsert_weekly_checkin(db, user.id, stress_level=10)

    def test_none_ratings_are_allowed(self, test_user, db):
        """None values for ratings should be allowed (optional)."""
        user, _ = test_user
        result = upsert_weekly_checkin(db, user.id)
        assert result.training_adherence is None
        assert result.energy_level is None

    def test_boundary_1_is_valid(self, test_user, db):
        """stress_level=1 should be valid."""
        user, _ = test_user
        result = upsert_weekly_checkin(db, user.id, stress_level=1)
        assert result.stress_level == 1

    def test_boundary_5_is_valid(self, test_user, db):
        """diet_adherence=5 should be valid."""
        user, _ = test_user
        result = upsert_weekly_checkin(db, user.id, diet_adherence=5)
        assert result.diet_adherence == 5


class TestUpsertWeeklyCheckinInsert:
    """Test insertion of new WeeklyCheckin rows."""

    def test_insert_new_checkin_defaults_to_current_week(self, test_user, db):
        """New checkin without week_start should use Monday of current week."""
        user, _ = test_user
        result = upsert_weekly_checkin(
            db, user.id,
            training_adherence=3,
            energy_level=4,
        )
        expected_monday = _monday_of_week(date.today())
        assert result.week_start == expected_monday
        assert result.user_id == user.id

    def test_insert_new_checkin_with_explicit_week_start(self, test_user, db):
        """New checkin with explicit week_start should use that date."""
        user, _ = test_user
        target_week = date(2026, 4, 6)
        result = upsert_weekly_checkin(
            db, user.id,
            training_adherence=3,
            week_start=target_week,
        )
        assert result.week_start == target_week
        assert result.training_adherence == 3

    def test_insert_preserves_all_fields(self, test_user, db):
        """All provided fields should be stored."""
        user, _ = test_user
        result = upsert_weekly_checkin(
            db, user.id,
            training_adherence=3,
            energy_level=4,
            sleep_quality=2,
            diet_adherence=5,
            stress_level=1,
            notes="Great week!",
        )
        assert result.training_adherence == 3
        assert result.energy_level == 4
        assert result.sleep_quality == 2
        assert result.diet_adherence == 5
        assert result.stress_level == 1
        assert result.notes == "Great week!"


class TestUpsertWeeklyCheckinUpdate:
    """Test updating existing WeeklyCheckin rows."""

    def test_update_existing_same_week(self, test_user, db):
        """Calling upsert twice in same week should update the first row."""
        user, _ = test_user
        target_week = _monday_of_week(date.today())

        # First insert
        result1 = upsert_weekly_checkin(
            db, user.id,
            training_adherence=3,
            week_start=target_week,
        )
        id1 = result1.id

        # Second upsert — should update
        result2 = upsert_weekly_checkin(
            db, user.id,
            training_adherence=5,
            week_start=target_week,
        )

        assert result2.id == id1
        assert result2.training_adherence == 5

    def test_update_partial_fields(self, test_user, db):
        """Updating only some fields should preserve others."""
        user, _ = test_user
        target_week = _monday_of_week(date.today())

        # First insert with multiple fields
        result1 = upsert_weekly_checkin(
            db, user.id,
            training_adherence=3,
            energy_level=4,
            sleep_quality=2,
            week_start=target_week,
        )

        # Update only energy_level
        result2 = upsert_weekly_checkin(
            db, user.id,
            energy_level=5,
            week_start=target_week,
        )

        assert result2.training_adherence == 3  # unchanged
        assert result2.energy_level == 5  # updated
        assert result2.sleep_quality == 2  # unchanged

    def test_update_notes(self, test_user, db):
        """Updating notes should work independently."""
        user, _ = test_user
        target_week = _monday_of_week(date.today())

        upsert_weekly_checkin(
            db, user.id,
            training_adherence=3,
            notes="Original note",
            week_start=target_week,
        )

        result = upsert_weekly_checkin(
            db, user.id,
            notes="Updated note",
            week_start=target_week,
        )

        assert result.notes == "Updated note"
        assert result.training_adherence == 3


class TestUpsertWeeklyCheckinMultipleWeeks:
    """Test that different weeks are stored separately."""

    def test_different_weeks_are_separate_rows(self, test_user, db):
        """Checkins for different weeks should create separate rows."""
        user, _ = test_user
        week1 = date(2026, 3, 30)  # Monday
        week2 = date(2026, 4, 6)   # Next Monday

        result1 = upsert_weekly_checkin(
            db, user.id,
            training_adherence=3,
            week_start=week1,
        )

        result2 = upsert_weekly_checkin(
            db, user.id,
            training_adherence=5,
            week_start=week2,
        )

        assert result1.id != result2.id
        assert result1.week_start == week1
        assert result2.week_start == week2
        assert result1.training_adherence == 3
        assert result2.training_adherence == 5
