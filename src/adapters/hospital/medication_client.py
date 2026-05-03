from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from src.adapters.hospital.csv_utils import (
    in_requested_window,
    normalize_year_month,
    pick,
    read_hospital_csv,
    requested_chart_set,
)

STANDARD_MEDICATION_COLUMNS = [
    "chart_no",
    "deid",
    "name",
    "year_month",
    "order_code",
    "drug_name",
    "dose",
    "unit",
    "frequency",
    "drug_class",
    "source",
    "source_record_id",
    "start_date",
    "end_date",
    "status",
    "synced_at",
]


def fetch_medications(
    *,
    chart_nos: Iterable[str] | None = None,
    start_date: str = "",
    end_date: str = "",
    csv_path: Path | str | None = None,
    source: str = "hospital_csv",
) -> list[dict[str, str]]:
    """Fetch medication/order rows from the configured hospital source."""

    path = Path(csv_path or os.getenv("HOSPITAL_MEDICATION_CSV", "")).expanduser()
    if path and str(path) != ".":
        return fetch_medications_from_csv(
            path,
            chart_nos=chart_nos,
            start_date=start_date,
            end_date=end_date,
            source=source,
        )
    raise NotImplementedError(
        "TODO(HIS): set HOSPITAL_MEDICATION_CSV for CSV bridge or implement hospital medication REST/FHIR adapter"
    )


def fetch_medications_from_csv(
    path: Path | str,
    *,
    chart_nos: Iterable[str] | None = None,
    start_date: str = "",
    end_date: str = "",
    source: str = "hospital_csv",
) -> list[dict[str, str]]:
    chart_filter = requested_chart_set(chart_nos)
    records: list[dict[str, str]] = []
    for _, row in read_hospital_csv(path).iterrows():
        chart_no = pick(row, ["chart_no", "mrn", "medical_record_no", "pat_no", "病歷號"])
        if chart_filter and chart_no not in chart_filter:
            continue
        order_date = pick(row, ["order_date", "start_date", "開始日", "開立日"])
        if not in_requested_window(order_date, start_date, end_date):
            continue
        drug_name = pick(row, ["drug_name", "medication_name", "order_name", "藥名", "醫囑名稱"])
        if not chart_no or not drug_name:
            continue
        drug_class = pick(row, ["drug_class", "class", "類別"]) or _infer_drug_class(drug_name)
        records.append({
            "chart_no": chart_no,
            "deid": pick(row, ["deid"]),
            "name": pick(row, ["name", "patient_name", "姓名"]),
            "year_month": normalize_year_month(pick(row, ["year_month", "yyyymm"]), order_date),
            "order_code": pick(row, ["order_code", "drug_code", "medication_code", "醫令碼", "藥品碼"]),
            "drug_name": drug_name,
            "dose": pick(row, ["dose", "dosage", "劑量"]),
            "unit": pick(row, ["unit", "dose_unit", "dosage_unit", "單位"]),
            "frequency": pick(row, ["frequency", "freq", "頻率"]),
            "drug_class": drug_class,
            "source": pick(row, ["source"], source) or source,
            "source_record_id": pick(row, ["source_record_id", "order_no", "prescription_no"]),
            "start_date": order_date,
            "end_date": pick(row, ["end_date", "stop_date", "結束日", "停用日"]),
            "status": pick(row, ["status", "order_status", "狀態"]),
            "synced_at": "",
        })
    return records


def _infer_drug_class(drug_name: str) -> str:
    text = drug_name.upper()
    if any(token in text for token in ("EPO", "DARBE", "MIRCERA", "EPOETIN")):
        return "ESA"
    if any(token in text for token in ("VENOFER", "FERRIC", "IRON")):
        return "IRON_IV"
    if any(token in text for token in ("CALCIUM CARBONATE", "CALCIUM ACETATE")):
        return "CALCIUM_BINDER"
    if any(token in text for token in ("SEVELAMER", "LANTHANUM", "VELPHORO")):
        return "NON_CALCIUM_BINDER"
    if any(token in text for token in ("LOKELMA", "KAYEXALATE", "K BINDER")):
        return "K_BINDER"
    if any(token in text for token in ("CINACALCET", "CALCITRIOL", "PARICALCITOL")):
        return "PTH"
    return "OTHER"
