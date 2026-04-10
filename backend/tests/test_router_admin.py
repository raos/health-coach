"""Integration tests for /api/admin endpoints."""
import uuid
import pytest


class TestListUsers:
    def test_admin_can_list_users(self, client, admin_headers, test_user):
        resp = client.get("/api/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # admin_user + test_user

    def test_response_contains_expected_fields(self, client, admin_headers, test_user):
        resp = client.get("/api/admin/users", headers=admin_headers)
        assert resp.status_code == 200
        user_data = resp.json()[0]
        expected_fields = ["id", "email", "name", "is_active", "is_admin", "onboarding_complete"]
        for field in expected_fields:
            assert field in user_data, f"Missing field: {field}"

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

    def test_admin_can_promote_user_to_admin(self, client, admin_headers, test_user, db):
        user, _ = test_user
        resp = client.patch(
            f"/api/admin/users/{user.id}",
            json={"is_admin": True},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True

        db.refresh(user)
        assert user.is_admin is True

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

    def test_requires_auth(self, client, test_user):
        user, _ = test_user
        resp = client.patch(f"/api/admin/users/{user.id}", json={"is_active": False})
        assert resp.status_code == 401


class TestAuditLog:
    def test_admin_can_view_audit_log(self, client, admin_headers):
        resp = client.get("/api/admin/audit-log", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_audit_log_has_expected_fields(self, client, admin_headers):
        resp = client.get("/api/admin/audit-log", headers=admin_headers)
        assert resp.status_code == 200
        # May be empty, but if entries exist they should have these fields
        data = resp.json()
        if data:
            entry = data[0]
            assert "action" in entry
            assert "created_at" in entry

    def test_non_admin_cannot_view_audit_log(self, client, auth_headers):
        resp = client.get("/api/admin/audit-log", headers=auth_headers)
        assert resp.status_code == 403

    def test_requires_auth(self, client):
        resp = client.get("/api/admin/audit-log")
        assert resp.status_code == 401


class TestStats:
    def test_admin_can_view_stats(self, client, admin_headers, test_user):
        resp = client.get("/api/admin/stats", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_users" in data
        assert "active_users" in data
        assert "total_meal_plans" in data
        assert data["total_users"] >= 2  # admin + test_user

    def test_non_admin_cannot_view_stats(self, client, auth_headers):
        resp = client.get("/api/admin/stats", headers=auth_headers)
        assert resp.status_code == 403

    def test_requires_auth(self, client):
        resp = client.get("/api/admin/stats")
        assert resp.status_code == 401
