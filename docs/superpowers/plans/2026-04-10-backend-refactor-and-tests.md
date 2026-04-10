# Backend Refactoring & Testing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `datetime.utcnow()` deprecations across the backend, then write comprehensive unit and integration tests for all key service and router layers.

**Architecture:** Two scopes — (1) targeted refactoring of deprecated datetime calls and settings_status business logic; (2) pytest test suite with unit tests for pure/service functions and integration tests using FastAPI TestClient against a real PostgreSQL test database with per-test table truncation.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0.36, pytest 9.x (installed), httpx (installed), PostgreSQL, `unittest.mock` (stdlib), PyJWT

---

## Scope Check

This plan covers two independent subsystems — refactoring and testing — but they are strongly coupled (tests verify the refactored code) so they are delivered as one plan. Each task is independently committable.

---

## File Structure

**Modify (refactoring):**
- `backend/database/models.py:1` — add `timezone` to imports; update all `default=datetime.utcnow` column defaults to `lambda: datetime.now(timezone.utc)`
- `backend/routers/auth.py:1` — add `timezone` to imports; replace all `datetime.utcnow()` calls with `datetime.now(timezone.utc)`

**Create (test infrastructure):**
- `backend/pytest.ini` — pytest configuration
- `backend/tests/conftest.py` — shared fixtures: test DB engine, session, TestClient, JWT helpers, user factories

**Create (unit tests — no real DB):**
- `backend/tests/test_encryption.py` — `encrypt_value`, `decrypt_value`, `hmac_lookup`, `EncryptedString` roundtrip
- `backend/tests/test_dependencies.py` — `verify_token`, `get_user_id` with real JWT encoding
- `backend/tests/test_checkin_service.py` — `_monday_of_week`, rating validation in `upsert_weekly_checkin`
- `backend/tests/test_supplement_service.py` — `log_supplement_by_name`, `log_supplement_by_id`, `get_supplement_status_for_date` with mocked session

**Create (integration tests — real test PostgreSQL DB):**
- `backend/tests/test_router_weight.py` — log weight, history, delete
- `backend/tests/test_router_body_composition.py` — log body comp, history
- `backend/tests/test_router_supplements.py` — CRUD + daily logging
- `backend/tests/test_router_checkin.py` — upsert, latest, history
- `backend/tests/test_router_auth.py` — validate_invite, me, logout, invite code CRUD
- `backend/tests/test_router_admin.py` — list users, update user, audit log, stats

---

## Task 1: Create pytest.ini

**Files:**
- Create: `backend/pytest.ini`

- [ ] **Step 1: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

- [ ] **Step 2: Verify pytest still finds and runs existing tests**

```bash
cd backend && source venv/bin/activate && pytest tests/test_dashboard_service.py -v
```

Expected: `8 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/pytest.ini
git commit -m "test: add pytest.ini configuration"
```

---

## Task 2: Fix `datetime.utcnow()` deprecations in `database/models.py`

`datetime.utcnow()` is deprecated since Python 3.12 — it returns a naive datetime with no timezone info, which causes comparison bugs when mixed with timezone-aware datetimes (as seen in `dependencies.py` session revocation check).

**Files:**
- Modify: `backend/database/models.py`

- [ ] **Step 1: Update the import line at the top of `models.py`**

The current import is:
```python
from datetime import datetime, date
```

Change it to:
```python
from datetime import datetime, date, timezone
```

- [ ] **Step 2: Replace all `default=datetime.utcnow` with timezone-aware lambdas**

Use global search-replace. Every column that currently has `default=datetime.utcnow` must become `default=lambda: datetime.now(timezone.utc)`.

Affected lines (search for `datetime.utcnow` in `models.py`):
- `User.created_at`
- `MagicLinkToken.created_at`
- `UserConsent.consented_at`
- `AuditLog.created_at`
- `WeightLog.created_at`
- `BodyCompositionLog.created_at`
- `Vo2MaxLog.created_at`
- `StravaActivity.synced_at`
- `HevyWorkout.synced_at`
- `DailyHealthCache.synced_at`
- `OAuthToken.updated_at` (both `default` and `onupdate`)
- `HealthInsight.generated_at`
- `CoachConversation.created_at`
- `TrainingPlan.generated_at`
- `MealPlan.generated_at`

For `onupdate=datetime.utcnow` specifically: change to `onupdate=lambda: datetime.now(timezone.utc)`.

After editing, `grep "utcnow" backend/database/models.py` must return zero lines.

- [ ] **Step 3: Verify no import errors**

```bash
cd backend && source venv/bin/activate && python -c "from database.models import Base; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/database/models.py
git commit -m "fix: replace deprecated datetime.utcnow() with timezone-aware equivalents in models"
```

---

## Task 3: Fix `datetime.utcnow()` in `routers/auth.py`

**Files:**
- Modify: `backend/routers/auth.py`

- [ ] **Step 1: Update the import**

Current:
```python
from datetime import datetime, timedelta, timezone
```

`timezone` is already imported in auth.py — verify this. If not present, add it.

- [ ] **Step 2: Replace every `datetime.utcnow()` call**

Search for `datetime.utcnow()` in `routers/auth.py` and replace with `datetime.now(timezone.utc)`.

Occurrences (check each):
- `_validate_invite`: `invite.expires_at < datetime.utcnow()` → `invite.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)` (expires_at is naive, so we must make it aware for comparison)
- `google_callback`: `invite.used_at = datetime.utcnow()`
- `send_magic_link`: `datetime.utcnow() + timedelta(minutes=15)`
- `verify_magic_link`: `ml.expires_at < datetime.utcnow()` → same naive→aware fix
- `create_invite_code`: `datetime.utcnow() + timedelta(days=...)`
- `logout`: `db_user.last_logout_at = datetime.utcnow()`

For all `<= datetime.utcnow()` / `< datetime.utcnow()` comparisons against naive DB columns (`expires_at`, `ml.expires_at`): replace with `.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc)`.

For all assignment cases (setting a column value): `datetime.now(timezone.utc)`.

- [ ] **Step 3: Verify**

```bash
cd backend && source venv/bin/activate && python -c "from routers.auth import router; print('OK')"
grep "utcnow" backend/routers/auth.py && echo "FAIL: utcnow still present" || echo "PASS: no utcnow"
```

Expected: `OK` then `PASS: no utcnow`

- [ ] **Step 4: Commit**

```bash
git add backend/routers/auth.py
git commit -m "fix: replace deprecated datetime.utcnow() with timezone-aware equivalents in auth router"
```

---

## Task 4: Create test infrastructure (`conftest.py`)

**Files:**
- Create: `backend/tests/conftest.py`

**Pre-condition:** A PostgreSQL database named `health_coach_test` must exist.
```bash
createdb health_coach_test
```

- [ ] **Step 1: Write `tests/conftest.py`**

```python
"""
Shared pytest fixtures for the Health Coach backend test suite.

Sets up a real PostgreSQL test database (health_coach_test), creates all
tables once per session, and truncates all tables after each test so tests
are isolated without relying on mocked DB sessions.
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

# ── Set env vars BEFORE any app imports so config.py reads test values ────────
_TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://localhost/health_coach_test",
)
os.environ["DATABASE_URL"] = _TEST_DB_URL
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-prod")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "a" * 64)  # 32 bytes as hex
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("RESEND_API_KEY", "")
os.environ.setdefault("STRAVA_CLIENT_ID", "")
os.environ.setdefault("STRAVA_CLIENT_SECRET", "")
# ─────────────────────────────────────────────────────────────────────────────

import jwt
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from database.models import Base
from database.engine import get_db
from main import app

_TEST_JWT_SECRET = os.environ["JWT_SECRET_KEY"]

test_engine = create_engine(_TEST_DB_URL)
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


# ── Session-scoped: create tables once, drop after all tests ─────────────────

@pytest.fixture(scope="session", autouse=True)
def _create_test_tables():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


# ── Function-scoped: truncate all tables after every test ─────────────────────

@pytest.fixture(autouse=True)
def _truncate_tables():
    yield
    with test_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"TRUNCATE TABLE {table.name} RESTART IDENTITY CASCADE"))


# ── DB session fixture ────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """Return a SQLAlchemy session bound to the test database."""
    session = _TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


# ── FastAPI TestClient with db override ──────────────────────────────────────

@pytest.fixture
def client(db):
    """TestClient with get_db overridden to use the test session."""
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


# ── JWT helper ────────────────────────────────────────────────────────────────

def make_jwt(
    user_id: uuid.UUID,
    email: str,
    *,
    is_admin: bool = False,
    onboarding_complete: bool = True,
    issued_at: datetime | None = None,
) -> str:
    now = issued_at or datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "user_id": str(user_id),
        "email": email,
        "name": "Test User",
        "picture": "",
        "is_admin": is_admin,
        "onboarding_complete": onboarding_complete,
        "exp": now + timedelta(days=30),
        "iat": now,
    }
    return jwt.encode(payload, _TEST_JWT_SECRET, algorithm="HS256")


# ── User fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def test_user(db):
    """Insert a regular (non-admin) user + profile into the test DB."""
    from database.models import User, UserProfile
    from database.encryption import hmac_lookup

    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email="testuser@example.com",
        name="Test User",
        auth_provider="google",
        is_active=True,
        is_admin=False,
    )
    db.add(user)

    mcp_key = str(uuid.uuid4())
    profile = UserProfile(
        user_id=user_id,
        email="testuser@example.com",
        mcp_api_key=mcp_key,
        mcp_api_key_lookup=hmac_lookup(mcp_key),
        onboarding_complete=True,
        weekly_email_enabled=True,
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    db.refresh(profile)
    return user, profile


@pytest.fixture
def auth_headers(test_user):
    """Authorization headers for the test_user."""
    user, _ = test_user
    token = make_jwt(user.id, user.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_user(db):
    """Insert an admin user + profile into the test DB."""
    from database.models import User, UserProfile
    from database.encryption import hmac_lookup

    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email="admin@example.com",
        name="Admin User",
        auth_provider="google",
        is_active=True,
        is_admin=True,
    )
    db.add(user)

    mcp_key = str(uuid.uuid4())
    profile = UserProfile(
        user_id=user_id,
        email="admin@example.com",
        mcp_api_key=mcp_key,
        mcp_api_key_lookup=hmac_lookup(mcp_key),
        onboarding_complete=True,
        weekly_email_enabled=True,
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    return user, profile


@pytest.fixture
def admin_headers(admin_user):
    """Authorization headers for the admin_user."""
    user, _ = admin_user
    token = make_jwt(user.id, user.email, is_admin=True)
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 2: Create the test database**

```bash
createdb health_coach_test
```

Expected: no error (or "already exists" if it was created earlier)

- [ ] **Step 3: Verify conftest imports cleanly**

```bash
cd backend && source venv/bin/activate && pytest --collect-only 2>&1 | head -20
```

Expected: no import errors; `8 items` found (existing tests)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: add shared test fixtures (conftest.py) with test DB and JWT helpers"
```

---

## Task 5: Unit tests for `database/encryption.py`

These tests exercise the encryption/decryption/HMAC functions in isolation. They require `FIELD_ENCRYPTION_KEY` to be set (conftest.py handles this).

**Files:**
- Create: `backend/tests/test_encryption.py`

- [ ] **Step 1: Write the test file**

```python
"""Unit tests for database/encryption.py."""
import pytest
from database.encryption import encrypt_value, decrypt_value, hmac_lookup, EncryptedString, _PREFIX


class TestEncryptDecrypt:
    def test_encrypt_produces_prefix(self):
        ct = encrypt_value("hello")
        assert ct.startswith(_PREFIX)

    def test_decrypt_round_trips(self):
        plaintext = "my-api-key-12345"
        assert decrypt_value(encrypt_value(plaintext)) == plaintext

    def test_encrypt_is_non_deterministic(self):
        """Each call produces a different ciphertext (random nonce)."""
        ct1 = encrypt_value("same-input")
        ct2 = encrypt_value("same-input")
        assert ct1 != ct2

    def test_decrypt_legacy_plaintext_passthrough(self):
        """Values without the 'enc:v1:' prefix are returned as-is (legacy compat)."""
        assert decrypt_value("plain-old-key") == "plain-old-key"

    def test_encrypt_empty_returns_empty(self):
        assert encrypt_value("") == ""

    def test_decrypt_none_returns_none(self):
        assert decrypt_value(None) is None

    def test_encrypt_does_not_double_encrypt(self):
        ct = encrypt_value("value")
        assert encrypt_value(ct) == ct  # idempotent for already-encrypted values


class TestHmacLookup:
    def test_returns_hex_string(self):
        result = hmac_lookup("test-key")
        assert isinstance(result, str)
        assert len(result) == 64  # SHA-256 hex digest

    def test_deterministic(self):
        assert hmac_lookup("same") == hmac_lookup("same")

    def test_different_inputs_differ(self):
        assert hmac_lookup("key-a") != hmac_lookup("key-b")

    def test_empty_returns_none(self):
        assert hmac_lookup("") is None

    def test_none_returns_none(self):
        assert hmac_lookup(None) is None
```

- [ ] **Step 2: Run the tests**

```bash
cd backend && source venv/bin/activate && pytest tests/test_encryption.py -v
```

Expected: `9 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_encryption.py
git commit -m "test: add unit tests for field-level encryption module"
```

---

## Task 6: Unit tests for `dependencies.py`

Tests `verify_token` (token validation logic) and `get_user_id` (UUID extraction).  
`get_current_user` is tested indirectly via router integration tests in later tasks.

**Files:**
- Create: `backend/tests/test_dependencies.py`

- [ ] **Step 1: Write the test file**

```python
"""Unit tests for FastAPI auth dependencies."""
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

import jwt
import pytest
from fastapi import HTTPException

from dependencies import verify_token, get_user_id

_SECRET = "test-secret-key-do-not-use-in-prod"
_ALG = "HS256"


def _encode(payload: dict) -> str:
    return jwt.encode(payload, _SECRET, algorithm=_ALG)


def _valid_payload(user_id=None):
    uid = user_id or uuid.uuid4()
    now = datetime.now(timezone.utc)
    return {
        "sub": str(uid),
        "user_id": str(uid),
        "email": "test@example.com",
        "is_admin": False,
        "exp": now + timedelta(days=1),
        "iat": now,
    }


class TestVerifyToken:
    def test_valid_token_returns_payload(self):
        payload = _valid_payload()
        token = _encode(payload)
        result = verify_token(f"Bearer {token}")
        assert result["email"] == "test@example.com"

    def test_missing_header_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            verify_token(None)
        assert exc.value.status_code == 401

    def test_non_bearer_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            verify_token("Basic abc123")
        assert exc.value.status_code == 401

    def test_expired_token_raises_401(self):
        payload = _valid_payload()
        payload["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        token = _encode(payload)
        with pytest.raises(HTTPException) as exc:
            verify_token(f"Bearer {token}")
        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail.lower()

    def test_wrong_secret_raises_401(self):
        payload = _valid_payload()
        token = jwt.encode(payload, "wrong-secret", algorithm=_ALG)
        with pytest.raises(HTTPException) as exc:
            verify_token(f"Bearer {token}")
        assert exc.value.status_code == 401

    def test_malformed_token_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            verify_token("Bearer not.a.real.token")
        assert exc.value.status_code == 401


class TestGetUserId:
    def test_returns_uuid_from_valid_payload(self):
        uid = uuid.uuid4()
        payload = {"user_id": str(uid)}
        result = get_user_id(payload)
        assert result == uid

    def test_missing_user_id_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            get_user_id({})
        assert exc.value.status_code == 401

    def test_invalid_uuid_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            get_user_id({"user_id": "not-a-uuid"})
        assert exc.value.status_code == 401
```

- [ ] **Step 2: Run the tests**

```bash
cd backend && source venv/bin/activate && pytest tests/test_dependencies.py -v
```

Expected: `9 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_dependencies.py
git commit -m "test: add unit tests for JWT auth dependencies"
```

---

## Task 7: Unit tests for `services/checkin_service.py`

`upsert_weekly_checkin` has two testable behaviors without touching the DB:
1. `_monday_of_week` date logic
2. Rating validation (raises `ValueError` for out-of-range values)

For the DB-touching path we use a mock session.

**Files:**
- Create: `backend/tests/test_checkin_service.py`

- [ ] **Step 1: Write the test file**

```python
"""Unit tests for services/checkin_service.py."""
import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from services.checkin_service import _monday_of_week, upsert_weekly_checkin


class TestMondayOfWeek:
    def test_monday_returns_itself(self):
        d = date(2026, 4, 6)  # Monday
        assert _monday_of_week(d) == d

    def test_wednesday_returns_previous_monday(self):
        d = date(2026, 4, 8)  # Wednesday
        assert _monday_of_week(d) == date(2026, 4, 6)

    def test_sunday_returns_previous_monday(self):
        d = date(2026, 4, 12)  # Sunday
        assert _monday_of_week(d) == date(2026, 4, 6)

    def test_monday_of_new_year(self):
        d = date(2026, 1, 4)  # Sunday Jan 4, 2026 → Mon Dec 29, 2025
        assert _monday_of_week(d) == date(2025, 12, 29)


class TestUpsertWeeklyCheckinValidation:
    """Test that invalid ratings raise ValueError before any DB call."""

    def _make_db(self):
        db = MagicMock()
        # Simulate no existing check-in found
        db.query.return_value.filter.return_value.first.return_value = None
        # Make db.add/commit/refresh no-ops
        db.add.return_value = None
        db.commit.return_value = None
        mock_row = MagicMock()
        mock_row.id = 1
        db.refresh.side_effect = lambda obj: None
        return db

    def test_valid_ratings_do_not_raise(self):
        db = self._make_db()
        # Should not raise
        upsert_weekly_checkin(
            db, uuid.uuid4(),
            training_adherence=3,
            energy_level=4,
            sleep_quality=2,
            diet_adherence=5,
            stress_level=1,
        )

    def test_rating_zero_raises(self):
        db = self._make_db()
        with pytest.raises(ValueError, match="training_adherence"):
            upsert_weekly_checkin(db, uuid.uuid4(), training_adherence=0)

    def test_rating_six_raises(self):
        db = self._make_db()
        with pytest.raises(ValueError, match="energy_level"):
            upsert_weekly_checkin(db, uuid.uuid4(), energy_level=6)

    def test_rating_negative_raises(self):
        db = self._make_db()
        with pytest.raises(ValueError, match="sleep_quality"):
            upsert_weekly_checkin(db, uuid.uuid4(), sleep_quality=-1)

    def test_none_ratings_are_allowed(self):
        db = self._make_db()
        # All None is valid (partial update)
        upsert_weekly_checkin(db, uuid.uuid4())

    def test_boundary_1_is_valid(self):
        db = self._make_db()
        upsert_weekly_checkin(db, uuid.uuid4(), stress_level=1)

    def test_boundary_5_is_valid(self):
        db = self._make_db()
        upsert_weekly_checkin(db, uuid.uuid4(), diet_adherence=5)
```

- [ ] **Step 2: Run the tests**

```bash
cd backend && source venv/bin/activate && pytest tests/test_checkin_service.py -v
```

Expected: `11 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_checkin_service.py
git commit -m "test: add unit tests for checkin_service validation and date logic"
```

---

## Task 8: Unit tests for `services/supplement_service.py`

Tests the case-insensitive name lookup, idempotency, and the 4-tuple/3-tuple return shapes using a mock session.

**Files:**
- Create: `backend/tests/test_supplement_service.py`

- [ ] **Step 1: Write the test file**

```python
"""Unit tests for services/supplement_service.py."""
import uuid
from datetime import date
from unittest.mock import MagicMock, call

import pytest

from services.supplement_service import (
    log_supplement_by_name,
    log_supplement_by_id,
    get_supplement_status_for_date,
)


def _make_supplement(id_=1, name="Vitamin D", user_id=None):
    s = MagicMock()
    s.id = id_
    s.name = name
    s.is_active = True
    s.user_id = user_id or uuid.uuid4()
    return s


def _make_log(id_=10, supplement_id=1, date_=None):
    log = MagicMock()
    log.id = id_
    log.supplement_id = supplement_id
    log.date = date_ or date.today()
    return log


class TestLogSupplementByName:
    def test_existing_supplement_case_insensitive_match(self):
        db = MagicMock()
        uid = uuid.uuid4()
        supp = _make_supplement(name="Vitamin D", user_id=uid)
        # Query for supplements returns [supp]
        db.query.return_value.filter.return_value.all.return_value = [supp]
        # Query for existing log returns None (not yet logged today)
        db.query.return_value.filter.return_value.first.return_value = None

        log_entry, already_existed, match, created = log_supplement_by_name(
            db, uid, "vitamin d"  # lowercase — should match case-insensitively
        )

        assert match is supp
        assert created is False   # supplement was NOT created
        assert already_existed is False

    def test_supplement_created_if_not_found(self):
        db = MagicMock()
        uid = uuid.uuid4()
        # No existing supplements
        db.query.return_value.filter.return_value.all.return_value = []
        # No existing log
        db.query.return_value.filter.return_value.first.return_value = None

        # db.refresh should populate s.id — simulate by side effect
        created_supp = _make_supplement(name="Magnesium", user_id=uid)
        db.refresh.side_effect = lambda obj: setattr(obj, "id", 99)

        log_entry, already_existed, match, created = log_supplement_by_name(
            db, uid, "Magnesium"
        )

        assert created is True
        assert db.add.called  # supplement was added to session

    def test_already_logged_returns_existing_true(self):
        db = MagicMock()
        uid = uuid.uuid4()
        supp = _make_supplement(user_id=uid)
        existing_log = _make_log()

        # supplements query returns the supplement
        db.query.return_value.filter.return_value.all.return_value = [supp]
        # log query returns existing
        db.query.return_value.filter.return_value.first.return_value = existing_log

        log_entry, already_existed, match, created = log_supplement_by_name(
            db, uid, supp.name
        )

        assert already_existed is True
        assert log_entry is None


class TestLogSupplementById:
    def test_supplement_not_found_returns_none_triple(self):
        db = MagicMock()
        uid = uuid.uuid4()
        db.query.return_value.filter.return_value.first.return_value = None

        result = log_supplement_by_id(db, uid, supplement_id=99)
        assert result == (None, False, None)

    def test_already_logged_returns_existing_true(self):
        db = MagicMock()
        uid = uuid.uuid4()
        supp = _make_supplement()
        existing_log = _make_log()

        # First query (supplement lookup) returns supp
        # Second query (log lookup) returns existing_log
        db.query.return_value.filter.return_value.first.side_effect = [
            supp, existing_log
        ]

        log_entry, already_existed, match = log_supplement_by_id(
            db, uid, supplement_id=1
        )

        assert already_existed is True
        assert log_entry is existing_log

    def test_new_log_created(self):
        db = MagicMock()
        uid = uuid.uuid4()
        supp = _make_supplement()
        new_log = _make_log()

        # First query returns supp, second returns None (not yet logged)
        db.query.return_value.filter.return_value.first.side_effect = [supp, None]
        db.refresh.side_effect = lambda obj: None

        log_entry, already_existed, match = log_supplement_by_id(
            db, uid, supplement_id=1
        )

        assert already_existed is False
        assert match is supp
        assert db.add.called


class TestGetSupplementStatusForDate:
    def test_returns_all_and_taken_ids(self):
        db = MagicMock()
        uid = uuid.uuid4()
        supp_a = _make_supplement(id_=1)
        supp_b = _make_supplement(id_=2)
        log_a = _make_log(supplement_id=1)

        # First query (all supplements) returns [supp_a, supp_b]
        # Second query (supplement logs) returns [log_a]
        db.query.return_value.filter.return_value.all.side_effect = [
            [supp_a, supp_b],
            [log_a],
        ]

        all_supps, taken_ids = get_supplement_status_for_date(db, uid)

        assert len(all_supps) == 2
        assert 1 in taken_ids
        assert 2 not in taken_ids
```

- [ ] **Step 2: Run the tests**

```bash
cd backend && source venv/bin/activate && pytest tests/test_supplement_service.py -v
```

Expected: `7 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_supplement_service.py
git commit -m "test: add unit tests for supplement_service business logic"
```

---

## Task 9: Integration tests for `routers/weight.py`

**Files:**
- Create: `backend/tests/test_router_weight.py`

Uses `client` and `auth_headers` from conftest.py.

- [ ] **Step 1: Write the test file**

```python
"""Integration tests for POST/GET/DELETE /api/weight."""
from datetime import date, timedelta

import pytest


class TestLogWeight:
    def test_create_weight_log(self, client, auth_headers):
        resp = client.post(
            "/api/weight/log",
            json={"date": "2026-04-01", "weight_lbs": 175.5},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["weight_lbs"] == 175.5
        assert data["date"] == "2026-04-01"

    def test_upsert_existing_date(self, client, auth_headers):
        client.post(
            "/api/weight/log",
            json={"date": "2026-04-01", "weight_lbs": 175.0},
            headers=auth_headers,
        )
        resp = client.post(
            "/api/weight/log",
            json={"date": "2026-04-01", "weight_lbs": 174.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["weight_lbs"] == 174.0

    def test_log_with_body_fat(self, client, auth_headers):
        resp = client.post(
            "/api/weight/log",
            json={"date": "2026-04-02", "weight_lbs": 175.0, "body_fat_pct": 20.5},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["body_fat_pct"] == 20.5

    def test_requires_auth(self, client):
        resp = client.post(
            "/api/weight/log",
            json={"date": "2026-04-01", "weight_lbs": 175.0},
        )
        assert resp.status_code == 401


class TestGetLatestWeight:
    def test_no_logs_returns_none(self, client, auth_headers):
        resp = client.get("/api/weight/latest", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() is None

    def test_returns_most_recent(self, client, auth_headers):
        client.post("/api/weight/log", json={"date": "2026-03-01", "weight_lbs": 180.0}, headers=auth_headers)
        client.post("/api/weight/log", json={"date": "2026-04-01", "weight_lbs": 175.0}, headers=auth_headers)
        resp = client.get("/api/weight/latest", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["weight_lbs"] == 175.0


class TestWeightHistory:
    def test_empty_history(self, client, auth_headers):
        resp = client.get("/api/weight/history", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_all_logs_sorted(self, client, auth_headers):
        client.post("/api/weight/log", json={"date": "2026-04-02", "weight_lbs": 174.0}, headers=auth_headers)
        client.post("/api/weight/log", json={"date": "2026-04-01", "weight_lbs": 175.0}, headers=auth_headers)
        resp = client.get("/api/weight/history", headers=auth_headers)
        assert resp.status_code == 200
        dates = [r["date"] for r in resp.json()]
        assert dates == sorted(dates)

    def test_date_range_filter(self, client, auth_headers):
        client.post("/api/weight/log", json={"date": "2026-03-01", "weight_lbs": 180.0}, headers=auth_headers)
        client.post("/api/weight/log", json={"date": "2026-04-01", "weight_lbs": 175.0}, headers=auth_headers)
        resp = client.get(
            "/api/weight/history",
            params={"start": "2026-04-01", "end": "2026-04-30"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["weight_lbs"] == 175.0


class TestDeleteWeight:
    def test_delete_existing(self, client, auth_headers):
        create = client.post(
            "/api/weight/log",
            json={"date": "2026-04-01", "weight_lbs": 175.0},
            headers=auth_headers,
        )
        entry_id = create.json()["id"]
        resp = client.delete(f"/api/weight/{entry_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_delete_nonexistent_returns_404(self, client, auth_headers):
        resp = client.delete("/api/weight/9999", headers=auth_headers)
        assert resp.status_code == 404

    def test_cannot_delete_another_users_log(self, client, auth_headers, db, admin_user):
        # admin_user's weight log
        from database.models import WeightLog
        au, _ = admin_user
        wl = WeightLog(user_id=au.id, date="2026-04-01", weight_lbs=200.0)
        db.add(wl)
        db.commit()
        db.refresh(wl)

        resp = client.delete(f"/api/weight/{wl.id}", headers=auth_headers)
        assert resp.status_code == 404  # not visible to test_user
```

- [ ] **Step 2: Run the tests**

```bash
cd backend && source venv/bin/activate && pytest tests/test_router_weight.py -v
```

Expected: `10 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_router_weight.py
git commit -m "test: add integration tests for weight router"
```

---

## Task 10: Integration tests for `routers/body_composition.py`

**Files:**
- Create: `backend/tests/test_router_body_composition.py`

- [ ] **Step 1: Write the test file**

```python
"""Integration tests for /api/body-composition endpoints."""
import pytest


class TestLogBodyComposition:
    def test_log_body_comp_basic(self, client, auth_headers):
        resp = client.post(
            "/api/body-composition/log",
            json={"date": "2026-04-01", "body_fat_pct": 20.5},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["body_fat_pct"] == 20.5
        assert data["date"] == "2026-04-01"

    def test_lean_fat_derived_from_weight(self, client, auth_headers):
        # Log a weight first so the router can derive lean/fat mass
        client.post(
            "/api/weight/log",
            json={"date": "2026-04-01", "weight_lbs": 180.0},
            headers=auth_headers,
        )
        resp = client.post(
            "/api/body-composition/log",
            json={"date": "2026-04-01", "body_fat_pct": 20.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # fat_mass = 180 * 0.20 = 36.0 lbs
        assert data["fat_mass_lbs"] == pytest.approx(36.0, abs=0.5)
        # lean_mass = 180 - 36 = 144.0 lbs
        assert data["lean_mass_lbs"] == pytest.approx(144.0, abs=0.5)

    def test_requires_auth(self, client):
        resp = client.post(
            "/api/body-composition/log",
            json={"date": "2026-04-01", "body_fat_pct": 20.0},
        )
        assert resp.status_code == 401


class TestGetBodyComposition:
    def test_latest_returns_none_when_empty(self, client, auth_headers):
        resp = client.get("/api/body-composition/latest", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() is None

    def test_latest_returns_most_recent(self, client, auth_headers):
        client.post("/api/body-composition/log", json={"date": "2026-03-01", "body_fat_pct": 22.0}, headers=auth_headers)
        client.post("/api/body-composition/log", json={"date": "2026-04-01", "body_fat_pct": 20.0}, headers=auth_headers)
        resp = client.get("/api/body-composition/latest", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["body_fat_pct"] == 20.0

    def test_history_returns_all(self, client, auth_headers):
        client.post("/api/body-composition/log", json={"date": "2026-04-01", "body_fat_pct": 20.0}, headers=auth_headers)
        client.post("/api/body-composition/log", json={"date": "2026-04-02", "body_fat_pct": 19.5}, headers=auth_headers)
        resp = client.get("/api/body-composition/history", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2
```

- [ ] **Step 2: Run the tests**

```bash
cd backend && source venv/bin/activate && pytest tests/test_router_body_composition.py -v
```

Expected: `6 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_router_body_composition.py
git commit -m "test: add integration tests for body composition router"
```

---

## Task 11: Integration tests for `routers/supplements.py`

**Files:**
- Create: `backend/tests/test_router_supplements.py`

- [ ] **Step 1: Write the test file**

```python
"""Integration tests for /api/supplements endpoints."""
import pytest


def _create_supplement(client, auth_headers, name="Vitamin D", dosage="1000 IU"):
    resp = client.post(
        "/api/supplements",
        json={"name": name, "dosage": dosage},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()


class TestSupplementCRUD:
    def test_create_supplement(self, client, auth_headers):
        resp = client.post(
            "/api/supplements",
            json={"name": "Magnesium", "dosage": "400mg"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Magnesium"
        assert data["dosage"] == "400mg"
        assert data["is_active"] is True

    def test_list_supplements(self, client, auth_headers):
        _create_supplement(client, auth_headers, "Vitamin D")
        _create_supplement(client, auth_headers, "Omega-3")
        resp = client.get("/api/supplements", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_update_supplement(self, client, auth_headers):
        s = _create_supplement(client, auth_headers, "Zinc", "25mg")
        resp = client.patch(
            f"/api/supplements/{s['id']}",
            json={"dosage": "50mg"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["dosage"] == "50mg"

    def test_update_nonexistent_returns_404(self, client, auth_headers):
        resp = client.patch(
            "/api/supplements/9999",
            json={"dosage": "50mg"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_soft_delete_supplement(self, client, auth_headers):
        s = _create_supplement(client, auth_headers, "Creatine")
        resp = client.delete(f"/api/supplements/{s['id']}", headers=auth_headers)
        assert resp.status_code == 200

        # Should not appear in list after delete
        list_resp = client.get("/api/supplements", headers=auth_headers)
        ids = [x["id"] for x in list_resp.json()]
        assert s["id"] not in ids

    def test_requires_auth(self, client):
        resp = client.get("/api/supplements")
        assert resp.status_code == 401


class TestSupplementLogging:
    def test_log_supplement_taken(self, client, auth_headers):
        s = _create_supplement(client, auth_headers, "B12")
        resp = client.post(
            "/api/supplements/log",
            json={"supplement_id": s["id"], "date": "2026-04-01"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["supplement_id"] == s["id"]
        assert data["date"] == "2026-04-01"

    def test_log_nonexistent_supplement_returns_404(self, client, auth_headers):
        resp = client.post(
            "/api/supplements/log",
            json={"supplement_id": 9999},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_get_supplement_log_for_date(self, client, auth_headers):
        s = _create_supplement(client, auth_headers, "Iron")
        client.post(
            "/api/supplements/log",
            json={"supplement_id": s["id"], "date": "2026-04-01"},
            headers=auth_headers,
        )
        resp = client.get(
            "/api/supplements/log",
            params={"log_date": "2026-04-01"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_unlog_supplement(self, client, auth_headers):
        s = _create_supplement(client, auth_headers, "CoQ10")
        log_resp = client.post(
            "/api/supplements/log",
            json={"supplement_id": s["id"]},
            headers=auth_headers,
        )
        log_id = log_resp.json()["id"]

        del_resp = client.delete(f"/api/supplements/log/{log_id}", headers=auth_headers)
        assert del_resp.status_code == 200
```

- [ ] **Step 2: Run the tests**

```bash
cd backend && source venv/bin/activate && pytest tests/test_router_supplements.py -v
```

Expected: `9 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_router_supplements.py
git commit -m "test: add integration tests for supplements router"
```

---

## Task 12: Integration tests for `routers/checkin.py`

**Files:**
- Create: `backend/tests/test_router_checkin.py`

- [ ] **Step 1: Write the test file**

```python
"""Integration tests for /api/checkin endpoints."""
import pytest


class TestUpsertCheckin:
    def test_create_checkin(self, client, auth_headers):
        resp = client.post(
            "/api/checkin",
            json={
                "training_adherence": 4,
                "energy_level": 3,
                "sleep_quality": 4,
                "diet_adherence": 5,
                "stress_level": 2,
                "notes": "Good week overall",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["training_adherence"] == 4
        assert data["notes"] == "Good week overall"

    def test_upsert_same_week(self, client, auth_headers):
        client.post("/api/checkin", json={"training_adherence": 3}, headers=auth_headers)
        resp = client.post("/api/checkin", json={"training_adherence": 5}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["training_adherence"] == 5

    def test_invalid_rating_returns_422(self, client, auth_headers):
        resp = client.post(
            "/api/checkin",
            json={"training_adherence": 6},  # invalid: > 5
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_rating_zero_returns_422(self, client, auth_headers):
        resp = client.post(
            "/api/checkin",
            json={"energy_level": 0},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_partial_checkin_allowed(self, client, auth_headers):
        resp = client.post(
            "/api/checkin",
            json={"sleep_quality": 3},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sleep_quality"] == 3
        assert data["training_adherence"] is None

    def test_requires_auth(self, client):
        resp = client.post("/api/checkin", json={})
        assert resp.status_code == 401


class TestGetCheckin:
    def test_latest_returns_none_when_empty(self, client, auth_headers):
        resp = client.get("/api/checkin/latest", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() is None

    def test_latest_returns_most_recent(self, client, auth_headers):
        client.post(
            "/api/checkin",
            json={"week_start": "2026-03-30", "training_adherence": 3},
            headers=auth_headers,
        )
        client.post(
            "/api/checkin",
            json={"week_start": "2026-04-06", "training_adherence": 5},
            headers=auth_headers,
        )
        resp = client.get("/api/checkin/latest", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["training_adherence"] == 5

    def test_history_returns_all(self, client, auth_headers):
        for week in ["2026-03-23", "2026-03-30", "2026-04-06"]:
            client.post(
                "/api/checkin",
                json={"week_start": week, "energy_level": 3},
                headers=auth_headers,
            )
        resp = client.get("/api/checkin/history", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_history_limit(self, client, auth_headers):
        for i in range(5):
            week = f"2026-0{i+1}-06" if i < 9 else f"2026-{i+1:02d}-06"
            client.post(
                "/api/checkin",
                json={"week_start": f"2026-03-{(i+1)*7:02d}" if (i+1)*7 <= 28 else "2026-04-06", "energy_level": 3},
                headers=auth_headers,
            )
        resp = client.get("/api/checkin/history", params={"limit": 2}, headers=auth_headers)
        assert len(resp.json()) <= 2
```

- [ ] **Step 2: Run the tests**

```bash
cd backend && source venv/bin/activate && pytest tests/test_router_checkin.py -v
```

Expected: `10 passed` (or close — some dates may overlap in upsert)

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_router_checkin.py
git commit -m "test: add integration tests for checkin router"
```

---

## Task 13: Integration tests for `routers/auth.py` (non-OAuth paths)

Tests `validate_invite`, `get_me`, `logout`, and invite code CRUD. Google OAuth is excluded (requires external HTTP calls).

**Files:**
- Create: `backend/tests/test_router_auth.py`

- [ ] **Step 1: Write the test file**

```python
"""Integration tests for /api/auth endpoints (non-OAuth paths)."""
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from tests.conftest import make_jwt


class TestValidateInvite:
    def test_valid_code_returns_true(self, client, db, admin_user):
        from database.models import InviteCode
        admin, _ = admin_user
        invite = InviteCode(
            id=uuid.uuid4(),
            code="TESTCODE",
            created_by=admin.id,
            max_uses=5,
            use_count=0,
        )
        db.add(invite)
        db.commit()

        resp = client.get("/api/auth/validate-invite", params={"code": "TESTCODE"})
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_invalid_code_returns_false(self, client):
        resp = client.get("/api/auth/validate-invite", params={"code": "DOESNOTEXIST"})
        assert resp.status_code == 200
        assert resp.json()["valid"] is False

    def test_exhausted_code_returns_false(self, client, db, admin_user):
        from database.models import InviteCode
        admin, _ = admin_user
        invite = InviteCode(
            id=uuid.uuid4(),
            code="USED123",
            created_by=admin.id,
            max_uses=1,
            use_count=1,
        )
        db.add(invite)
        db.commit()

        resp = client.get("/api/auth/validate-invite", params={"code": "USED123"})
        assert resp.json()["valid"] is False

    def test_expired_code_returns_false(self, client, db, admin_user):
        from database.models import InviteCode
        admin, _ = admin_user
        invite = InviteCode(
            id=uuid.uuid4(),
            code="EXPIRED",
            created_by=admin.id,
            max_uses=5,
            use_count=0,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db.add(invite)
        db.commit()

        resp = client.get("/api/auth/validate-invite", params={"code": "EXPIRED"})
        assert resp.json()["valid"] is False


class TestGetMe:
    def test_returns_user_info(self, client, auth_headers, test_user):
        user, _ = test_user
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == user.email
        assert data["is_admin"] is False

    def test_requires_auth(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


class TestLogout:
    def test_logout_sets_last_logout_at(self, client, auth_headers, test_user, db):
        user, _ = test_user
        resp = client.post("/api/auth/logout", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        db.refresh(user)
        assert user.last_logout_at is not None

    def test_requires_auth(self, client):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 401


class TestInviteCodeAdmin:
    def test_admin_can_create_invite_code(self, client, admin_headers):
        resp = client.post(
            "/api/auth/invite-codes",
            json={"code": "MYCODE", "max_uses": 3},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == "MYCODE"
        assert data["max_uses"] == 3
        assert data["use_count"] == 0

    def test_auto_generated_code_when_empty(self, client, admin_headers):
        resp = client.post(
            "/api/auth/invite-codes",
            json={"max_uses": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["code"]  # non-empty

    def test_duplicate_code_returns_409(self, client, admin_headers):
        client.post("/api/auth/invite-codes", json={"code": "DUP"}, headers=admin_headers)
        resp = client.post("/api/auth/invite-codes", json={"code": "DUP"}, headers=admin_headers)
        assert resp.status_code == 409

    def test_non_admin_cannot_create_invite(self, client, auth_headers):
        resp = client.post(
            "/api/auth/invite-codes",
            json={"code": "NOPE"},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_admin_can_list_invite_codes(self, client, admin_headers):
        client.post("/api/auth/invite-codes", json={"code": "LIST1"}, headers=admin_headers)
        client.post("/api/auth/invite-codes", json={"code": "LIST2"}, headers=admin_headers)
        resp = client.get("/api/auth/invite-codes", headers=admin_headers)
        assert resp.status_code == 200
        codes = [x["code"] for x in resp.json()]
        assert "LIST1" in codes
        assert "LIST2" in codes
```

- [ ] **Step 2: Run the tests**

```bash
cd backend && source venv/bin/activate && pytest tests/test_router_auth.py -v
```

Expected: `13 passed`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_router_auth.py
git commit -m "test: add integration tests for auth router (validate invite, me, logout, invite codes)"
```

---

## Task 14: Integration tests for `routers/admin.py`

**Files:**
- Create: `backend/tests/test_router_admin.py`

- [ ] **Step 1: Write the test file**

```python
"""Integration tests for /api/admin endpoints."""
import uuid
import pytest


class TestListUsers:
    def test_admin_can_list_users(self, client, admin_headers, test_user):
        resp = client.get("/api/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 2  # admin_user + test_user

    def test_non_admin_cannot_list_users(self, client, auth_headers):
        resp = client.get("/api/admin/users", headers=auth_headers)
        assert resp.status_code == 403

    def test_requires_auth(self, client):
        resp = client.get("/api/admin/users")
        assert resp.status_code == 401


class TestUpdateUser:
    def test_admin_can_deactivate_user(self, client, admin_headers, test_user, db):
        user, _ = test_user
        resp = client.patch(
            f"/api/admin/users/{user.id}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        db.refresh(user)
        assert user.is_active is False

    def test_admin_can_promote_user(self, client, admin_headers, test_user, db):
        user, _ = test_user
        resp = client.patch(
            f"/api/admin/users/{user.id}",
            json={"is_admin": True},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True

    def test_admin_cannot_modify_self(self, client, admin_headers, admin_user):
        admin, _ = admin_user
        resp = client.patch(
            f"/api/admin/users/{admin.id}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert resp.status_code == 400

    def test_update_nonexistent_user_returns_404(self, client, admin_headers):
        resp = client.patch(
            f"/api/admin/users/{uuid.uuid4()}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_non_admin_cannot_update_user(self, client, auth_headers, test_user):
        user, _ = test_user
        resp = client.patch(
            f"/api/admin/users/{user.id}",
            json={"is_active": False},
            headers=auth_headers,
        )
        assert resp.status_code == 403


class TestAuditLog:
    def test_admin_can_view_audit_log(self, client, admin_headers):
        resp = client.get("/api/admin/audit-log", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_non_admin_cannot_view_audit_log(self, client, auth_headers):
        resp = client.get("/api/admin/audit-log", headers=auth_headers)
        assert resp.status_code == 403


class TestStats:
    def test_admin_can_view_stats(self, client, admin_headers, test_user):
        resp = client.get("/api/admin/stats", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_users" in data
        assert data["total_users"] >= 2  # admin + test_user
        assert "active_users" in data

    def test_non_admin_cannot_view_stats(self, client, auth_headers):
        resp = client.get("/api/admin/stats", headers=auth_headers)
        assert resp.status_code == 403
```

- [ ] **Step 2: Run the tests**

```bash
cd backend && source venv/bin/activate && pytest tests/test_router_admin.py -v
```

Expected: `10 passed`

- [ ] **Step 3: Run the full test suite to confirm nothing regressed**

```bash
cd backend && source venv/bin/activate && pytest tests/ -v
```

Expected: All tests pass (>60 tests total)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_router_admin.py
git commit -m "test: add integration tests for admin router"
```

---

## Self-Review

### Spec coverage

| Requirement | Covered by |
|---|---|
| Backend refactoring | Tasks 2, 3 |
| Unit tests — encryption | Task 5 |
| Unit tests — auth dependencies | Task 6 |
| Unit tests — checkin service | Task 7 |
| Unit tests — supplement service | Task 8 |
| Integration tests — weight router | Task 9 |
| Integration tests — body composition router | Task 10 |
| Integration tests — supplements router | Task 11 |
| Integration tests — checkin router | Task 12 |
| Integration tests — auth router | Task 13 |
| Integration tests — admin router | Task 14 |
| Test infrastructure | Tasks 1, 4 |

**Excluded (too complex / external dependencies):**
- Claude AI service tests — would require mocking the Anthropic API or spending real tokens
- Strava, Hevy, Garmin sync tests — require external API credentials
- Telegram webhook tests — require bot token and webhook setup
- MCP server tests — integration with SSE transport is complex
- Google OAuth callback — requires external HTTP to Google

### Placeholder scan
No TBD, no "add appropriate error handling", no "similar to Task N" without code.

### Type consistency
- `make_jwt` returns `str` (Task 4) — used with `f"Bearer {token}"` in all auth_headers (Tasks 9-14) ✓
- `test_user` returns `(User, UserProfile)` tuple — destructured consistently as `user, _` and `user, profile` ✓  
- `_create_supplement` helper in Task 11 returns `dict` — accessed via `["id"]` consistently ✓
- `_make_supplement` / `_make_log` in Task 8 return `MagicMock` with `.id` attribute ✓
