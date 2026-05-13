"""HTTP client wrapper for the Hermesfy CLI.

Provides a thin HTTP client that POSTs/GETs to a FastAPI backend.
All operations use httpx with configurable server URL and auth token.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0  # seconds
ENV_AUTH_TOKEN = "HERMESFY_AUTH_TOKEN"
ENV_SERVER_URL = "HERMESFY_SERVER_URL"
DEFAULT_SERVER_URL = "http://localhost:8000"


class HermesfyClientError(Exception):
    """Raised when an HTTP request to the backend fails."""


class HermesfyClient:
    """Thin HTTP client for the Hermesfy backend API.

    All commands go through this client which handles:
      - Authentication (Bearer token)
      - Base URL resolution
      - JSON serialization/deserialization
      - Error handling

    Usage:
        client = HermesfyClient(server_url="http://localhost:8000", auth_token="...")
        workflows = await client.list_workflows(session_id="abc")
    """

    def __init__(
        self,
        server_url: str | None = None,
        auth_token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self._server_url = (
            server_url
            or os.environ.get(ENV_SERVER_URL)
            or DEFAULT_SERVER_URL
        ).rstrip("/")
        self._auth_token = auth_token or os.environ.get(ENV_AUTH_TOKEN) or ""
        self._timeout = timeout
        self._session_id: str = "default"
        self._workflow_id: str | None = None

    # ── Properties ───────────────────────────────────────────────────────

    @property
    def server_url(self) -> str:
        return self._server_url

    @property
    def session_id(self) -> str:
        return self._session_id

    @session_id.setter
    def session_id(self, value: str) -> None:
        self._session_id = value

    @property
    def workflow_id(self) -> str | None:
        return self._workflow_id

    @workflow_id.setter
    def workflow_id(self, value: str | None) -> None:
        self._workflow_id = value

    # ── HTTP Helpers ─────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        return headers

    def _url(self, path: str) -> str:
        return f"{self._server_url}{path}"

    def _check_response(self, response: httpx.Response) -> dict:
        """Raise HermesfyClientError on non-2xx, return parsed JSON."""
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise HermesfyClientError(
                f"HTTP {response.status_code}: {detail}"
            )
        try:
            return response.json()
        except json.JSONDecodeError:
            return {"raw": response.text}

    # ── API Methods ──────────────────────────────────────────────────────

    def get_nodes(self) -> dict:
        """GET /api/workflows/{workflow_id}/nodes — list nodes."""
        resp = httpx.get(
            self._url(f"/api/workflows/{self._workflow_id}/nodes"),
            headers=self._headers(),
            timeout=self._timeout,
        )
        return self._check_response(resp)

    def get_info(self) -> dict:
        """GET /api/workflows/{workflow_id}/info — workflow info."""
        resp = httpx.get(
            self._url(f"/api/workflows/{self._workflow_id}/info"),
            headers=self._headers(),
            timeout=self._timeout,
        )
        return self._check_response(resp)

    def get_graph(self) -> dict:
        """GET /api/workflows/{workflow_id}/graph — DAG graph structure."""
        resp = httpx.get(
            self._url(f"/api/workflows/{self._workflow_id}/graph"),
            headers=self._headers(),
            timeout=self._timeout,
        )
        return self._check_response(resp)

    def get_context(self) -> dict:
        """GET /api/sessions/{session_id}/context — session context."""
        resp = httpx.get(
            self._url(f"/api/sessions/{self._session_id}/context"),
            headers=self._headers(),
            timeout=self._timeout,
        )
        return self._check_response(resp)

    def create_workflow(self, data: dict) -> dict:
        """POST /api/workflows — create a new workflow."""
        payload = {**data, "session_id": self._session_id}
        resp = httpx.post(
            self._url("/api/workflows"),
            headers=self._headers(),
            json=payload,
            timeout=self._timeout,
        )
        result = self._check_response(resp)
        # Auto-set workflow_id from response
        if "workflow_id" in result:
            self._workflow_id = result["workflow_id"]
        return result

    def connect_nodes(self, source: str, target: str) -> dict:
        """POST /api/workflows/{workflow_id}/edges — connect two nodes."""
        resp = httpx.post(
            self._url(f"/api/workflows/{self._workflow_id}/edges"),
            headers=self._headers(),
            json={"source": source, "target": target},
            timeout=self._timeout,
        )
        return self._check_response(resp)

    def set_workflow_config(self, config: dict) -> dict:
        """PUT /api/workflows/{workflow_id}/config — set workflow config."""
        resp = httpx.put(
            self._url(f"/api/workflows/{self._workflow_id}/config"),
            headers=self._headers(),
            json=config,
            timeout=self._timeout,
        )
        return self._check_response(resp)

    def run_node(self, node_id: str, inputs: dict | None = None) -> dict:
        """POST /api/workflows/{workflow_id}/nodes/{node_id}/run — run single node."""
        resp = httpx.post(
            self._url(f"/api/workflows/{self._workflow_id}/nodes/{node_id}/run"),
            headers=self._headers(),
            json=inputs or {},
            timeout=self._timeout * 3,  # Longer timeout for execution
        )
        return self._check_response(resp)

    def run_all(self, options: dict | None = None) -> dict:
        """POST /api/workflows/{workflow_id}/run — run entire workflow."""
        resp = httpx.post(
            self._url(f"/api/workflows/{self._workflow_id}/run"),
            headers=self._headers(),
            json=options or {},
            timeout=self._timeout * 10,  # Much longer for full workflow
        )
        return self._check_response(resp)

    def save_workflow(self, filename: str | None = None) -> dict:
        """POST /api/workflows/{workflow_id}/save — save workflow to server."""
        resp = httpx.post(
            self._url(f"/api/workflows/{self._workflow_id}/save"),
            headers=self._headers(),
            json={"filename": filename or f"{self._workflow_id}.json"},
            timeout=self._timeout,
        )
        return self._check_response(resp)

    def load_workflow(self, filename: str) -> dict:
        """POST /api/workflows/load — load workflow from file."""
        resp = httpx.post(
            self._url("/api/workflows/load"),
            headers=self._headers(),
            json={"filename": filename},
            timeout=self._timeout,
        )
        result = self._check_response(resp)
        if "workflow_id" in result:
            self._workflow_id = result["workflow_id"]
        return result

    def clear_session(self) -> dict:
        """DELETE /api/sessions/{session_id} — clear session."""
        resp = httpx.delete(
            self._url(f"/api/sessions/{self._session_id}"),
            headers=self._headers(),
            timeout=self._timeout,
        )
        return self._check_response(resp)
