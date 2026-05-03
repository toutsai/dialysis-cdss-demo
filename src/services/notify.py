from __future__ import annotations

import hashlib
import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage

from src.audit import audit_payload


@dataclass(frozen=True)
class NotifyResult:
    sent: bool
    message: str
    channel: str = ""


def notify_pending_approvals(message: str, dry_run: bool = True) -> None:
    """Notify physicians or nurses.

    TODO(NOTIFY): LINE Notify was discontinued. If LINE is required, implement
    LINE Messaging API here or use the hospital notification adapter.
    """
    if dry_run:
        print(f"[dry-run notify] {message}")
        return
    raise NotImplementedError("TODO(NOTIFY): implement email or LINE Messaging API notification")


def notify_new_pending_problem(
    *,
    patient_label: str,
    bed: str,
    created_by: str,
    created_at: str,
    problem_content: str = "",
) -> NotifyResult:
    lines = _pending_problem_lines(
        patient_label=patient_label,
        bed=bed,
        created_by=created_by,
        created_at=created_at,
        problem_content=problem_content,
    )
    line_result = _notify_line(
        lines=lines,
        patient_label=patient_label,
        bed=bed,
        created_by=created_by,
        created_at=created_at,
        problem_content=problem_content,
    )
    if line_result.sent:
        return line_result
    email_result = _notify_email(
        lines=lines,
        patient_label=patient_label,
        bed=bed,
        created_by=created_by,
        created_at=created_at,
        problem_content=problem_content,
    )
    if email_result.sent:
        return email_result
    return NotifyResult(False, f"{line_result.message}；{email_result.message}")


def _notify_line(
    *,
    lines: list[str],
    patient_label: str,
    bed: str,
    created_by: str,
    created_at: str,
    problem_content: str,
) -> NotifyResult:
    token = _env("LINE_CHANNEL_ACCESS_TOKEN")
    to_id = _env("LINE_TO_ID") or _env("LINE_TO_USER_ID")
    if not token or not to_id:
        result = NotifyResult(False, "尚未設定 LINE_CHANNEL_ACCESS_TOKEN / LINE_TO_ID，未寄出 LINE 通知。", "line")
        _audit_notification("line", result, patient_label, bed, created_by, created_at, problem_content)
        return result

    try:
        status_code = _post_line_message(
            token,
            {"to": to_id, "messages": [{"type": "text", "text": "\n".join(lines)}]},
        )
    except (OSError, urllib.error.URLError) as exc:
        result = NotifyResult(False, f"LINE 通知失敗：{exc}", "line")
        _audit_notification("line", result, patient_label, bed, created_by, created_at, problem_content)
        return result
    if status_code >= 400:
        result = NotifyResult(False, f"LINE 通知失敗：HTTP {status_code}", "line")
        _audit_notification("line", result, patient_label, bed, created_by, created_at, problem_content)
        return result

    result = NotifyResult(True, "已寄出 LINE 待處理問題通知", "line")
    _audit_notification("line", result, patient_label, bed, created_by, created_at, problem_content)
    return result


def _notify_email(
    *,
    lines: list[str],
    patient_label: str,
    bed: str,
    created_by: str,
    created_at: str,
    problem_content: str,
) -> NotifyResult:
    recipient = _env("PROBLEM_NOTIFY_TO") or _env("EMAIL_TO")
    username = _env("SMTP_USERNAME") or _env("EMAIL_FROM")
    password = _env("SMTP_PASSWORD")
    sender = _env("SMTP_FROM") or username
    host = _env("SMTP_HOST") or "smtp.gmail.com"
    port = int(_env("SMTP_PORT") or "587")

    if not recipient:
        result = NotifyResult(False, "尚未設定 PROBLEM_NOTIFY_TO，未寄出 email 通知。", "email")
        _audit_notification("email", result, patient_label, bed, created_by, created_at, problem_content)
        return result
    if not username or not password or not sender:
        result = NotifyResult(False, "尚未設定 SMTP_USERNAME / SMTP_PASSWORD，未寄出 email 通知。", "email")
        _audit_notification("email", result, patient_label, bed, created_by, created_at, problem_content)
        return result

    msg = EmailMessage()
    msg["Subject"] = "透析 CDSS：有新的待處理問題"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content("\n".join(lines))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls(context=context)
            smtp.login(username, password)
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException) as exc:
        result = NotifyResult(False, f"email 通知失敗：{exc}", "email")
        _audit_notification("email", result, patient_label, bed, created_by, created_at, problem_content)
        return result
    result = NotifyResult(True, f"已寄出 email 待處理問題通知至 {recipient}", "email")
    _audit_notification("email", result, patient_label, bed, created_by, created_at, problem_content)
    return result


def _pending_problem_lines(
    *,
    patient_label: str,
    bed: str,
    created_by: str,
    created_at: str,
    problem_content: str,
) -> list[str]:
    lines = [
        "透析 CDSS：新的現在待處理問題",
        "",
        f"病人：{patient_label}",
        f"床位：{bed or '未填'}",
        f"建立者：{created_by or 'unknown'}",
        f"時間：{created_at}",
    ]
    if _env_flag("LINE_INCLUDE_PROBLEM_CONTENT", False):
        lines.extend(["", "內容：", problem_content or "未填"])
    else:
        lines.extend(["", "請登入系統查看內容。"])
    return lines


def _audit_notification(
    provider: str,
    result: NotifyResult,
    patient_label: str,
    bed: str,
    created_by: str,
    created_at: str,
    problem_content: str,
) -> None:
    audit_payload(
        service="notification",
        model=provider,
        payload={
            "provider": provider,
            "event": "pending_problem_changed",
            "patient_label": patient_label,
            "bed": bed,
            "created_by": created_by,
            "created_at": created_at,
            "include_content": _env_flag("LINE_INCLUDE_PROBLEM_CONTENT", False),
            "problem_content_hash": _hash_text(problem_content),
        },
        response={"sent": result.sent, "message": result.message, "channel": result.channel},
        status="ok" if result.sent else "skipped",
    )


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else ""


def _post_line_message(token: str, payload: dict[str, object]) -> int:
    request = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def _env_flag(key: str, default: bool = False) -> bool:
    value = _env(key)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


def _env(key: str) -> str:
    return os.getenv(key, "").strip()
