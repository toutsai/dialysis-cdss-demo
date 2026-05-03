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

STANDARD_LAB_COLUMNS = [
    "chart_no",
    "deid",
    "name",
    "year_month",
    "item_key",
    "value",
    "unit",
    "report_date",
    "source",
    "source_record_id",
    "synced_at",
]

LAB_ITEM_ALIASES = {
    "ALB": "Albumin",
    "ALBUMIN": "Albumin",
    "CA": "Ca",
    "CALCIUM": "Ca",
    "CAXP": "CaXP",
    "CA*P": "CaXP",
    "FERRITIN": "Ferritin",
    "HB": "Hb",
    "HGB": "Hb",
    "HEMOGLOBIN": "Hb",
    "P": "P",
    "PHOS": "P",
    "PHOSPHORUS": "P",
    "IPTH": "iPTH",
    "PTH": "iPTH",
    "TSAT": "TSAT",
    "TRANSFERRIN SATURATION": "TSAT",
}


def fetch_labs(
    *,
    chart_nos: Iterable[str] | None = None,
    start_date: str = "",
    end_date: str = "",
    csv_path: Path | str | None = None,
    source: str = "hospital_csv",
) -> list[dict[str, str]]:
    """Fetch lab rows from the configured hospital source.

    First production milestone can use a CSV/SFTP bridge by setting
    HOSPITAL_LAB_CSV. When the hospital provides REST/FHIR specs, replace this
    function body or add a sibling API adapter that returns the same records.
    """

    path = Path(csv_path or os.getenv("HOSPITAL_LAB_CSV", "")).expanduser()
    if path and str(path) != ".":
        return fetch_labs_from_csv(
            path,
            chart_nos=chart_nos,
            start_date=start_date,
            end_date=end_date,
            source=source,
        )
    raise NotImplementedError(
        "TODO(HIS): set HOSPITAL_LAB_CSV for CSV bridge or implement hospital lab REST/FHIR adapter"
    )


def fetch_labs_from_csv(
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
        report_date = pick(row, ["report_date", "result_date", "report_time", "報告日", "報告日期"])
        if not in_requested_window(report_date, start_date, end_date):
            continue
        item_key = _normalize_lab_item(
            pick(row, ["item_key", "item_code", "lab_code", "test_code", "檢驗代碼"])
            or pick(row, ["item_name", "lab_name", "test_name", "檢驗名稱", "檢驗項目"])
        )
        if not chart_no or not item_key:
            continue
        records.append({
            "chart_no": chart_no,
            "deid": pick(row, ["deid"]),
            "name": pick(row, ["name", "patient_name", "姓名"]),
            "year_month": normalize_year_month(pick(row, ["year_month", "yyyymm"]), report_date),
            "item_key": item_key,
            "value": pick(row, ["value", "result_value", "result", "結果值", "數值"]),
            "unit": pick(row, ["unit", "result_unit", "單位"]),
            "report_date": report_date,
            "source": pick(row, ["source"], source) or source,
            "source_record_id": pick(row, ["source_record_id", "accession_no", "order_no", "specimen_no"]),
            "synced_at": "",
        })
    return records


def _normalize_lab_item(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return LAB_ITEM_ALIASES.get(text.upper(), text)
