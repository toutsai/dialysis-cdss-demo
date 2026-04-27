from __future__ import annotations

import hashlib
from dataclasses import asdict, is_dataclass
from typing import Any

FORBIDDEN_KEYS = {
    "name",
    "chart_no",
    "birthday",
    "birth_date",
    "phone",
    "national_id",
    "address",
    "bed",
}


def stable_deid(chart_no: str, salt: str = "dialysis-cdss-v1") -> str:
    digest = hashlib.sha256(f"{salt}:{chart_no}".encode("utf-8")).hexdigest()
    number = int(digest[:10], 16) % 1_000_000
    return f"P{number:06d}"


def redact_for_claude(payload: Any, chart_to_deid: dict[str, str] | None = None) -> Any:
    """Remove direct identifiers before sending data to Claude.

    PRIVACY: Claude payload must not include name, chart_no, birthday, phone,
    address, or full bed information. Local NocoDB keeps the mapping.
    """
    chart_to_deid = chart_to_deid or {}
    if is_dataclass(payload):
        payload = asdict(payload)
    if isinstance(payload, list):
        return [redact_for_claude(item, chart_to_deid) for item in payload]
    if isinstance(payload, tuple):
        return [redact_for_claude(item, chart_to_deid) for item in payload]
    if not isinstance(payload, dict):
        return payload

    out: dict[str, Any] = {}
    chart_no = str(payload.get("chart_no", "") or "")
    if chart_no:
        out["deid"] = chart_to_deid.get(chart_no, stable_deid(chart_no))

    for key, value in payload.items():
        key_text = str(key)
        if key_text in FORBIDDEN_KEYS:
            continue
        out[key_text] = redact_for_claude(value, chart_to_deid)
    return out
