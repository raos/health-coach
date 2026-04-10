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

    def test_create_supplement_with_notes(self, client, auth_headers):
        resp = client.post(
            "/api/supplements",
            json={"name": "Vitamin C", "dosage": "500mg", "notes": "Take with food"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Take with food"

    def test_create_supplement_strips_whitespace(self, client, auth_headers):
        resp = client.post(
            "/api/supplements",
            json={"name": "  Zinc  ", "dosage": "  25mg  "},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Zinc"
        assert data["dosage"] == "25mg"

    def test_list_supplements(self, client, auth_headers):
        _create_supplement(client, auth_headers, "Vitamin D")
        _create_supplement(client, auth_headers, "Omega-3")
        resp = client.get("/api/supplements", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_empty_initially(self, client, auth_headers):
        resp = client.get("/api/supplements", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_update_supplement_dosage(self, client, auth_headers):
        s = _create_supplement(client, auth_headers, "Zinc", "25mg")
        resp = client.patch(
            f"/api/supplements/{s['id']}",
            json={"dosage": "50mg"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["dosage"] == "50mg"

    def test_update_supplement_name(self, client, auth_headers):
        s = _create_supplement(client, auth_headers, "Mag", "300mg")
        resp = client.patch(
            f"/api/supplements/{s['id']}",
            json={"name": "Magnesium"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Magnesium"

    def test_update_supplement_notes(self, client, auth_headers):
        s = _create_supplement(client, auth_headers, "Iron", "18mg")
        resp = client.patch(
            f"/api/supplements/{s['id']}",
            json={"notes": "Before bed"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Before bed"

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

        # Should not appear in list after soft delete
        list_resp = client.get("/api/supplements", headers=auth_headers)
        ids = [x["id"] for x in list_resp.json()]
        assert s["id"] not in ids

    def test_delete_returns_status_and_id(self, client, auth_headers):
        s = _create_supplement(client, auth_headers, "Turmeric")
        resp = client.delete(f"/api/supplements/{s['id']}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "deleted"
        assert data["id"] == s["id"]

    def test_delete_nonexistent_returns_404(self, client, auth_headers):
        resp = client.delete("/api/supplements/9999", headers=auth_headers)
        assert resp.status_code == 404

    def test_update_deleted_supplement_returns_404(self, client, auth_headers):
        s = _create_supplement(client, auth_headers, "Selenium")
        client.delete(f"/api/supplements/{s['id']}", headers=auth_headers)
        resp = client.patch(
            f"/api/supplements/{s['id']}",
            json={"dosage": "100mcg"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_requires_auth(self, client):
        resp = client.get("/api/supplements")
        assert resp.status_code == 401

    def test_create_requires_auth(self, client):
        resp = client.post(
            "/api/supplements",
            json={"name": "Vitamin D", "dosage": "1000 IU"},
        )
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
        assert "id" in data

    def test_log_supplement_without_date_uses_today(self, client, auth_headers):
        from datetime import date
        s = _create_supplement(client, auth_headers, "D3")
        resp = client.post(
            "/api/supplements/log",
            json={"supplement_id": s["id"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["date"] == date.today().isoformat()

    def test_log_supplement_idempotent(self, client, auth_headers):
        """Logging the same supplement+date twice returns the existing log (no error)."""
        s = _create_supplement(client, auth_headers, "Folate")
        payload = {"supplement_id": s["id"], "date": "2026-04-01"}

        resp1 = client.post("/api/supplements/log", json=payload, headers=auth_headers)
        resp2 = client.post("/api/supplements/log", json=payload, headers=auth_headers)

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Both should return the same log entry id
        assert resp1.json()["id"] == resp2.json()["id"]

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
        logs = resp.json()
        assert len(logs) == 1
        assert logs[0]["supplement_id"] == s["id"]
        assert logs[0]["date"] == "2026-04-01"

    def test_get_supplement_log_empty_for_other_date(self, client, auth_headers):
        s = _create_supplement(client, auth_headers, "Folate")
        client.post(
            "/api/supplements/log",
            json={"supplement_id": s["id"], "date": "2026-04-01"},
            headers=auth_headers,
        )
        # Different date — should be empty
        resp = client.get(
            "/api/supplements/log",
            params={"log_date": "2026-04-02"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_supplement_log_multiple_entries(self, client, auth_headers):
        s1 = _create_supplement(client, auth_headers, "Vitamin A", "5000 IU")
        s2 = _create_supplement(client, auth_headers, "Vitamin E", "400 IU")
        for s in (s1, s2):
            client.post(
                "/api/supplements/log",
                json={"supplement_id": s["id"], "date": "2026-04-05"},
                headers=auth_headers,
            )
        resp = client.get(
            "/api/supplements/log",
            params={"log_date": "2026-04-05"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

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

    def test_unlog_removes_from_log(self, client, auth_headers):
        s = _create_supplement(client, auth_headers, "Astaxanthin")
        log_resp = client.post(
            "/api/supplements/log",
            json={"supplement_id": s["id"], "date": "2026-04-03"},
            headers=auth_headers,
        )
        log_id = log_resp.json()["id"]

        client.delete(f"/api/supplements/log/{log_id}", headers=auth_headers)

        get_resp = client.get(
            "/api/supplements/log",
            params={"log_date": "2026-04-03"},
            headers=auth_headers,
        )
        assert get_resp.status_code == 200
        assert get_resp.json() == []

    def test_unlog_nonexistent_returns_404(self, client, auth_headers):
        resp = client.delete("/api/supplements/log/9999", headers=auth_headers)
        assert resp.status_code == 404

    def test_log_requires_auth(self, client):
        resp = client.get("/api/supplements/log")
        assert resp.status_code == 401

    def test_post_log_requires_auth(self, client):
        resp = client.post(
            "/api/supplements/log",
            json={"supplement_id": 1},
        )
        assert resp.status_code == 401
