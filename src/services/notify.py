from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage


@dataclass(frozen=True)
class NotifyResult:
    sent: bool
    message: str


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
) -> NotifyResult:
    recipient = _env("PROBLEM_NOTIFY_TO") or _env("EMAIL_TO")
    username = _env("SMTP_USERNAME") or _env("EMAIL_FROM")
    password = _env("SMTP_PASSWORD")
    sender = _env("SMTP_FROM") or username
    host = _env("SMTP_HOST") or "smtp.gmail.com"
    port = int(_env("SMTP_PORT") or "587")

    if not recipient:
        return NotifyResult(False, "已新增；尚未設定 PROBLEM_NOTIFY_TO，未寄出通知。")
    if not username or not password or not sender:
        return NotifyResult(False, "已新增；尚未設定 SMTP_USERNAME / SMTP_PASSWORD，未寄出通知。")

    msg = EmailMessage()
    msg["Subject"] = "透析 CDSS：有新的待處理問題"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(
        "\n".join([
            "透析 CDSS 有新的現在待處理問題。",
            "",
            f"病人：{patient_label}",
            f"床位：{bed or '未填'}",
            f"新增者：{created_by or 'unknown'}",
            f"新增時間：{created_at}",
            "",
            "請登入系統查看詳細內容。",
        ])
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.starttls(context=context)
        smtp.login(username, password)
        smtp.send_message(msg)
    return NotifyResult(True, f"已寄出待處理問題通知至 {recipient}")


def _env(key: str) -> str:
    return os.getenv(key, "").strip()
