from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd


def read_hospital_csv(path: Path | str) -> pd.DataFrame:
    return pd.read_csv(Path(path), dtype=str, keep_default_na=False, encoding="utf-8-sig").fillna("")


def pick(row: pd.Series, names: Iterable[str], default: str = "") -> str:
    lower_index = {str(col).strip().lower(): col for col in row.index}
    for name in names:
        col = lower_index.get(name.strip().lower())
        if col is not None:
            return str(row.get(col, default)).strip()
    return default


def normalize_year_month(value: object, fallback_date: object = "") -> str:
    text = str(value or "").strip()
    if len(text) >= 6 and text[:6].isdigit():
        return text[:6]
    return date_to_year_month(fallback_date)


def date_to_year_month(value: object) -> str:
    parsed = parse_date(value)
    return parsed.strftime("%Y%m") if parsed else ""


def parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def in_requested_window(value: object, start_date: str = "", end_date: str = "") -> bool:
    parsed = parse_date(value)
    if not parsed:
        return True
    start = parse_date(start_date)
    end = parse_date(end_date)
    if start and parsed < start:
        return False
    if end and parsed > end:
        return False
    return True


def requested_chart_set(chart_nos: Iterable[str] | None) -> set[str]:
    return {str(chart_no).strip() for chart_no in chart_nos or [] if str(chart_no).strip()}
