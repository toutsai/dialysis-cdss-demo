from __future__ import annotations

import os
from typing import Any

import requests


class NocoDBClient:
    """Small NocoDB CRUD wrapper.

    Keep NocoDB specifics in this adapter. Domain and services should pass
    plain dict records only.
    """

    def __init__(self, base_url: str | None = None, api_token: str | None = None):
        self.base_url = (base_url or os.getenv("NOCODB_BASE_URL") or "").rstrip("/")
        self.api_token = api_token or os.getenv("NOCODB_API_TOKEN") or ""
        if not self.base_url or not self.api_token:
            raise ValueError("NOCODB_BASE_URL and NOCODB_API_TOKEN are required")

    def insert_records(self, table_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        url = f"{self.base_url}/api/v2/tables/{table_id}/records"
        resp = requests.post(url, headers=self._headers(), json=records, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _headers(self) -> dict[str, str]:
        return {
            "xc-token": self.api_token,
            "Content-Type": "application/json",
        }
