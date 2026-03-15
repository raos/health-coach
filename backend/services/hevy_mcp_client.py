"""
Synchronous Python client for the @vreippainen/hevy-mcp-server MCP server.
Communicates via JSON-RPC 2.0 over stdio with the Node.js subprocess.
"""
import json
import os
import subprocess
import threading
from typing import Any, Optional


class HevyMCPClient:
    """Spawns the hevy-mcp-server process and communicates via MCP over stdio."""

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._req_id = 0

    def _start_process(self):
        env = {**os.environ, "HEVY_API_KEY": self._api_key}
        self._proc = subprocess.Popen(
            ["hevy-mcp-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,  # MCP servers log to stderr; don't pollute backend
            env=env,
        )
        self._initialize()

    def _ensure_running(self):
        if self._proc is None or self._proc.poll() is not None:
            self._start_process()

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def _send_request(self, method: str, params: dict = None) -> Any:
        """Send a JSON-RPC request and return the result (or raise on error)."""
        req_id = self._next_id()
        msg = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params:
            msg["params"] = params
        line = json.dumps(msg) + "\n"
        self._proc.stdin.write(line.encode())
        self._proc.stdin.flush()

        raw = self._proc.stdout.readline()
        if not raw:
            raise RuntimeError("Hevy MCP server closed stdout unexpectedly")
        resp = json.loads(raw)
        if "error" in resp:
            raise RuntimeError(f"MCP error: {resp['error']}")
        return resp.get("result")

    def _send_notification(self, method: str, params: dict = None):
        """Send a JSON-RPC notification (no response expected)."""
        msg = {"jsonrpc": "2.0", "method": method}
        if params:
            msg["params"] = params
        line = json.dumps(msg) + "\n"
        self._proc.stdin.write(line.encode())
        self._proc.stdin.flush()

    def _initialize(self):
        self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "health-app", "version": "1.0.0"},
        })
        self._send_notification("notifications/initialized")

    def call_tool(self, tool_name: str, arguments: dict = None) -> Any:
        """Call an MCP tool and return the parsed result."""
        with self._lock:
            self._ensure_running()
            result = self._send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments or {},
            })

        # MCP tools/call result has content array of {type, text} items
        if isinstance(result, dict) and "content" in result:
            for item in result["content"]:
                if item.get("type") == "text":
                    text = item["text"]
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return text
        return result

    # ── Convenience wrappers matching the MCP tool names ─────────────────────

    def get_workouts(self, limit: int = 10, start_date: str = None, end_date: str = None) -> list:
        args: dict = {"limit": limit}
        if start_date:
            args["startDate"] = start_date
        if end_date:
            args["endDate"] = end_date
        result = self.call_tool("get-workouts", args)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("workouts", [])
        return []

    def get_exercises(self, search_term: str = None, exclude_unused: bool = True) -> list:
        args: dict = {"excludeUnused": exclude_unused}
        if search_term:
            args["searchTerm"] = search_term
        result = self.call_tool("get-exercises", args)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("exercises", list(result.values())[0] if result else [])
        return []

    def get_exercise_progress(
        self,
        exercise_ids: list[str],
        limit: int = 10,
        start_date: str = None,
        end_date: str = None,
    ) -> list:
        args: dict = {"exerciseIds": exercise_ids, "limit": limit}
        if start_date:
            args["startDate"] = start_date
        if end_date:
            args["endDate"] = end_date
        result = self.call_tool("get-exercise-progress-by-ids", args)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("progress", result.get("exercises", []))
        return []

    def get_routines(self) -> list:
        result = self.call_tool("get-routines", {})
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return result.get("routines", [])
        return []

    def close(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
