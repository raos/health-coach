"""
Garmin Connect service with MFA support.
Flow:
  1. Call start_login() → returns "ok" (token reuse) or "mfa_required" (needs OTP)
  2. If "mfa_required", display OTP prompt, then call submit_mfa(otp)
  3. On success, session tokens are saved to garmin_session/ dir for reuse.
"""
import os
import queue
import threading
import time
from datetime import date, timedelta
from typing import Optional

from config import settings

# Use GARMIN_SESSION_DIR env var if set (Railway: /data/garmin_session),
# otherwise fall back to a local directory beside the backend root.
_TOKEN_DIR = os.environ.get(
    "GARMIN_SESSION_DIR",
    os.path.join(os.path.dirname(__file__), "..", "garmin_session"),
)


class GarminService:
    # How long (seconds) to cache a failed connection check before retrying
    _STATUS_TTL = 600  # 10 minutes

    def __init__(self):
        self._client = None
        self._state_queue: queue.Queue = queue.Queue()
        self._mfa_event = threading.Event()
        self._mfa_code: Optional[str] = None
        self._last_check_time: float = 0.0   # epoch seconds of last status check
        self._last_check_ok: bool = False     # result of last check

    def is_configured(self) -> bool:
        return bool(settings.garmin_email and settings.garmin_password)

    def is_authenticated(self) -> bool:
        """Fast check — True only if a working client is already in memory."""
        return self._client is not None

    def has_saved_tokens(self) -> bool:
        """True if token files exist on disk (may or may not still be valid)."""
        return os.path.exists(os.path.join(_TOKEN_DIR, "oauth2_token.json"))

    def check_connection(self) -> bool:
        """
        Test whether saved tokens actually work. Caches the result for
        _STATUS_TTL seconds to avoid hammering Garmin's API on every page load.
        Always returns True immediately if _client is already in memory.
        """
        if self._client is not None:
            return True
        now = time.time()
        if now - self._last_check_time < self._STATUS_TTL:
            return self._last_check_ok   # return cached result, don't hit Garmin
        # Actually test the connection
        try:
            self._get_client()
            self._last_check_ok = True
        except Exception:
            self._last_check_ok = False
        self._last_check_time = now
        return self._last_check_ok

    def invalidate_status_cache(self) -> None:
        """Force the next check_connection() call to re-test (call after login/import)."""
        self._last_check_time = 0.0

    def _token_dir(self) -> str:
        os.makedirs(_TOKEN_DIR, exist_ok=True)
        return _TOKEN_DIR

    def _prompt_mfa(self) -> str:
        """Called by garth during login when MFA code is needed. Blocks until submit_mfa() is called."""
        self._state_queue.put("mfa_required")
        self._mfa_event.wait(timeout=300)  # wait up to 5 min for user to enter OTP
        self._mfa_event.clear()
        return self._mfa_code or ""

    def _do_login(self, client) -> None:
        try:
            client.login()
            client.garth.dump(self._token_dir())
            self._client = client
            self._last_check_ok = True
            self._last_check_time = time.time()
            self._state_queue.put("done")
        except Exception as e:
            self._state_queue.put(f"error:{e}")

    def _drain_queue(self):
        while not self._state_queue.empty():
            try:
                self._state_queue.get_nowait()
            except queue.Empty:
                break

    def start_login(self) -> str:
        """
        Initiate Garmin login. Returns:
          "ok"           — authenticated (via saved tokens or password login without MFA)
          "mfa_required" — Garmin sent an OTP email; call submit_mfa(otp) to finish
        Raises RuntimeError on failure.
        """
        if not self.is_configured():
            raise RuntimeError("GARMIN_EMAIL and GARMIN_PASSWORD not set in .env")

        from garminconnect import Garmin

        # Try saved session tokens first.
        # Must use login(tokenstore=) — not garth.load() — because login() also
        # refreshes the OAuth2 token and sets display_name (needed for all API URLs).
        token_dir = self._token_dir()
        if os.path.exists(os.path.join(token_dir, "oauth2_token.json")):
            try:
                client = Garmin(settings.garmin_email, settings.garmin_password)
                client.login(tokenstore=token_dir)
                self._client = client
                self._last_check_ok = True
                self._last_check_time = time.time()
                return "ok"
            except Exception:
                pass  # tokens expired — fall through to fresh login

        # Fresh login with MFA support
        self._mfa_event.clear()
        self._mfa_code = None
        self._drain_queue()

        client = Garmin(
            settings.garmin_email,
            settings.garmin_password,
            prompt_mfa=self._prompt_mfa,
        )
        thread = threading.Thread(target=self._do_login, args=(client,), daemon=True)
        thread.start()

        # Block until either MFA is requested or login finishes
        try:
            state = self._state_queue.get(timeout=60)
        except queue.Empty:
            raise RuntimeError("Garmin login timed out. Check credentials.")

        if state == "mfa_required":
            return "mfa_required"
        elif state == "done":
            return "ok"
        else:
            raise RuntimeError(state.replace("error:", "", 1))

    def submit_mfa(self, otp: str) -> None:
        """Provide the OTP from Garmin's MFA email to complete login."""
        self._mfa_code = otp.strip()
        self._mfa_event.set()

        try:
            state = self._state_queue.get(timeout=30)
        except queue.Empty:
            raise RuntimeError("Timed out waiting for Garmin to accept MFA code.")

        if state != "done":
            raise RuntimeError(state.replace("error:", "", 1))

    def _get_client(self):
        if self._client is not None:
            return self._client
        # Try to restore from saved tokens (e.g. after server restart).
        # login(tokenstore=) loads tokens, refreshes the OAuth2 token if
        # expired, and sets display_name — all needed for API URL construction.
        token_dir = self._token_dir()
        if os.path.exists(os.path.join(token_dir, "oauth2_token.json")) and self.is_configured():
            try:
                from garminconnect import Garmin
                client = Garmin(settings.garmin_email, settings.garmin_password)
                client.login(tokenstore=token_dir)
                self._client = client
                return client
            except Exception as e:
                raise RuntimeError(f"Garmin token restore failed: {e}") from e
        raise RuntimeError("Garmin not authenticated. Go to Settings → Garmin Connect → Connect.")

    # ── Data methods ──────────────────────────────────────────────────────────

    def get_sleep_data(self, for_date: Optional[date] = None) -> dict:
        d = for_date or date.today() - timedelta(days=1)
        return self._get_client().get_sleep_data(d.isoformat())

    def get_body_battery(self, for_date: Optional[date] = None) -> list:
        d = for_date or date.today()
        return self._get_client().get_body_battery(d.isoformat())

    def get_steps(self, for_date: Optional[date] = None) -> dict:
        d = for_date or date.today()
        return self._get_client().get_steps_data(d.isoformat())

    def get_resting_heart_rate(self, for_date: Optional[date] = None) -> Optional[int]:
        try:
            d = for_date or date.today()
            # get_heart_rates returns restingHeartRate as a top-level field
            data = self._get_client().get_heart_rates(d.isoformat())
            rhr = data.get("restingHeartRate")
            if rhr:
                return int(rhr)
            # fallback: try the userstats endpoint
            rhr_data = self._get_client().get_rhr_day(d.isoformat())
            readings = (
                rhr_data.get("allMetrics", {})
                .get("metricsMap", {})
                .get("WELLNESS_RESTING_HEART_RATE", [])
            )
            if readings:
                return int(readings[0].get("value", 0)) or None
        except Exception:
            pass
        return None

    def get_vo2max(self) -> Optional[float]:
        try:
            data = self._get_client().get_max_metrics(date.today().isoformat())
            if data and isinstance(data, list) and len(data) > 0:
                return data[0].get("generic", {}).get("vo2MaxPreciseValue")
        except Exception:
            pass
        return None

    def get_sleep_range(self, days: int = 30) -> list:
        """Sleep data for the past N days, oldest first."""
        results = []
        for i in range(days, -1, -1):
            d = date.today() - timedelta(days=i)
            try:
                sleep = self.get_sleep_data(d)
                if sleep:
                    daily = sleep.get("dailySleepDTO", {})
                    duration = round((daily.get("sleepTimeSeconds") or 0) / 3600, 1)
                    if duration > 0:
                        results.append({
                            "date": d.isoformat(),
                            "duration_hours": duration,
                            "score": daily.get("sleepScores", {}).get("overall", {}).get("value"),
                            "deep_min": round((daily.get("deepSleepSeconds") or 0) / 60),
                            "rem_min": round((daily.get("remSleepSeconds") or 0) / 60),
                            "light_min": round((daily.get("lightSleepSeconds") or 0) / 60),
                        })
            except Exception:
                pass
        return results

    def get_steps_range(self, days: int = 30) -> list:
        """Daily step counts for the past N days, oldest first."""
        results = []
        for i in range(days, 0, -1):
            d = date.today() - timedelta(days=i)
            try:
                steps = self.get_steps(d)
                if steps and isinstance(steps, list):
                    total = sum(s.get("steps", 0) for s in steps)
                    if total > 0:
                        results.append({"date": d.isoformat(), "steps": total})
            except Exception:
                pass
        return results

    def get_resting_hr_range(self, days: int = 30) -> list:
        """Resting heart rate for the past N days, oldest first."""
        results = []
        for i in range(days, 0, -1):
            d = date.today() - timedelta(days=i)
            try:
                rhr = self.get_resting_heart_rate(d)
                if rhr:
                    results.append({"date": d.isoformat(), "rhr": rhr})
            except Exception:
                pass
        return results

    def get_health_snapshot(self) -> dict:
        """Return a dict of all available health metrics for use in AI context."""
        result = {}
        yesterday = date.today() - timedelta(days=1)
        try:
            sleep = self.get_sleep_data(yesterday)
            if sleep:
                daily = sleep.get("dailySleepDTO", {})
                result["sleep_duration_hours"] = round(
                    (daily.get("sleepTimeSeconds") or 0) / 3600, 1
                )
                result["sleep_score"] = daily.get("sleepScores", {}).get("overall", {}).get("value")
                result["deep_sleep_min"] = round(
                    (daily.get("deepSleepSeconds") or 0) / 60
                )
                result["rem_sleep_min"] = round(
                    (daily.get("remSleepSeconds") or 0) / 60
                )
        except Exception:
            pass
        try:
            bb = self.get_body_battery()
            if bb:
                # Pick latest reading
                latest = bb[-1] if isinstance(bb, list) else bb
                result["body_battery"] = latest.get("charged") or latest.get("bodyBatteryLevel")
        except Exception:
            pass
        try:
            rhr = self.get_resting_heart_rate()
            if rhr:
                result["resting_hr"] = rhr
        except Exception:
            pass
        try:
            steps = self.get_steps()
            if steps and isinstance(steps, list) and len(steps) > 0:
                result["daily_steps"] = sum(s.get("steps", 0) for s in steps)
        except Exception:
            pass
        return result


garmin_service = GarminService()
