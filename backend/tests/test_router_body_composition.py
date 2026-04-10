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
        # Log a weight first
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

    def test_requires_auth_latest(self, client):
        resp = client.get("/api/body-composition/latest")
        assert resp.status_code == 401

    def test_requires_auth_history(self, client):
        resp = client.get("/api/body-composition/history")
        assert resp.status_code == 401
