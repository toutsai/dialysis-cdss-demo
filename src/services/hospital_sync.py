from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from src import db
from src.adapters.hospital.lab_client import STANDARD_LAB_COLUMNS, fetch_labs
from src.adapters.hospital.medication_client import STANDARD_MEDICATION_COLUMNS, fetch_medications
from src.audit import audit_payload


@dataclass(frozen=True)
class HospitalSyncSummary:
    source: str
    start_date: str = ""
    end_date: str = ""
    lab_count: int = 0
    medication_count: int = 0
    skipped: list[str] = field(default_factory=list)
    synced_at: str = ""


def sync_hospital_data(
    *,
    chart_nos: Iterable[str] | None = None,
    start_date: str = "",
    end_date: str = "",
    lab_csv: Path | str | None = None,
    medication_csv: Path | str | None = None,
    sync_medications: bool = False,
    source: str = "hospital_csv",
) -> HospitalSyncSummary:
    """Synchronize hospital data into local CDSS tables.

    This service is the stable boundary for HIS/LIS integration. Future API
    clients should return rows with the same normalized columns, then this
    function can persist them without changing Streamlit or the rule engine.

    Labs are the default sync target. Medication sync is intentionally opt-in
    because dialysis medication orders may be easier and safer to maintain from
    the CDSS front end during the first deployment.
    """

    db.ensure_database()
    synced_at = datetime.now().isoformat(timespec="seconds")
    skipped: list[str] = []

    lab_rows = _fetch_or_skip(
        "labs",
        lambda: fetch_labs(
            chart_nos=chart_nos,
            start_date=start_date,
            end_date=end_date,
            csv_path=lab_csv,
            source=source,
        ),
        skipped,
    )
    medication_rows: list[dict[str, str]] = []
    if sync_medications:
        medication_rows = _fetch_or_skip(
            "medications",
            lambda: fetch_medications(
                chart_nos=chart_nos,
                start_date=start_date,
                end_date=end_date,
                csv_path=medication_csv,
                source=source,
            ),
            skipped,
        )

    lab_frame = _prepare_frame(lab_rows, STANDARD_LAB_COLUMNS, synced_at)
    medication_frame = _prepare_frame(medication_rows, STANDARD_MEDICATION_COLUMNS, synced_at)
    lab_frame = _fill_patient_labels(lab_frame)
    medication_frame = _fill_patient_labels(medication_frame)

    lab_count = db.replace_synced_labs(lab_frame, source=source) if not lab_frame.empty else 0
    medication_count = (
        db.replace_synced_medications(medication_frame, source=source) if not medication_frame.empty else 0
    )

    summary = HospitalSyncSummary(
        source=source,
        start_date=start_date,
        end_date=end_date,
        lab_count=lab_count,
        medication_count=medication_count,
        skipped=skipped,
        synced_at=synced_at,
    )
    audit_payload(
        service="hospital_sync",
        model=source,
        payload={
            "chart_no_count": len({str(chart_no).strip() for chart_no in chart_nos or [] if str(chart_no).strip()}),
            "start_date": start_date,
            "end_date": end_date,
            "sync_medications": sync_medications,
            "skipped": skipped,
        },
        response=asdict(summary),
        status="ok",
    )
    return summary


def _fetch_or_skip(name: str, fetcher, skipped: list[str]) -> list[dict[str, str]]:
    try:
        return fetcher()
    except NotImplementedError as exc:
        skipped.append(f"{name}: {exc}")
        return []


def _prepare_frame(rows: list[dict[str, str]], columns: list[str], synced_at: str) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=columns)
    for col in columns:
        if col not in frame.columns:
            frame[col] = ""
    frame["synced_at"] = synced_at
    return frame[columns].fillna("")


def _fill_patient_labels(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows
    try:
        patients = db.patients().fillna("")
    except Exception:
        return rows
    lookup = {
        str(row.get("chart_no", "")).strip(): {
            "deid": str(row.get("deid", "")).strip(),
            "name": str(row.get("name", "")).strip(),
        }
        for row in patients.to_dict("records")
    }
    rows = rows.copy()
    for idx, row in rows.iterrows():
        chart_no = str(row.get("chart_no", "")).strip()
        patient = lookup.get(chart_no, {})
        if not str(row.get("deid", "")).strip():
            rows.at[idx, "deid"] = patient.get("deid", "")
        if not str(row.get("name", "")).strip():
            rows.at[idx, "name"] = patient.get("name", "")
    return rows
