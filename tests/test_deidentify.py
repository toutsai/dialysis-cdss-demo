from src.domain.deidentify import redact_for_claude, stable_deid


def test_stable_deid_is_stable():
    assert stable_deid("12345A") == stable_deid("12345A")
    assert stable_deid("12345A").startswith("P")


def test_redact_for_claude_removes_identifiers():
    payload = {
        "chart_no": "12345A",
        "name": "測試病人",
        "bed": "12",
        "labs": {"Hb": 9.8},
    }
    redacted = redact_for_claude(payload)
    assert "chart_no" not in redacted
    assert "name" not in redacted
    assert "bed" not in redacted
    assert redacted["deid"].startswith("P")
    assert redacted["labs"]["Hb"] == 9.8
