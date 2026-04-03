import json
import time
import uuid
from typing import Optional
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import desc

from config import settings
from database.models import OAuthToken, StravaActivity

STRAVA_API_BASE = "https://www.strava.com/api/v3"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"


class StravaService:
    def __init__(self, db: Session, user_id: Optional[uuid.UUID] = None):
        self.db = db
        self.user_id = user_id

    def _token_query(self):
        q = self.db.query(OAuthToken).filter(OAuthToken.service == "strava")
        if self.user_id is not None:
            q = q.filter(OAuthToken.user_id == self.user_id)
        return q

    def is_connected(self) -> bool:
        return self._token_query().first() is not None

    def get_auth_url(self) -> str:
        # Encode user_id in state so callback can associate token with user
        state = str(self.user_id) if self.user_id else ""
        params = {
            "client_id": settings.strava_client_id,
            "redirect_uri": settings.strava_redirect_uri,
            "response_type": "code",
            "approval_prompt": "auto",
            "scope": "read,activity:read_all",
            "state": state,
        }
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{STRAVA_AUTH_URL}?{query}"

    def exchange_code(self, code: str) -> dict:
        with httpx.Client() as client:
            response = client.post(STRAVA_TOKEN_URL, data={
                "client_id": settings.strava_client_id,
                "client_secret": settings.strava_client_secret,
                "code": code,
                "grant_type": "authorization_code",
            })
            response.raise_for_status()
            return response.json()

    def save_tokens(self, token_data: dict):
        athlete = token_data.get("athlete", {})
        token = self._token_query().first()
        if not token:
            token = OAuthToken(service="strava", user_id=self.user_id)
            self.db.add(token)

        token.access_token = token_data["access_token"]
        token.refresh_token = token_data["refresh_token"]
        token.expires_at = token_data["expires_at"]
        token.athlete_id = str(athlete.get("id", ""))
        self.db.commit()

    def _refresh_if_needed(self) -> Optional[str]:
        token = self._token_query().first()
        if not token:
            return None

        if token.expires_at and token.expires_at < time.time() + 300:
            with httpx.Client() as client:
                response = client.post(STRAVA_TOKEN_URL, data={
                    "client_id": settings.strava_client_id,
                    "client_secret": settings.strava_client_secret,
                    "refresh_token": token.refresh_token,
                    "grant_type": "refresh_token",
                })
                if response.status_code == 200:
                    data = response.json()
                    token.access_token = data["access_token"]
                    token.refresh_token = data["refresh_token"]
                    token.expires_at = data["expires_at"]
                    self.db.commit()

        return token.access_token

    def get_status(self) -> dict:
        token = self._token_query().first()
        if not token:
            return {"connected": False}

        access_token = self._refresh_if_needed()
        if not access_token:
            return {"connected": False}

        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{STRAVA_API_BASE}/athlete",
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=10,
                )
                if response.status_code == 200:
                    athlete = response.json()
                    return {
                        "connected": True,
                        "athlete_id": athlete.get("id"),
                        "athlete_name": f"{athlete.get('firstname', '')} {athlete.get('lastname', '')}".strip(),
                    }
        except Exception:
            pass

        return {"connected": True, "athlete_id": token.athlete_id}

    def sync_activities(self, per_page: int = 200) -> dict:
        access_token = self._refresh_if_needed()
        if not access_token:
            return {"added": 0, "updated": 0, "deleted": 0}

        with httpx.Client() as client:
            response = client.get(
                f"{STRAVA_API_BASE}/athlete/activities",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"per_page": per_page, "page": 1},
                timeout=15,
            )
            response.raise_for_status()
            activities = response.json()

        from datetime import datetime
        fetched_ids = {a["id"] for a in activities}

        user_filter = (
            [StravaActivity.user_id == self.user_id]
            if self.user_id is not None else []
        )

        if activities:
            dates = [datetime.fromisoformat(a["start_date"].replace("Z", "+00:00")) for a in activities]
            window_start = min(dates)
            stale_q = (
                self.db.query(StravaActivity)
                .filter(StravaActivity.start_date >= window_start)
                .filter(StravaActivity.id.notin_(fetched_ids))
            )
            for f in user_filter:
                stale_q = stale_q.filter(f)
            stale = stale_q.all()
            deleted = len(stale)
            for row in stale:
                self.db.delete(row)
        else:
            deleted = 0

        added = updated = 0
        for a in activities:
            start_date = datetime.fromisoformat(a["start_date"].replace("Z", "+00:00"))
            existing_q = self.db.query(StravaActivity).filter(StravaActivity.id == a["id"])
            for f in user_filter:
                existing_q = existing_q.filter(f)
            existing = existing_q.first()
            if existing:
                existing.name = a.get("name", "")
                existing.activity_type = a.get("type", "")
                existing.distance_m = a.get("distance")
                existing.moving_time_s = a.get("moving_time")
                existing.elapsed_time_s = a.get("elapsed_time")
                existing.total_elevation = a.get("total_elevation_gain")
                existing.average_hr = a.get("average_heartrate")
                existing.max_hr = a.get("max_heartrate")
                existing.average_speed = a.get("average_speed")
                existing.kudos_count = a.get("kudos_count", 0)
                existing.raw_json = json.dumps(a)
                updated += 1
            else:
                self.db.add(StravaActivity(
                    id=a["id"],
                    user_id=self.user_id,
                    name=a.get("name", ""),
                    activity_type=a.get("type", ""),
                    start_date=start_date,
                    distance_m=a.get("distance"),
                    moving_time_s=a.get("moving_time"),
                    elapsed_time_s=a.get("elapsed_time"),
                    total_elevation=a.get("total_elevation_gain"),
                    average_hr=a.get("average_heartrate"),
                    max_hr=a.get("max_heartrate"),
                    average_speed=a.get("average_speed"),
                    kudos_count=a.get("kudos_count", 0),
                    raw_json=json.dumps(a),
                ))
                added += 1

        self.db.commit()
        return {"added": added, "updated": updated, "deleted": deleted}
