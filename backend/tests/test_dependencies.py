"""Unit tests for FastAPI auth dependencies."""
import os
import uuid
from datetime import datetime, timezone, timedelta

# Set env vars BEFORE any app imports
os.environ.setdefault("DATABASE_URL", "postgresql://localhost/health_coach_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-do-not-use-in-prod")
os.environ.setdefault("FIELD_ENCRYPTION_KEY", "a" * 64)

import jwt
import pytest
from fastapi import HTTPException

from dependencies import verify_token, get_user_id

_SECRET = "test-secret-key-do-not-use-in-prod"
_ALG = "HS256"


def _encode(payload: dict) -> str:
    """Encode a JWT payload."""
    return jwt.encode(payload, _SECRET, algorithm=_ALG)


def _valid_payload(user_id=None):
    """Return a valid JWT payload."""
    uid = user_id or uuid.uuid4()
    now = datetime.now(timezone.utc)
    return {
        "sub": str(uid),
        "user_id": str(uid),
        "email": "test@example.com",
        "name": "Test User",
        "picture": "",
        "is_admin": False,
        "onboarding_complete": True,
        "exp": now + timedelta(days=1),
        "iat": now,
    }


class TestVerifyToken:
    """Tests for verify_token() dependency."""

    def test_valid_token_returns_payload(self):
        """Valid Bearer token should decode and return payload."""
        payload = _valid_payload()
        token = _encode(payload)
        result = verify_token(f"Bearer {token}")
        assert result["email"] == "test@example.com"
        assert result["is_admin"] is False

    def test_missing_authorization_header_raises_401(self):
        """Missing Authorization header should raise 401."""
        with pytest.raises(HTTPException) as exc:
            verify_token(None)
        assert exc.value.status_code == 401
        assert "authenticated" in exc.value.detail.lower()

    def test_empty_authorization_header_raises_401(self):
        """Empty Authorization header should raise 401."""
        with pytest.raises(HTTPException) as exc:
            verify_token("")
        assert exc.value.status_code == 401

    def test_non_bearer_scheme_raises_401(self):
        """Non-Bearer authorization should raise 401."""
        with pytest.raises(HTTPException) as exc:
            verify_token("Basic abc123")
        assert exc.value.status_code == 401

    def test_bearer_without_token_raises_401(self):
        """Bearer with no token should raise 401."""
        with pytest.raises(HTTPException) as exc:
            verify_token("Bearer ")
        assert exc.value.status_code == 401

    def test_expired_token_raises_401(self):
        """Expired JWT should raise 401."""
        payload = _valid_payload()
        payload["exp"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        token = _encode(payload)
        with pytest.raises(HTTPException) as exc:
            verify_token(f"Bearer {token}")
        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail.lower()

    def test_wrong_secret_raises_401(self):
        """Token signed with wrong secret should raise 401."""
        payload = _valid_payload()
        token = jwt.encode(payload, "wrong-secret", algorithm=_ALG)
        with pytest.raises(HTTPException) as exc:
            verify_token(f"Bearer {token}")
        assert exc.value.status_code == 401

    def test_malformed_token_raises_401(self):
        """Malformed token should raise 401."""
        with pytest.raises(HTTPException) as exc:
            verify_token("Bearer not.a.real.token")
        assert exc.value.status_code == 401

    def test_payload_contains_expected_fields(self):
        """Decoded payload should contain expected JWT claims."""
        uid = uuid.uuid4()
        payload = _valid_payload(uid)
        token = _encode(payload)
        result = verify_token(f"Bearer {token}")
        assert result["user_id"] == str(uid)
        assert result["sub"] == str(uid)
        assert result["is_admin"] is False
        assert result["email"] == "test@example.com"

    def test_bearer_case_sensitive(self):
        """Bearer scheme should be case-sensitive (must be 'Bearer')."""
        payload = _valid_payload()
        token = _encode(payload)
        # Lowercase 'bearer' should fail
        with pytest.raises(HTTPException) as exc:
            verify_token(f"bearer {token}")
        assert exc.value.status_code == 401

    def test_admin_flag_preserved_in_payload(self):
        """Admin flag should be preserved in decoded payload."""
        payload = _valid_payload()
        payload["is_admin"] = True
        token = _encode(payload)
        result = verify_token(f"Bearer {token}")
        assert result["is_admin"] is True


class TestGetUserId:
    """Tests for get_user_id() dependency."""

    def test_returns_uuid_from_valid_payload(self):
        """Valid user_id in payload should return UUID object."""
        uid = uuid.uuid4()
        payload = {"user_id": str(uid)}
        result = get_user_id(payload)
        assert result == uid
        assert isinstance(result, uuid.UUID)

    def test_missing_user_id_raises_401(self):
        """Missing user_id claim should raise 401."""
        with pytest.raises(HTTPException) as exc:
            get_user_id({})
        assert exc.value.status_code == 401
        assert "user_id" in exc.value.detail.lower()

    def test_none_user_id_raises_401(self):
        """None user_id should raise 401."""
        with pytest.raises(HTTPException) as exc:
            get_user_id({"user_id": None})
        assert exc.value.status_code == 401

    def test_empty_string_user_id_raises_401(self):
        """Empty string user_id should raise 401."""
        with pytest.raises(HTTPException) as exc:
            get_user_id({"user_id": ""})
        assert exc.value.status_code == 401

    def test_invalid_uuid_format_raises_401(self):
        """Invalid UUID string should raise 401."""
        with pytest.raises(HTTPException) as exc:
            get_user_id({"user_id": "not-a-uuid"})
        assert exc.value.status_code == 401
        assert "invalid" in exc.value.detail.lower()

    def test_partial_uuid_raises_401(self):
        """Incomplete UUID string should raise 401."""
        with pytest.raises(HTTPException) as exc:
            get_user_id({"user_id": "12345678-1234-1234"})
        assert exc.value.status_code == 401

    def test_integer_user_id_raises_401(self):
        """Integer user_id (not string) should raise 401."""
        with pytest.raises(HTTPException) as exc:
            get_user_id({"user_id": 12345})
        assert exc.value.status_code == 401

    def test_uuid_object_in_payload_raises_401(self):
        """UUID object (not string) should raise 401."""
        uid = uuid.uuid4()
        with pytest.raises(HTTPException) as exc:
            get_user_id({"user_id": uid})
        assert exc.value.status_code == 401

    def test_multiple_uuid_formats(self):
        """Various valid UUID formats should be accepted."""
        # Standard format
        uid1 = uuid.uuid4()
        result1 = get_user_id({"user_id": str(uid1)})
        assert result1 == uid1

        # Uppercase
        uid2 = uuid.uuid4()
        result2 = get_user_id({"user_id": str(uid2).upper()})
        assert result2 == uid2


class TestIntegration:
    """Integration tests combining verify_token and get_user_id."""

    def test_verify_then_get_user_id_flow(self):
        """Typical flow: verify token, then extract user_id."""
        uid = uuid.uuid4()
        payload = _valid_payload(uid)
        token = _encode(payload)

        # Step 1: verify token
        verified_payload = verify_token(f"Bearer {token}")

        # Step 2: get user_id from verified payload
        result_uid = get_user_id(verified_payload)
        assert result_uid == uid

    def test_token_with_all_required_fields(self):
        """Complete token should work end-to-end."""
        uid = uuid.uuid4()
        payload = {
            "sub": str(uid),
            "user_id": str(uid),
            "email": "user@example.com",
            "name": "Full Name",
            "picture": "https://example.com/pic.jpg",
            "is_admin": False,
            "onboarding_complete": True,
            "exp": datetime.now(timezone.utc) + timedelta(days=30),
            "iat": datetime.now(timezone.utc),
        }
        token = _encode(payload)

        # Verify
        verified = verify_token(f"Bearer {token}")
        assert verified["email"] == "user@example.com"

        # Extract user_id
        extracted_uid = get_user_id(verified)
        assert extracted_uid == uid
