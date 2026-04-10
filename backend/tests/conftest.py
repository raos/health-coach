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
