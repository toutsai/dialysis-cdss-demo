from src.domain.dose_adjustment import build_dose_adjustments
from src.domain.entities import LabResult, Medication
from src.settings import load_dose_rules


def test_esa_high_hb_decreases_dose():
    rules = load_dose_rules()
    suggestions = build_dose_adjustments(
        labs=[LabResult("1", "202604", "Hb", 12.0)],
        medications=[Medication("1", "202604", "ESA", "Darbepoetin alfa", "60", "QW", "ESA")],
        rules=rules,
    )
    assert any(s.drug_class == "ESA" and s.action == "decrease" for s in suggestions)


def test_low_iron_suggests_supplement():
    rules = load_dose_rules()
    suggestions = build_dose_adjustments(
        labs=[
            LabResult("1", "202604", "Ferritin", 80),
            LabResult("1", "202604", "TSAT", 18),
        ],
        medications=[],
        rules=rules,
    )
    assert any(s.drug_class == "IRON" and s.action == "supplement" for s in suggestions)


def test_mbd_high_p_and_high_ca_with_calcium_binder_suggests_switch():
    rules = load_dose_rules()
    suggestions = build_dose_adjustments(
        labs=[
            LabResult("1", "202604", "P", 6.4),
            LabResult("1", "202604", "cCa", 10.6),
            LabResult("1", "202604", "CaXP", 68),
        ],
        medications=[Medication("1", "202604", "PB", "Calcium carbonate", "1#", "TIDCC", "CALCIUM_BINDER")],
        rules=rules,
    )
    assert any(s.drug_class == "CKD-MBD" and s.action == "decrease_or_switch_binder" for s in suggestions)
