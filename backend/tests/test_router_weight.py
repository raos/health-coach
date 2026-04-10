"""Integration tests for POST/GET/DELETE /api/weight."""
import pytest
from datetime import date as date_type

from database.models import WeightLog


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

    def test_upsert_existing_date_updates_weight(self, client, auth_headers):
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

    def test_returns_all_logs_sorted_ascending(self, client, auth_headers):
        client.post("/api/weight/log", json={"date": "2026-04-02", "weight_lbs": 174.0}, headers=auth_headers)
        client.post("/api/weight/log", json={"date": "2026-04-01", "weight_lbs": 175.0}, headers=auth_headers)
        resp = client.get("/api/weight/history", headers=auth_headers)
        assert resp.status_code == 200
        dates = [r["date"] for r in resp.json()]
        assert dates == sorted(dates)

    def test_date_range_filter_start(self, client, auth_headers):
        client.post("/api/weight/log", json={"date": "2026-03-01", "weight_lbs": 180.0}, headers=auth_headers)
        client.post("/api/weight/log", json={"date": "2026-04-01", "weight_lbs": 175.0}, headers=auth_headers)
        resp = client.get(
            "/api/weight/history",
            params={"start": "2026-04-01"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["weight_lbs"] == 175.0

    def test_date_range_filter_end(self, client, auth_headers):
        client.post("/api/weight/log", json={"date": "2026-03-01", "weight_lbs": 180.0}, headers=auth_headers)
        client.post("/api/weight/log", json={"date": "2026-04-01", "weight_lbs": 175.0}, headers=auth_headers)
        resp = client.get(
            "/api/weight/history",
            params={"end": "2026-03-31"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["weight_lbs"] == 180.0

    def test_user_isolation(self, client, auth_headers, admin_user, db):
        """test_user should not see admin_user's weight logs."""
        admin, _ = admin_user
        wl = WeightLog(user_id=admin.id, date=date_type(2026, 4, 1), weight_lbs=200.0)
        db.add(wl)
        db.commit()

        resp = client.get("/api/weight/history", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []


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

    def test_cannot_delete_another_users_log(self, client, auth_headers, admin_user, db):
        admin, _ = admin_user
        wl = WeightLog(user_id=admin.id, date=date_type(2026, 4, 1), weight_lbs=200.0)
        db.add(wl)
        db.commit()
        db.refresh(wl)

        resp = client.delete(f"/api/weight/{wl.id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_requires_auth(self, client):
        resp = client.delete("/api/weight/1")
        assert resp.status_code == 401
