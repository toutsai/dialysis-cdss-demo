from src.domain.entities import LabResult
from src.domain.trend_recommendation import (
    DialysisOrderTrendRecord,
    MedicationTrendRecord,
    build_trend_recommendations,
    medication_exposure_points,
)


DOSE_RULES = {
    "esa": {
        "hb_low": 10.0,
        "hb_high": 11.5,
        "hold_if_hb_above": 12.5,
        "require_iron_replete_before_increase": True,
        "ferritin_replete_min": 100,
        "tsat_replete_min": 20,
    },
    "mbd": {
        "phosphate_high": 5.5,
        "ipth_high": 600,
    },
}


def test_hb_falling_without_esa_increase_suggests_esa_increase():
    suggestions = build_trend_recommendations(
        selected_month="202605",
        labs=[
            LabResult("1", "202603", "Hb", 10.4),
            LabResult("1", "202604", "Hb", 10.1),
            LabResult("1", "202605", "Hb", 9.8),
            LabResult("1", "202605", "Ferritin", 200),
            LabResult("1", "202605", "TSAT", 25),
        ],
        medications=[
            MedicationTrendRecord("1", "202603", "ESA", "Darbepoetin alfa", "20", "mcg", "QW"),
            MedicationTrendRecord("1", "202604", "ESA", "Darbepoetin alfa", "20", "mcg", "QW"),
            MedicationTrendRecord("1", "202605", "ESA", "Darbepoetin alfa", "20", "mcg", "QW"),
        ],
        dialysis_orders=[],
        dose_rules=DOSE_RULES,
    )

    assert any(s.group == "anemia" and s.action == "increase" for s in suggestions)


def test_esa_increase_with_hb_response_suggests_observation():
    suggestions = build_trend_recommendations(
        selected_month="202605",
        labs=[
            LabResult("1", "202603", "Hb", 9.5),
            LabResult("1", "202604", "Hb", 9.7),
            LabResult("1", "202605", "Hb", 9.9),
            LabResult("1", "202605", "Ferritin", 200),
            LabResult("1", "202605", "TSAT", 25),
        ],
        medications=[
            MedicationTrendRecord("1", "202603", "ESA", "Darbepoetin alfa", "20", "mcg", "QW"),
            MedicationTrendRecord("1", "202604", "ESA", "Darbepoetin alfa", "40", "mcg", "QW"),
            MedicationTrendRecord("1", "202605", "ESA", "Darbepoetin alfa", "40", "mcg", "QW"),
        ],
        dialysis_orders=[],
        dose_rules=DOSE_RULES,
    )

    anemia = [s for s in suggestions if s.group == "anemia"]
    assert anemia[0].action == "observe_after_response"
    assert not anemia[0].actionable


def test_esa_large_increase_with_poor_hb_response_suggests_reassessment():
    suggestions = build_trend_recommendations(
        selected_month="202605",
        labs=[
            LabResult("1", "202603", "Hb", 9.8),
            LabResult("1", "202604", "Hb", 9.8),
            LabResult("1", "202605", "Hb", 9.9),
            LabResult("1", "202605", "Ferritin", 200),
            LabResult("1", "202605", "TSAT", 25),
        ],
        medications=[
            MedicationTrendRecord("1", "202603", "ESA", "Darbepoetin alfa", "20", "mcg", "QW"),
            MedicationTrendRecord("1", "202604", "ESA", "Darbepoetin alfa", "40", "mcg", "QW"),
            MedicationTrendRecord("1", "202605", "ESA", "Darbepoetin alfa", "40", "mcg", "QW"),
        ],
        dialysis_orders=[],
        dose_rules=DOSE_RULES,
    )

    assert any(s.group == "anemia" and s.action == "increase_after_insufficient_response" for s in suggestions)


def test_phosphate_rising_with_unchanged_binder_suggests_phosphate_strategy():
    suggestions = build_trend_recommendations(
        selected_month="202605",
        labs=[
            LabResult("1", "202603", "P", 5.0),
            LabResult("1", "202604", "P", 5.4),
            LabResult("1", "202605", "P", 5.8),
        ],
        medications=[
            MedicationTrendRecord("1", "202603", "CALCIUM_BINDER", "Calcium carbonate", "1", "tab", "TID with meals"),
            MedicationTrendRecord("1", "202604", "CALCIUM_BINDER", "Calcium carbonate", "1", "tab", "TID with meals"),
            MedicationTrendRecord("1", "202605", "CALCIUM_BINDER", "Calcium carbonate", "1", "tab", "TID with meals"),
        ],
        dialysis_orders=[],
        dose_rules=DOSE_RULES,
    )

    assert any(s.group == "mbd" and s.action == "intensify_phosphate_control" for s in suggestions)


def test_adequacy_falling_without_order_change_suggests_dialysis_order_review():
    suggestions = build_trend_recommendations(
        selected_month="202605",
        labs=[
            LabResult("1", "202603", "Kt/V", 1.35),
            LabResult("1", "202604", "Kt/V", 1.25),
            LabResult("1", "202605", "Kt/V", 1.15),
            LabResult("1", "202603", "URR", 70),
            LabResult("1", "202604", "URR", 67),
            LabResult("1", "202605", "URR", 64),
        ],
        medications=[],
        dialysis_orders=[
            DialysisOrderTrendRecord("1", "202603", dialyzer="Rex25A", blood_flow="250", dialysate_flow="500"),
            DialysisOrderTrendRecord("1", "202604", dialyzer="Rex25A", blood_flow="250", dialysate_flow="500"),
            DialysisOrderTrendRecord("1", "202605", dialyzer="Rex25A", blood_flow="250", dialysate_flow="500"),
        ],
        dose_rules=DOSE_RULES,
    )

    adequacy = [s for s in suggestions if s.group == "adequacy"]
    assert adequacy[0].action == "adjust_dialysis_order"
    assert adequacy[0].target_tab == "透析醫囑"


def test_frequency_parser_calculates_monthly_exposure():
    points = medication_exposure_points(
        [
            MedicationTrendRecord("1", "202605", "ESA", "Darbepoetin alfa", "40", "mcg", "QW"),
            MedicationTrendRecord("1", "202606", "ESA", "Darbepoetin alfa", "40", "mcg", "Q2W"),
            MedicationTrendRecord("1", "202607", "ESA", "Darbepoetin alfa", "1", "tab", "TID with meals"),
        ],
        ["202605", "202606", "202607"],
        {"ESA"},
    )

    assert points[0].value == 160
    assert points[1].value == 80
    assert points[2].value == 90
