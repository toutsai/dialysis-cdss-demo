from __future__ import annotations


def notify_pending_approvals(message: str, dry_run: bool = True) -> None:
    """Notify physicians or nurses.

    TODO(NOTIFY): LINE Notify was discontinued. If LINE is required, implement
    LINE Messaging API here or use the hospital notification adapter.
    """
    if dry_run:
        print(f"[dry-run notify] {message}")
        return
    raise NotImplementedError("TODO(NOTIFY): implement email or LINE Messaging API notification")
