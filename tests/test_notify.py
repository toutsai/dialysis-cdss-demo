from __future__ import annotations

from src.services import notify


def _clear_notification_env(monkeypatch):
    for key in [
        "LINE_CHANNEL_ACCESS_TOKEN",
        "LINE_TO_ID",
        "LINE_TO_USER_ID",
        "LINE_INCLUDE_PROBLEM_CONTENT",
        "PROBLEM_NOTIFY_TO",
        "EMAIL_TO",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_FROM",
        "EMAIL_FROM",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_notify_pending_problem_without_config_is_nonblocking(monkeypatch):
    _clear_notification_env(monkeypatch)
    monkeypatch.setattr(notify, "audit_payload", lambda **kwargs: kwargs)

    result = notify.notify_new_pending_problem(
        patient_label="MaskedPatient01",
        bed="1",
        created_by="DoctorA",
        created_at="2026-05-03T00:00:00",
        problem_content="SecretProblemContent",
    )

    assert not result.sent
    assert "LINE_CHANNEL_ACCESS_TOKEN" in result.message
    assert "PROBLEM_NOTIFY_TO" in result.message


def test_line_notification_omits_problem_content_by_default(monkeypatch):
    _clear_notification_env(monkeypatch)
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "token")
    monkeypatch.setenv("LINE_TO_ID", "group-id")
    monkeypatch.setattr(notify, "audit_payload", lambda **kwargs: kwargs)
    sent = {}

    def fake_post_line_message(token, payload):
        sent["token"] = token
        sent["payload"] = payload
        return 200

    monkeypatch.setattr(notify, "_post_line_message", fake_post_line_message)
    result = notify.notify_new_pending_problem(
        patient_label="MaskedPatient01",
        bed="1",
        created_by="DoctorA",
        created_at="2026-05-03T00:00:00",
        problem_content="SecretProblemContent",
    )

    assert result.sent
    assert result.channel == "line"
    text = sent["payload"]["messages"][0]["text"]
    assert "MaskedPatient01" in text
    assert "SecretProblemContent" not in text


def test_line_notification_includes_problem_content_when_enabled(monkeypatch):
    _clear_notification_env(monkeypatch)
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "token")
    monkeypatch.setenv("LINE_TO_ID", "group-id")
    monkeypatch.setenv("LINE_INCLUDE_PROBLEM_CONTENT", "1")
    monkeypatch.setattr(notify, "audit_payload", lambda **kwargs: kwargs)
    sent = {}

    def fake_post_line_message(token, payload):
        sent["payload"] = payload
        return 200

    monkeypatch.setattr(notify, "_post_line_message", fake_post_line_message)
    result = notify.notify_new_pending_problem(
        patient_label="MaskedPatient01",
        bed="1",
        created_by="DoctorA",
        created_at="2026-05-03T00:00:00",
        problem_content="SecretProblemContent",
    )

    assert result.sent
    assert "SecretProblemContent" in sent["payload"]["messages"][0]["text"]
