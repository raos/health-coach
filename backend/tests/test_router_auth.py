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

    def test_no_auth_required(self, client):
        """validate-invite is public."""
        resp = client.get("/api/auth/validate-invite", params={"code": "ANYTHING"})
        assert resp.status_code == 200  # not 401


class TestGetMe:
    def test_returns_user_info(self, client, auth_headers, test_user):
        user, _ = test_user
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == user.email
        assert data["is_admin"] is False
        assert data["onboarding_complete"] is True

    def test_requires_auth(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


class TestLogout:
    def test_logout_returns_ok(self, client, auth_headers):
        resp = client.post("/api/auth/logout", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_logout_sets_last_logout_at(self, client, auth_headers, test_user, db):
        user, _ = test_user
        client.post("/api/auth/logout", headers=auth_headers)
        db.refresh(user)
        assert user.last_logout_at is not None

    def test_requires_auth(self, client):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 401


class TestRefreshToken:
    def test_returns_new_token(self, client, auth_headers, test_user):
        resp = client.post("/api/auth/refresh-token", headers=auth_headers)
        assert resp.status_code == 200
        assert "token" in resp.json()
        assert isinstance(resp.json()["token"], str)

    def test_requires_auth(self, client):
        resp = client.post("/api/auth/refresh-token")
        assert resp.status_code == 401

    def test_inactive_user_gets_403(self, client, db, test_user):
        """A user whose is_active=False cannot refresh their token."""
        user, _ = test_user
        user.is_active = False
        db.commit()

        token = make_jwt(user.id, user.email)
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.post("/api/auth/refresh-token", headers=headers)
        assert resp.status_code == 403


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
        assert data["uses_remaining"] == 3

    def test_code_is_uppercased(self, client, admin_headers):
        resp = client.post(
            "/api/auth/invite-codes",
            json={"code": "lowercase"},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == "LOWERCASE"

    def test_auto_generated_code_when_empty(self, client, admin_headers):
        resp = client.post(
            "/api/auth/invite-codes",
            json={"max_uses": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        code = resp.json()["code"]
        assert code  # non-empty
        assert len(code) > 0

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

    def test_non_admin_cannot_list_invites(self, client, auth_headers):
        resp = client.get("/api/auth/invite-codes", headers=auth_headers)
        assert resp.status_code == 403

    def test_invite_code_with_expiry(self, client, admin_headers):
        """Creating a code with expires_days sets expires_at."""
        resp = client.post(
            "/api/auth/invite-codes",
            json={"code": "EXPIRES7", "max_uses": 2, "expires_days": 7},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["expires_at"] is not None

    def test_invite_code_no_expiry_by_default(self, client, admin_headers):
        """expires_days=0 means no expiry (expires_at is None)."""
        resp = client.post(
            "/api/auth/invite-codes",
            json={"code": "NOEXP", "max_uses": 1, "expires_days": 0},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["expires_at"] is None

    def test_requires_auth_to_create(self, client):
        resp = client.post("/api/auth/invite-codes", json={"code": "ANON"})
        assert resp.status_code == 401

    def test_requires_auth_to_list(self, client):
        resp = client.get("/api/auth/invite-codes")
        assert resp.status_code == 401
