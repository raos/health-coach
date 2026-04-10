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

    def test_upsert_same_week_updates_values(self, client, auth_headers):
        # Use explicit week_start to avoid depending on current date
        client.post("/api/checkin", json={"week_start": "2026-04-06", "training_adherence": 3}, headers=auth_headers)
        resp = client.post("/api/checkin", json={"week_start": "2026-04-06", "training_adherence": 5}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["training_adherence"] == 5

    def test_invalid_rating_too_high_returns_422(self, client, auth_headers):
        resp = client.post(
            "/api/checkin",
            json={"training_adherence": 6},
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
            json={"week_start": "2026-04-06", "sleep_quality": 3},
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
        client.post("/api/checkin", json={"week_start": "2026-03-30", "training_adherence": 3}, headers=auth_headers)
        client.post("/api/checkin", json={"week_start": "2026-04-06", "training_adherence": 5}, headers=auth_headers)
        resp = client.get("/api/checkin/latest", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["training_adherence"] == 5
        assert resp.json()["week_start"] == "2026-04-06"

    def test_history_returns_all_descending(self, client, auth_headers):
        client.post("/api/checkin", json={"week_start": "2026-03-23", "energy_level": 3}, headers=auth_headers)
        client.post("/api/checkin", json={"week_start": "2026-03-30", "energy_level": 4}, headers=auth_headers)
        client.post("/api/checkin", json={"week_start": "2026-04-06", "energy_level": 5}, headers=auth_headers)
        resp = client.get("/api/checkin/history", headers=auth_headers)
        assert resp.status_code == 200
        weeks = [r["week_start"] for r in resp.json()]
        assert weeks == sorted(weeks, reverse=True)

    def test_history_limit(self, client, auth_headers):
        client.post("/api/checkin", json={"week_start": "2026-03-23", "energy_level": 3}, headers=auth_headers)
        client.post("/api/checkin", json={"week_start": "2026-03-30", "energy_level": 4}, headers=auth_headers)
        client.post("/api/checkin", json={"week_start": "2026-04-06", "energy_level": 5}, headers=auth_headers)
        resp = client.get("/api/checkin/history", params={"limit": 2}, headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_requires_auth_latest(self, client):
        resp = client.get("/api/checkin/latest")
        assert resp.status_code == 401

    def test_requires_auth_history(self, client):
        resp = client.get("/api/checkin/history")
        assert resp.status_code == 401


class TestUserIsolation:
    def test_cannot_see_other_users_checkins(self, client, auth_headers, admin_user, db):
        """test_user should not see admin_user's check-ins."""
        from database.models import WeeklyCheckin
        from datetime import date
        admin, _ = admin_user
        checkin = WeeklyCheckin(
            user_id=admin.id,
            week_start=date(2026, 4, 6),
            training_adherence=5,
        )
        db.add(checkin)
        db.commit()

        resp = client.get("/api/checkin/history", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []
