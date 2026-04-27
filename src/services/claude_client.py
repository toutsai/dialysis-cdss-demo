from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from src.audit import audit_payload


def summarize_recommendations(payload: dict[str, Any], prompts_dir: Path) -> dict[str, Any]:
    """Call Claude to summarize rule-engine recommendations.

    PRIVACY: Caller must pass an already de-identified payload.
    AUDIT: The de-identified payload and response metadata are auditable.
    """
    model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    system = (prompts_dir / "system.md").read_text(encoding="utf-8")
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=model,
        max_tokens=1200,
        system=system,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    text = response.content[0].text if response.content else "{}"
    audit_payload(service="claude", model=model, payload=payload, response={"text": text})
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"physician_summary": text, "nursing_tasks": [], "risk_notes": ["Claude response was not JSON"]}
