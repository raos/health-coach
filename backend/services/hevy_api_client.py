"""
Direct HTTP client for the Hevy REST API (api.hevyapp.com/v1).
Replaces the MCP stdio subprocess approach so it works on Railway (no Node.js required).
"""
import httpx
from typing import Optional

_BASE = "https://api.hevyapp.com/v1"


class HevyAPIClient:
    """Thin wrapper around the Hevy REST API. Same public interface as HevyMCPClient."""

    def __init__(self, api_key: str):
        self._headers = {"api-key": api_key, "Accept": "application/json"}

    def _get(self, path: str, params: dict = None) -> dict:
        with httpx.Client(timeout=15) as client:
            resp = client.get(f"{_BASE}{path}", headers=self._headers, params=params or {})
            resp.raise_for_status()
            return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                f"{_BASE}{path}",
                headers={**self._headers, "Content-Type": "application/json"},
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    # ── Public methods matching HevyMCPClient interface ───────────────────────

    def get_workouts(
        self,
        limit: int = 10,
        start_date: str = None,
        end_date: str = None,
    ) -> list:
        """Return recent workouts, optionally filtered by ISO date strings."""
        page_size = 10  # Hevy max page size is 10
        workouts = []
        page = 1
        while len(workouts) < limit:
            data = self._get("/workouts", {"page": page, "pageSize": page_size})
            batch = data.get("workouts", [])
            if not batch:
                break
            workouts.extend(batch)
            # Stop when last page (batch smaller than page_size) or limit reached
            if len(batch) < page_size:
                break
            page += 1

        # Filter by date if requested
        if start_date:
            workouts = [w for w in workouts if w.get("start_time", "") >= start_date]
        if end_date:
            workouts = [w for w in workouts if w.get("start_time", "") <= end_date]

        return workouts[:limit]

    def get_exercises(
        self,
        search_term: str = None,
        exclude_unused: bool = True,
    ) -> list:
        """Return exercise templates, optionally filtered by search term."""
        all_templates = []
        page = 1
        while True:
            data = self._get("/exercise_templates", {"page": page, "pageSize": 100})
            batch = data.get("exercise_templates", [])
            all_templates.extend(batch)
            if page >= data.get("pageCount", 1) or not batch:
                break
            page += 1

        if search_term:
            term = search_term.lower()
            all_templates = [t for t in all_templates if term in t.get("title", "").lower()]

        return all_templates

    def get_exercise_progress(
        self,
        exercise_ids: list,
        limit: int = 10,
        start_date: str = None,
        end_date: str = None,
    ) -> list:
        """Return sets for the given exercise template IDs across recent workouts."""
        id_set = set(exercise_ids)
        workouts = self.get_workouts(limit=50, start_date=start_date, end_date=end_date)
        progress = []
        for workout in workouts:
            for ex in workout.get("exercises", []):
                if ex.get("exercise_template_id") in id_set:
                    progress.append({
                        "workout_id": workout.get("id"),
                        "workout_title": workout.get("title"),
                        "start_time": workout.get("start_time"),
                        "exercise_title": ex.get("title"),
                        "exercise_template_id": ex.get("exercise_template_id"),
                        "sets": ex.get("sets", []),
                    })
        return progress[:limit]

    def get_routines(self) -> list:
        """Return all routines."""
        all_routines = []
        page = 1
        while True:
            data = self._get("/routines", {"page": page, "pageSize": 10})
            batch = data.get("routines", [])
            all_routines.extend(batch)
            if page >= data.get("pageCount", 1) or not batch:
                break
            page += 1
        return all_routines

    def create_routine(self, title: str, exercises: list) -> dict:
        """
        Create a routine in Hevy.
        exercises: list of dicts — each must have:
          exercise_template_id (str), rest_seconds (int), notes (str),
          sets (list of {type, weight_kg, reps})
        Returns the created routine object.
        """
        payload = {"routine": {"title": title, "exercises": exercises}}
        return self._post("/routines", payload)

    def close(self):
        pass  # No persistent connection to close
