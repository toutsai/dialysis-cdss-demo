from src.domain.entities import LabResult
from src.domain.rules import Thresholds, evaluate_month


def test_hb_low_generates_recommendation():
    recs = evaluate_month(
        chart_no="12345A",
        year_month="202604",
        labs=[LabResult(chart_no="12345A", year_month="202604", item_key="Hb", value=9.2)],
        medications=[],
        thresholds=Thresholds(),
    )
    assert any(rec.rule_id == "esa.hb_low" for rec in recs)


def test_no_labs_no_recommendation():
    recs = evaluate_month(
        chart_no="12345A",
        year_month="202604",
        labs=[],
        medications=[],
        thresholds=Thresholds(),
    )
    assert recs == []
