#!/usr/bin/env python3
"""
garmin_import_json.py — Import Garmin steps and resting HR from DevTools-captured JSON.

Usage:
  python scripts/garmin_import_json.py ~/Downloads/garmin_data/         # folder of JSON files
  python scripts/garmin_import_json.py ~/Downloads/day1.json day2.json  # individual files
  python scripts/garmin_import_json.py ~/Downloads/garmin_data/ --url https://your-railway.up.railway.app

How to capture the JSON files:
  1. Go to connect.garmin.com (already logged in)
  2. Open DevTools → Network tab → filter by "Fetch/XHR" → check "Preserve log"
  3. Navigate to connect.garmin.com/modern/daily-summary
  4. Use the date arrows to step through past days
  5. In the Network tab, right-click any request with "usersummary" in the URL
     → Copy → Copy Response → paste into a .json file
  6. Repeat for each day you want to import (or capture the bulk chart requests)

Supported JSON formats (auto-detected):
  A) Single-day usersummary:  {"calendarDate": "2026-03-25", "totalSteps": 8432, "restingHeartRateValue": 58}
  B) dailyHeartRate:          {"calendarDate": "2026-03-25", "restingHeartRate": 58}
  C) Array of daily records:  [{"calendarDate": "...", "totalSteps": ...}, ...]
  D) Wrapped array:           {"dailySummaries": [...]} or {"allMetrics": [...]}
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Missing dependency: pip install requests")


# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_APP_URL = "http://localhost:8000"

def load_env():
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


# ── JSON parsing ──────────────────────────────────────────────────────────────

def extract_record(obj: dict) -> dict | None:
    """Extract steps and/or resting_hr from a single day's JSON object."""
    date_str = obj.get("calendarDate") or obj.get("summaryDate") or obj.get("date")
    if not date_str:
        return None

    record = {"date": date_str[:10]}  # normalize to YYYY-MM-DD

    steps = obj.get("totalSteps") or obj.get("steps")
    if steps is not None:
        record["steps"] = int(steps)

    rhr = obj.get("restingHeartRateValue") or obj.get("restingHeartRate")
    if rhr is not None:
        record["resting_hr"] = int(rhr)

    sleeping_secs = obj.get("sleepingSeconds")
    if sleeping_secs:
        record["sleep_duration_hours"] = round(sleeping_secs / 3600, 1)

    # Only return if we got at least one useful metric
    if len(record) > 1:
        return record
    return None


def parse_file(path: Path) -> list[dict]:
    """Parse a JSON file and return a list of daily records."""
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print(f"  Skipping {path.name}: invalid JSON ({e})")
        return []

    records = []

    if isinstance(data, list):
        # Format C: array of daily objects
        for obj in data:
            if isinstance(obj, dict):
                r = extract_record(obj)
                if r:
                    records.append(r)

    elif isinstance(data, dict):
        # Try Format D: wrapped array (check common wrapper keys)
        for wrapper_key in ("dailySummaries", "allMetrics", "summaries", "values", "data"):
            if wrapper_key in data and isinstance(data[wrapper_key], list):
                for obj in data[wrapper_key]:
                    if isinstance(obj, dict):
                        r = extract_record(obj)
                        if r:
                            records.append(r)
                break
        else:
            # Format A/B: single day object
            r = extract_record(data)
            if r:
                records.append(r)

    return records


def collect_files(paths: list[str]) -> list[Path]:
    """Expand folders to .json files; keep individual files as-is."""
    files = []
    for p in paths:
        path = Path(p).expanduser()
        if path.is_dir():
            files.extend(sorted(path.glob("*.json")))
        elif path.is_file():
            files.append(path)
        else:
            print(f"Warning: {p} does not exist, skipping.")
    return files


# ── Push to app ───────────────────────────────────────────────────────────────

def push_to_app(app_url: str, api_key: str, daily: list[dict]):
    url = f"{app_url.rstrip('/')}/api/garmin/push-data?key={api_key}"
    payload = {"daily": daily, "vo2max": []}
    resp = requests.post(url, json=payload, timeout=30)
    if resp.status_code == 200:
        result = resp.json()
        print(f"Success: {result['upserted_daily']} records upserted.")
    elif resp.status_code == 401:
        sys.exit("Error: Invalid MCP_API_KEY. Check your .env file.")
    else:
        sys.exit(f"Error {resp.status_code}: {resp.text}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Import Garmin JSON from DevTools into health app")
    parser.add_argument("paths", nargs="+", help="JSON file(s) or folder containing JSON files")
    parser.add_argument("--url", default=None, help="App URL (default: http://localhost:8000)")
    args = parser.parse_args()

    env = load_env()
    api_key = env.get("MCP_API_KEY") or os.environ.get("MCP_API_KEY")
    app_url = args.url or env.get("PUSH_APP_URL") or DEFAULT_APP_URL

    if not api_key:
        sys.exit("Set MCP_API_KEY in .env or environment variables.")

    files = collect_files(args.paths)
    if not files:
        sys.exit("No JSON files found.")

    print(f"Processing {len(files)} file(s)...\n")

    # Collect all records, deduplicate by date (last-write-wins)
    by_date: dict[str, dict] = {}
    for f in files:
        records = parse_file(f)
        for r in records:
            existing = by_date.get(r["date"], {})
            existing.update(r)  # merge: newer files fill in missing fields
            by_date[r["date"]] = existing

    if not by_date:
        sys.exit("No usable records found. Check that your JSON files contain 'calendarDate', 'totalSteps', or 'restingHeartRate' fields.")

    daily = sorted(by_date.values(), key=lambda x: x["date"])

    print(f"Found {len(daily)} dates with data:")
    for r in daily:
        parts = []
        if "steps" in r:
            parts.append(f"steps: {r['steps']:,}")
        if "resting_hr" in r:
            parts.append(f"resting_hr: {r['resting_hr']}")
        if "sleep_duration_hours" in r:
            parts.append(f"sleep: {r['sleep_duration_hours']}h")
        print(f"  {r['date']}  {', '.join(parts) if parts else '(no metrics)'}")

    print(f"\nPushing to {app_url} ...")
    push_to_app(app_url, api_key, daily)


if __name__ == "__main__":
    main()
