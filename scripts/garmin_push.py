#!/usr/bin/env python3
"""
garmin_push.py — Fetch Garmin data and push it to the health app.

Usage:
  python scripts/garmin_push.py                         # push last 30 days to local app
  python scripts/garmin_push.py --days 90               # push last 90 days
  python scripts/garmin_push.py --url https://your-railway-app.up.railway.app

Requirements:
  pip install garminconnect requests python-dotenv

Tokens are saved to ~/.health_app_garmin/ after first login so MFA is only
needed once. Run this script whenever you want to sync fresh data to the app.
"""

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests")

try:
    from garminconnect import Garmin
except ImportError:
    sys.exit("Missing dependency: pip install garminconnect")

# ── Config ────────────────────────────────────────────────────────────────────

TOKEN_DIR = Path.home() / ".health_app_garmin"
DEFAULT_APP_URL = "http://localhost:8000"

def load_env():
    """Load .env from the repo root (two levels up from scripts/)."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return {}
    values = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        values[key.strip()] = val.strip()
    return values

# ── Garmin auth ───────────────────────────────────────────────────────────────

def get_client(email: str, password: str) -> Garmin:
    TOKEN_DIR.mkdir(exist_ok=True)
    token_file = TOKEN_DIR / "oauth2_token.json"

    # Try saved tokens first
    if token_file.exists():
        try:
            client = Garmin(email, password)
            client.login(tokenstore=str(TOKEN_DIR))
            print("Garmin: restored session from saved tokens.")
            return client
        except Exception as e:
            print(f"Saved tokens failed ({e}), attempting fresh login...")

    # Fresh login — will trigger MFA
    def prompt_mfa():
        return input("Enter Garmin MFA code from your email: ").strip()

    client = Garmin(email, password, prompt_mfa=prompt_mfa)
    client.login()
    client.garth.dump(str(TOKEN_DIR))
    print("Garmin: logged in and tokens saved.")
    return client

# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_daily_records(client: Garmin, days: int) -> list:
    records = []
    today = date.today()
    print(f"Fetching {days} days of daily data...")

    for i in range(days, 0, -1):
        d = today - timedelta(days=i)
        record = {"date": d.isoformat()}

        # Sleep
        try:
            sleep = client.get_sleep_data(d.isoformat())
            if sleep:
                dto = sleep.get("dailySleepDTO", {})
                duration = round((dto.get("sleepTimeSeconds") or 0) / 3600, 1)
                if duration > 0:
                    record["sleep_duration_hours"] = duration
                    record["deep_min"] = round((dto.get("deepSleepSeconds") or 0) / 60)
                    record["rem_min"] = round((dto.get("remSleepSeconds") or 0) / 60)
                    record["light_min"] = round((dto.get("lightSleepSeconds") or 0) / 60)
                    scores = dto.get("sleepScores", {}).get("overall", {})
                    score = scores.get("value") if isinstance(scores, dict) else None
                    if score:
                        record["sleep_score"] = int(score)
        except Exception:
            pass

        # Steps
        try:
            steps_data = client.get_steps_data(d.isoformat())
            if steps_data and isinstance(steps_data, list):
                total = sum(s.get("steps", 0) for s in steps_data)
                if total > 0:
                    record["steps"] = total
        except Exception:
            pass

        # Resting HR
        try:
            hr_data = client.get_heart_rates(d.isoformat())
            rhr = hr_data.get("restingHeartRate") if hr_data else None
            if rhr:
                record["resting_hr"] = int(rhr)
        except Exception:
            pass

        # Only include the record if we got at least one metric
        if len(record) > 1:
            records.append(record)

        if (days - i + 1) % 10 == 0:
            print(f"  {days - i + 1}/{days} days fetched...")

    print(f"Fetched {len(records)} daily records with data.")
    return records


def fetch_vo2max_records(client: Garmin, days: int) -> list:
    records = []
    today = date.today()
    print("Fetching VO2 max history...")

    for i in range(days, -1, -1):
        d = today - timedelta(days=i)
        try:
            data = client.get_max_metrics(d.isoformat())
            if data and isinstance(data, list) and len(data) > 0:
                value = data[0].get("generic", {}).get("vo2MaxPreciseValue")
                if value is not None:
                    records.append({"date": d.isoformat(), "vo2max": float(value)})
        except Exception:
            pass

    print(f"Fetched {len(records)} VO2 max records.")
    return records

# ── Push to app ───────────────────────────────────────────────────────────────

def push_to_app(app_url: str, api_key: str, daily: list, vo2max: list):
    url = f"{app_url.rstrip('/')}/api/garmin/push-data?key={api_key}"
    payload = {"daily": daily, "vo2max": vo2max}
    print(f"\nPushing to {app_url}/api/garmin/push-data ...")
    resp = requests.post(url, json=payload, timeout=30)
    if resp.status_code == 200:
        result = resp.json()
        print(f"Success: {result['upserted_daily']} daily records, {result['upserted_vo2']} VO2 max records upserted.")
    else:
        print(f"Error {resp.status_code}: {resp.text}")
        sys.exit(1)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Sync Garmin data to health app")
    parser.add_argument("--days", type=int, default=30, help="Number of days to sync (default: 30)")
    parser.add_argument("--url", type=str, default=None, help="App URL (default: http://localhost:8000)")
    args = parser.parse_args()

    env = load_env()

    email = env.get("GARMIN_EMAIL") or os.environ.get("GARMIN_EMAIL")
    password = env.get("GARMIN_PASSWORD") or os.environ.get("GARMIN_PASSWORD")
    api_key = env.get("MCP_API_KEY") or os.environ.get("MCP_API_KEY")
    app_url = args.url or env.get("PUSH_APP_URL") or DEFAULT_APP_URL

    if not email or not password:
        sys.exit("Set GARMIN_EMAIL and GARMIN_PASSWORD in .env or environment variables.")
    if not api_key:
        sys.exit("Set MCP_API_KEY in .env or environment variables.")

    print(f"Garmin sync: {args.days} days → {app_url}\n")

    client = get_client(email, password)
    daily = fetch_daily_records(client, args.days)
    vo2max = fetch_vo2max_records(client, args.days)
    push_to_app(app_url, api_key, daily, vo2max)


if __name__ == "__main__":
    main()
