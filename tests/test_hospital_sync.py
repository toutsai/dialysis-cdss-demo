from pathlib import Path

import pandas as pd

from src import db
from src.adapters.hospital.lab_client import fetch_labs_from_csv
from src.adapters.hospital.medication_client import fetch_medications_from_csv
from src.services.hospital_sync import sync_hospital_data


def test_lab_csv_adapter_normalizes_common_columns(tmp_path: Path):
    csv_path = tmp_path / "labs.csv"
    pd.DataFrame([{
        "mrn": "A001",
        "lab_code": "HGB",
        "result": "10.2",
        "result_unit": "g/dL",
        "report_date": "2026-04-15",
    }]).to_csv(csv_path, index=False, encoding="utf-8-sig")

    rows = fetch_labs_from_csv(csv_path, chart_nos=["A001"], start_date="2026-04-01", end_date="2026-04-30")

    assert rows[0]["chart_no"] == "A001"
    assert rows[0]["item_key"] == "Hb"
    assert rows[0]["year_month"] == "202604"
    assert rows[0]["value"] == "10.2"


def test_medication_csv_adapter_infers_drug_class(tmp_path: Path):
    csv_path = tmp_path / "medications.csv"
    pd.DataFrame([{
        "chart_no": "A001",
        "drug_name": "Darbepoetin alfa",
        "dose": "40",
        "frequency": "QW",
        "start_date": "2026-04-01",
    }]).to_csv(csv_path, index=False, encoding="utf-8-sig")

    rows = fetch_medications_from_csv(csv_path)

    assert rows[0]["drug_class"] == "ESA"
    assert rows[0]["year_month"] == "202604"


def test_hospital_sync_defaults_to_lab_only(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "hospital.sqlite"
    lab_csv = tmp_path / "labs.csv"
    med_csv = tmp_path / "medications.csv"
    monkeypatch.setenv("DIALYSIS_CDSS_DB_PATH", str(db_path))

    with db.connect(db_path) as conn:
        pd.DataFrame([{
            "chart_no": "A001",
            "deid": "P000001",
            "name": "Demo Patient",
            "frequency": "135",
            "shift": "AM",
            "bed": "1",
            "identity": "",
            "active": "True",
            "source": "test",
            "last_synced_at": "",
        }]).to_sql("patients", conn, if_exists="replace", index=False)
        db._ensure_patient_columns(conn)

    pd.DataFrame([{
        "chart_no": "A001",
        "item_key": "Hb",
        "value": "10.2",
        "unit": "g/dL",
        "report_date": "2026-04-15",
    }]).to_csv(lab_csv, index=False, encoding="utf-8-sig")
    pd.DataFrame([{
        "chart_no": "A001",
        "drug_name": "Darbepoetin alfa",
        "dose": "40",
        "frequency": "QW",
        "start_date": "2026-04-01",
    }]).to_csv(med_csv, index=False, encoding="utf-8-sig")

    summary = sync_hospital_data(lab_csv=lab_csv, medication_csv=med_csv)

    assert summary.lab_count == 1
    assert summary.medication_count == 0
    detail = db.patient_detail("A001")
    assert detail["lab_results"].iloc[0]["item_key"] == "Hb"
    assert detail["lab_results"].iloc[0]["deid"] == "P000001"
    assert detail["medications"].empty


def test_hospital_sync_can_opt_in_to_medications(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "hospital.sqlite"
    lab_csv = tmp_path / "labs.csv"
    med_csv = tmp_path / "medications.csv"
    monkeypatch.setenv("DIALYSIS_CDSS_DB_PATH", str(db_path))

    with db.connect(db_path) as conn:
        pd.DataFrame([{
            "chart_no": "A001",
            "deid": "P000001",
            "name": "Demo Patient",
            "frequency": "135",
            "shift": "AM",
            "bed": "1",
            "identity": "",
            "active": "True",
            "source": "test",
            "last_synced_at": "",
        }]).to_sql("patients", conn, if_exists="replace", index=False)
        db._ensure_patient_columns(conn)

    pd.DataFrame([{
        "chart_no": "A001",
        "item_key": "Hb",
        "value": "10.2",
        "unit": "g/dL",
        "report_date": "2026-04-15",
    }]).to_csv(lab_csv, index=False, encoding="utf-8-sig")
    pd.DataFrame([{
        "chart_no": "A001",
        "drug_name": "Darbepoetin alfa",
        "dose": "40",
        "frequency": "QW",
        "start_date": "2026-04-01",
    }]).to_csv(med_csv, index=False, encoding="utf-8-sig")

    summary = sync_hospital_data(lab_csv=lab_csv, medication_csv=med_csv, sync_medications=True)

    assert summary.lab_count == 1
    assert summary.medication_count == 1
    detail = db.patient_detail("A001")
    assert detail["medications"].iloc[0]["drug_class"] == "ESA"
