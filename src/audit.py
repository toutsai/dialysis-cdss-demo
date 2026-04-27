from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def audit_payload(service: str, model: str, payload: dict[str, Any], response: dict[str, Any], status: str = "ok") -> dict[str, Any]:
    record = {
        "service": service,
        "model": model,
        "payload_hash": _hash(payload),
        "deid_payload_json": payload,
        "response_json": response,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
    }
    path = Path("exports") / "api_audit_logs.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
