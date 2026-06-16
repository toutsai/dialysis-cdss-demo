from pathlib import Path

import pandas as pd
import pytest

from src import db
from src.services.hospital_inbox import scan_inbox


def _read_labs(db_path: Path, chart_no: str) -> pd.DataFrame:
    with db.connect(db_path) as conn:
        return pd.read_sql_query(
            "select * from lab_results where chart_no = ?", conn, params=[chart_no]
        ).fillna("")


def _seed_patient(db_path: Path) -> None:
    with db.connect(db_path) as conn:
        pd.DataFrame([{
            "chart_no": "A001",
            "deid": "P000001",
            "name": "Demo Patient",
            "active": "True",
            "source": "test",
        }]).to_sql("patients", conn, if_exists="replace", index=False)
        db._ensure_patient_columns(conn)


def _write_lab_csv(path: Path, value: str = "10.2") -> None:
    pd.DataFrame([{
        "mrn": "A001",
        "lab_code": "HGB",
        "result": value,
        "result_unit": "g/dL",
        "report_date": "2026-04-15",
    }]).to_csv(path, index=False, encoding="utf-8-sig")


def test_scan_ingests_and_archives_new_file(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "hospital.sqlite"
    monkeypatch.setenv("DIALYSIS_CDSS_DB_PATH", str(db_path))
    _seed_patient(db_path)

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    csv_path = inbox / "2026-04.csv"
    _write_lab_csv(csv_path)

    summary = scan_inbox(inbox, stable_seconds=0)

    assert len(summary.processed) == 1
    assert summary.processed[0].lab_count == 1
    assert not csv_path.exists()
    archived = list((inbox / "archive").glob("*__2026-04.csv"))
    assert len(archived) == 1
    labs = _read_labs(db_path, "A001")
    assert labs.iloc[0]["item_key"] == "Hb"


def test_unstable_file_is_skipped_then_processed(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "hospital.sqlite"
    monkeypatch.setenv("DIALYSIS_CDSS_DB_PATH", str(db_path))
    _seed_patient(db_path)

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    csv_path = inbox / "2026-04.csv"
    _write_lab_csv(csv_path)

    skipped = scan_inbox(inbox, stable_seconds=3600)
    assert len(skipped.skipped) == 1
    assert csv_path.exists()

    processed = scan_inbox(inbox, stable_seconds=0)
    assert len(processed.processed) == 1
    assert not csv_path.exists()


def test_bad_file_quarantined_to_failed(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "hospital.sqlite"
    monkeypatch.setenv("DIALYSIS_CDSS_DB_PATH", str(db_path))
    _seed_patient(db_path)

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    bad = inbox / "broken.csv"
    bad.write_bytes(b"")

    summary = scan_inbox(inbox, stable_seconds=0)

    assert len(summary.failed) == 1
    assert not bad.exists()
    assert len(list((inbox / "failed").glob("*__broken.csv"))) == 1


def test_reprocess_same_month_is_idempotent(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "hospital.sqlite"
    monkeypatch.setenv("DIALYSIS_CDSS_DB_PATH", str(db_path))
    _seed_patient(db_path)

    inbox = tmp_path / "inbox"
    inbox.mkdir()

    first = inbox / "2026-04.csv"
    _write_lab_csv(first, value="10.2")
    scan_inbox(inbox, stable_seconds=0)

    second = inbox / "2026-04-corrected.csv"
    _write_lab_csv(second, value="11.5")
    scan_inbox(inbox, stable_seconds=0)

    labs = _read_labs(db_path, "A001")
    hb = labs[labs["item_key"] == "Hb"]
    assert len(hb) == 1
    assert hb.iloc[0]["value"] == "11.5"


def test_missing_inbox_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        scan_inbox(tmp_path / "nope", stable_seconds=0)
