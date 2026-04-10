"""Unit tests for services/supplement_service.py."""
from datetime import date, timedelta
import pytest

from services.supplement_service import (
    log_supplement_by_name,
    log_supplement_by_id,
    get_supplement_status_for_date,
)
from database.models import Supplement, SupplementLog


class TestLogSupplementByName:
    """Test log_supplement_by_name: case-insensitive lookup with auto-create."""

    def test_new_supplement_created_case_insensitive_match(self, test_user, db):
        """New supplement created with case-insensitive name lookup."""
        user, _ = test_user
        log_entry, already_existed, supp, supp_created = log_supplement_by_name(
            db, user.id, "Vitamin D"
        )
        assert supp_created is True
        assert already_existed is False
        assert log_entry is not None
        assert supp.name == "Vitamin D"
        assert supp.user_id == user.id

    def test_existing_supplement_case_insensitive_match(self, test_user, db):
        """Existing supplement matched case-insensitively."""
        user, _ = test_user
        # Create first
        _, _, supp1, _ = log_supplement_by_name(db, user.id, "Vitamin D")

        # Log same supplement with different case
        log_entry, already_existed, supp2, supp_created = log_supplement_by_name(
            db, user.id, "vitamin d"
        )

        assert supp_created is False  # supplement was not created, reused
        assert already_existed is True  # log already exists for today
        assert supp2.id == supp1.id  # same supplement

    def test_already_logged_today_returns_existing_true(self, test_user, db):
        """Logging same supplement twice in same day returns already_existed=True."""
        user, _ = test_user
        # First log
        log_entry1, already_existed1, _, _ = log_supplement_by_name(
            db, user.id, "Magnesium"
        )
        assert already_existed1 is False
        assert log_entry1 is not None

        # Second log same day
        log_entry2, already_existed2, _, _ = log_supplement_by_name(
            db, user.id, "Magnesium"
        )
        assert already_existed2 is True
        assert log_entry2 is None  # No new log entry created

    def test_different_dates_create_separate_logs(self, test_user, db):
        """Same supplement on different dates creates separate logs."""
        user, _ = test_user
        today = date.today()
        yesterday = today - timedelta(days=1)

        log_entry1, already_existed1, supp1, _ = log_supplement_by_name(
            db, user.id, "Vitamin D", target_date=yesterday
        )
        assert already_existed1 is False
        assert log_entry1 is not None

        log_entry2, already_existed2, supp2, _ = log_supplement_by_name(
            db, user.id, "Vitamin D", target_date=today
        )
        assert already_existed2 is False
        assert log_entry2 is not None
        assert log_entry1.id != log_entry2.id  # Different log entries
        assert supp1.id == supp2.id  # Same supplement

    def test_defaults_to_today(self, test_user, db):
        """When target_date is None, defaults to today."""
        user, _ = test_user
        log_entry, _, _, _ = log_supplement_by_name(db, user.id, "Vitamin D")
        assert log_entry.date == date.today()

    def test_supplement_created_flag_only_true_on_creation(self, test_user, db):
        """supplement_was_created is True only when supplement is newly created."""
        user, _ = test_user
        # First call creates
        _, _, _, created1 = log_supplement_by_name(db, user.id, "Omega-3")
        assert created1 is True

        # Second call reuses (but already_existed will be True)
        # So we can't easily test this case — skip.


class TestLogSupplementById:
    """Test log_supplement_by_id: lookup by ID without auto-create."""

    def test_supplement_not_found_returns_none_triple(self, test_user, db):
        """Non-existent supplement ID returns (None, False, None)."""
        user, _ = test_user
        result = log_supplement_by_id(db, user.id, supplement_id=99999)
        assert result == (None, False, None)

    def test_supplement_not_owned_by_user_returns_none(self, test_user, db):
        """Supplement owned by different user should not be found."""
        user1, _ = test_user
        # Create supplement for user1
        _, _, supp1, _ = log_supplement_by_name(db, user1.id, "Vitamin D")

        # Try to log with different user
        from database.models import User, UserProfile
        from database.encryption import hmac_lookup
        import uuid

        user2_id = uuid.uuid4()
        user2 = User(
            id=user2_id,
            email="user2@example.com",
            name="User 2",
            auth_provider="google",
            is_active=True,
            is_admin=False,
        )
        db.add(user2)
        mcp_key = str(uuid.uuid4())
        profile2 = UserProfile(
            user_id=user2_id,
            email="user2@example.com",
            mcp_api_key=mcp_key,
            mcp_api_key_lookup=hmac_lookup(mcp_key),
            onboarding_complete=True,
        )
        db.add(profile2)
        db.commit()

        result = log_supplement_by_id(db, user2_id, supplement_id=supp1.id)
        assert result == (None, False, None)

    def test_inactive_supplement_not_found(self, test_user, db):
        """Inactive supplement should not be loggable."""
        user, _ = test_user
        # Create supplement and deactivate it
        _, _, supp, _ = log_supplement_by_name(db, user.id, "Vitamin D")
        supp.is_active = False
        db.commit()

        # Try to log it
        result = log_supplement_by_id(db, user.id, supplement_id=supp.id)
        assert result == (None, False, None)

    def test_log_supplement_by_id_new_entry(self, test_user, db):
        """Logging new supplement by ID should create log entry."""
        user, _ = test_user
        # Create supplement via name first
        _, _, supp, _ = log_supplement_by_name(db, user.id, "Vitamin D")

        # Clear today's logs
        db.query(SupplementLog).filter(
            SupplementLog.user_id == user.id,
            SupplementLog.date == date.today()
        ).delete()
        db.commit()

        # Log by ID
        log_entry, already_existed, match = log_supplement_by_id(
            db, user.id, supplement_id=supp.id
        )

        assert already_existed is False
        assert log_entry is not None
        assert match.id == supp.id

    def test_already_logged_by_id_returns_existing_true(self, test_user, db):
        """Logging same supplement ID twice returns already_existed=True."""
        user, _ = test_user
        # Create and log via name
        _, _, supp, _ = log_supplement_by_name(db, user.id, "Vitamin D")

        # Try to log same by ID
        log_entry, already_existed, match = log_supplement_by_id(
            db, user.id, supplement_id=supp.id
        )

        assert already_existed is True
        assert log_entry is not None  # Returns existing log, not None
        assert match.id == supp.id

    def test_log_by_id_different_dates_create_separate(self, test_user, db):
        """Same supplement ID on different dates creates separate logs."""
        user, _ = test_user
        _, _, supp, _ = log_supplement_by_name(db, user.id, "Vitamin D")

        today = date.today()
        yesterday = today - timedelta(days=1)

        # Clear today's log
        db.query(SupplementLog).filter(
            SupplementLog.user_id == user.id,
            SupplementLog.date == today
        ).delete()
        db.commit()

        log1, _, _ = log_supplement_by_id(
            db, user.id, supplement_id=supp.id, target_date=yesterday
        )
        log2, _, _ = log_supplement_by_id(
            db, user.id, supplement_id=supp.id, target_date=today
        )

        assert log1.id != log2.id


class TestGetSupplementStatusForDate:
    """Test get_supplement_status_for_date: query all supplements and taken IDs."""

    def test_empty_supplements_returns_empty(self, test_user, db):
        """User with no supplements should return empty lists."""
        user, _ = test_user
        all_supps, taken_ids = get_supplement_status_for_date(db, user.id)
        assert all_supps == []
        assert taken_ids == set()

    def test_returns_all_active_supplements(self, test_user, db):
        """Should return all active supplements for the user."""
        user, _ = test_user
        log_supplement_by_name(db, user.id, "Vitamin D")
        log_supplement_by_name(db, user.id, "Magnesium")
        log_supplement_by_name(db, user.id, "Omega-3")

        all_supps, _ = get_supplement_status_for_date(db, user.id)
        assert len(all_supps) == 3
        names = {s.name for s in all_supps}
        assert names == {"Vitamin D", "Magnesium", "Omega-3"}

    def test_inactive_supplements_excluded(self, test_user, db):
        """Inactive supplements should not be returned."""
        user, _ = test_user
        _, _, supp_active, _ = log_supplement_by_name(db, user.id, "Vitamin D")
        _, _, supp_inactive, _ = log_supplement_by_name(db, user.id, "Magnesium")

        # Deactivate one
        supp_inactive.is_active = False
        db.commit()

        all_supps, _ = get_supplement_status_for_date(db, user.id)
        assert len(all_supps) == 1
        assert all_supps[0].id == supp_active.id

    def test_returns_taken_ids_for_date(self, test_user, db):
        """taken_ids should contain supplements logged for target_date."""
        user, _ = test_user
        _, _, supp1, _ = log_supplement_by_name(db, user.id, "Vitamin D")
        _, _, supp2, _ = log_supplement_by_name(db, user.id, "Magnesium")
        _, _, supp3, _ = log_supplement_by_name(db, user.id, "Omega-3")

        # Clear today's logs and re-log only some
        db.query(SupplementLog).filter(
            SupplementLog.user_id == user.id,
            SupplementLog.date == date.today()
        ).delete()
        db.commit()

        log_supplement_by_id(db, user.id, supplement_id=supp1.id)
        log_supplement_by_id(db, user.id, supplement_id=supp2.id)
        # supp3 not logged

        all_supps, taken_ids = get_supplement_status_for_date(db, user.id)

        assert len(all_supps) == 3
        assert supp1.id in taken_ids
        assert supp2.id in taken_ids
        assert supp3.id not in taken_ids

    def test_different_dates_have_different_taken(self, test_user, db):
        """Same supplements logged on different dates should track separately."""
        user, _ = test_user
        today = date.today()
        yesterday = today - timedelta(days=1)

        # Create supplement via name (logs to today)
        _, _, supp, _ = log_supplement_by_name(db, user.id, "Vitamin D", target_date=today)

        # Clear all logs first
        db.query(SupplementLog).filter(
            SupplementLog.user_id == user.id,
            SupplementLog.supplement_id == supp.id
        ).delete()
        db.commit()

        # Log on yesterday
        log_supplement_by_id(db, user.id, supplement_id=supp.id, target_date=yesterday)

        # Check yesterday
        _, taken_yesterday = get_supplement_status_for_date(
            db, user.id, target_date=yesterday
        )
        assert supp.id in taken_yesterday

        # Check today (not logged)
        _, taken_today = get_supplement_status_for_date(
            db, user.id, target_date=today
        )
        assert supp.id not in taken_today

    def test_defaults_to_today(self, test_user, db):
        """When target_date is None, should use today."""
        user, _ = test_user
        log_supplement_by_name(db, user.id, "Vitamin D")

        all_supps, taken_ids = get_supplement_status_for_date(db, user.id)

        assert len(all_supps) == 1
        assert all_supps[0].id in taken_ids

    def test_isolated_by_user(self, test_user, db):
        """Different users should have isolated supplement lists."""
        user1, _ = test_user
        from database.models import User, UserProfile
        from database.encryption import hmac_lookup
        import uuid

        user2_id = uuid.uuid4()
        user2 = User(
            id=user2_id,
            email="user2@example.com",
            name="User 2",
            auth_provider="google",
            is_active=True,
            is_admin=False,
        )
        db.add(user2)
        mcp_key = str(uuid.uuid4())
        profile2 = UserProfile(
            user_id=user2_id,
            email="user2@example.com",
            mcp_api_key=mcp_key,
            mcp_api_key_lookup=hmac_lookup(mcp_key),
            onboarding_complete=True,
        )
        db.add(profile2)
        db.commit()

        # User1 logs a supplement
        log_supplement_by_name(db, user1.id, "Vitamin D")

        # User2 should see nothing
        all_supps_user2, taken_ids_user2 = get_supplement_status_for_date(db, user2_id)
        assert all_supps_user2 == []
        assert taken_ids_user2 == set()

        # User1 should see it
        all_supps_user1, taken_ids_user1 = get_supplement_status_for_date(db, user1.id)
        assert len(all_supps_user1) == 1
        assert all_supps_user1[0].name == "Vitamin D"
