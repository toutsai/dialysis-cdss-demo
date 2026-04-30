from src.domain.entities import Patient, Shift
from scripts.export_nocodb_csv import _deid_rows, _dialysis_order_rows, _hospital_drug_rows, _patient_rows, _problem_list_rows, _staff_rows
from src.domain.entities import DialysisSchedule


def test_patient_rows_include_deid_and_workflow_fields():
    rows = _patient_rows([
        Patient(chart_no="12345A", name="測試病人", frequency="一三五", shift=Shift.MORNING, bed="1")
    ], exported_at="2026-04-27T00:00:00")
    assert rows[0]["deid"].startswith("P")
    assert rows[0]["shift"] == "早班"
    assert rows[0]["last_synced_at"] == "2026-04-27T00:00:00"


def test_deid_rows_keep_local_mapping():
    rows = _deid_rows([
        Patient(chart_no="12345A", name="測試病人", frequency="一三五", shift=Shift.MORNING)
    ], created_at="2026-04-27T00:00:00")
    assert rows == [{
        "chart_no": "12345A",
        "deid": rows[0]["deid"],
        "created_at": "2026-04-27T00:00:00",
    }]


def test_problem_list_rows_start_blank_but_link_patient():
    rows = _problem_list_rows([
        Patient(chart_no="12345A", name="測試病人", frequency="一三五", shift=Shift.MORNING)
    ], exported_at="2026-04-27T00:00:00")
    assert rows[0]["problem"] == ""
    assert rows[0]["problem_categories"] == '["現在待處理問題"]'
    assert rows[0]["status"] == "Active"
    assert rows[0]["owner_role"] == "護理師"
    assert "priority" not in rows[0]


def test_dialysis_order_rows_seed_from_schedule():
    rows = _dialysis_order_rows([
        DialysisSchedule(
            chart_no="12345A",
            name="測試病人",
            frequency="一三五",
            shift=Shift.MORNING,
            bed="1",
            dialyzer="FX80",
            dialysate_ca="3.0",
        )
    ], exported_at="2026-04-27T00:00:00")
    assert rows[0]["dialyzer"] == "FX80"
    assert rows[0]["dialysate_ca"] == "3.0"
    assert rows[0]["blood_flow"] == ""


def test_staff_rows_have_active_people():
    rows = _staff_rows()
    assert rows
    assert {"staff_id", "name", "role", "active", "note"} <= set(rows[0])


def test_hospital_drug_rows_have_requested_types():
    rows = _hospital_drug_rows()
    types = {row["drug_type"] for row in rows}
    assert {"ESA", "降磷藥", "降鉀藥", "副甲狀腺亢進藥物"} <= types
