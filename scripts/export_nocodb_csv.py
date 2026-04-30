from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any
import hashlib

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.adapters.patient_source_excel import load_schedule_workbook
from src.domain.deidentify import stable_deid
from src.domain.entities import DialysisSchedule, Patient


def main() -> None:
    _load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Export NocoDB seed CSV files from schedule workbook")
    parser.add_argument("--schedule-xlsx", default=os.getenv("SCHEDULE_XLSX"))
    parser.add_argument("--out-dir", default=str(ROOT / "exports" / "nocodb_seed"))
    args = parser.parse_args()

    if not args.schedule_xlsx:
        raise SystemExit("SCHEDULE_XLSX is required. Set it in .env or pass --schedule-xlsx.")

    result = load_schedule_workbook(Path(args.schedule_xlsx))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    exported_at = datetime.now().isoformat(timespec="seconds")
    _write_csv(out_dir / "patients.csv", _patient_rows(result.patients, exported_at))
    _write_csv(out_dir / "dialysis_schedule.csv", _schedule_rows(result.schedules))
    _write_csv(out_dir / "deid_map.csv", _deid_rows(result.patients, exported_at))
    _write_csv(out_dir / "problem_list.csv", _problem_list_rows(result.patients, exported_at))
    _write_csv(out_dir / "clinical_events.csv", _clinical_event_rows(result.patients, exported_at))
    _write_csv(out_dir / "dialysis_orders.csv", _dialysis_order_rows(result.schedules, exported_at))
    labs = _mock_lab_rows(result.patients, year_month="202604")
    meds = _mock_medication_rows(result.patients, year_month="202604")
    _write_csv(out_dir / "lab_results.csv", labs)
    _write_csv(out_dir / "medications.csv", meds)
    _write_csv(out_dir / "recommendations.csv", _recommendation_rows(result.patients, year_month="202604", exported_at=exported_at))
    _write_csv(out_dir / "staff.csv", _staff_rows())
    _write_csv(out_dir / "hospital_drugs.csv", _hospital_drug_rows())

    print(f"exported patients: {len(result.patients)}")
    print(f"exported schedules: {len(result.schedules)}")
    print("exported workflow templates: problem_list, clinical_events, dialysis_orders")
    print("exported mock clinical data: lab_results, medications, recommendations")
    print("exported admin templates: staff")
    print("exported medication templates: hospital_drugs")
    print(f"output: {out_dir}")


def _patient_rows(patients: list[Patient], exported_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in patients:
        rows.append({
            "chart_no": p.chart_no,
            "deid": stable_deid(p.chart_no),
            "name": p.name,
            "frequency": p.frequency,
            "shift": p.shift.value,
            "bed": p.bed or "",
            "identity": p.identity,
            "active": p.active,
            "source": p.source,
            "last_synced_at": exported_at,
        })
    return rows


def _schedule_rows(schedules: list[DialysisSchedule]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for s in schedules:
        rows.append({
            "chart_no": s.chart_no,
            "deid": stable_deid(s.chart_no),
            "name": s.name,
            "frequency": s.frequency,
            "shift": s.shift.value,
            "bed": s.bed or "",
            "dialyzer": s.dialyzer or "",
            "dialysate_ca": s.dialysate_ca or "",
            "source_sheet": s.source_sheet,
            "source_updated_at": s.source_updated_at.isoformat(timespec="seconds") if s.source_updated_at else "",
        })
    return rows


def _deid_rows(patients: list[Patient], created_at: str) -> list[dict[str, Any]]:
    return [
        {"chart_no": p.chart_no, "deid": stable_deid(p.chart_no), "created_at": created_at}
        for p in patients
    ]


def _problem_list_rows(patients: list[Patient], exported_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in patients:
        rows.append({
            "chart_no": p.chart_no,
            "deid": stable_deid(p.chart_no),
            "name": p.name,
            "problem": "",
            "problem_categories": '["現在待處理問題"]',
            "status": "Active",
            "owner_role": "護理師",
            "updated_by": "",
            "updated_at": exported_at,
            "note": "",
        })
    return rows


def _clinical_event_rows(patients: list[Patient], exported_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in patients:
        rows.append({
            "chart_no": p.chart_no,
            "deid": stable_deid(p.chart_no),
            "name": p.name,
            "event_type": "",
            "event_date": "",
            "title": "",
            "event_content": "",
            "source": "manual",
            "updated_by": "",
            "updated_at": exported_at,
            "note": "",
        })
    return rows


def _dialysis_order_rows(schedules: list[DialysisSchedule], exported_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for s in schedules:
        rows.append({
            "chart_no": s.chart_no,
            "deid": stable_deid(s.chart_no),
            "name": s.name,
            "order_month": "",
            "dialyzer": s.dialyzer or "",
            "dialysate_ca": s.dialysate_ca or "",
            "blood_flow": "",
            "dry_weight": "",
            "anticoagulant": "",
            "vascular_access": "",
            "updated_by": "",
            "updated_at": exported_at,
            "note": "",
        })
    return rows


def _mock_lab_rows(patients: list[Patient], year_month: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in patients:
        seed = _stable_int(p.chart_no)
        hb = round(9.0 + (seed % 38) / 10, 1)
        ferritin = 60 + (seed // 3) % 520
        tsat = 12 + (seed // 5) % 36
        phosphate = round(3.4 + ((seed // 7) % 42) / 10, 1)
        ca = round(8.3 + ((seed // 11) % 24) / 10, 1)
        albumin = round(3.1 + ((seed // 13) % 14) / 10, 1)
        cca = round(ca + 0.8 * (4.0 - albumin), 2)
        caxp = round(cca * phosphate, 1)
        ipth = 120 + (seed // 17) % 820
        values = {
            "Hb": (hb, "g/dL"),
            "Ferritin": (float(ferritin), "ng/mL"),
            "TSAT": (float(tsat), "%"),
            "P": (phosphate, "mg/dL"),
            "Ca": (ca, "mg/dL"),
            "Albumin": (albumin, "g/dL"),
            "cCa": (cca, "mg/dL"),
            "CaXP": (caxp, ""),
            "iPTH": (float(ipth), "pg/mL"),
        }
        for item_key, (value, unit) in values.items():
            rows.append({
                "chart_no": p.chart_no,
                "deid": stable_deid(p.chart_no),
                "name": p.name,
                "year_month": year_month,
                "item_key": item_key,
                "value": value,
                "unit": unit,
                "report_date": f"{year_month[:4]}-{year_month[4:]}-15",
                "source": "mock",
            })
    return rows


def _mock_medication_rows(patients: list[Patient], year_month: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in patients:
        seed = _stable_int(p.chart_no)
        rows.append({
            "chart_no": p.chart_no,
            "deid": stable_deid(p.chart_no),
            "name": p.name,
            "year_month": year_month,
            "order_code": "ESA-MOCK",
            "drug_name": "Darbepoetin alfa",
            "dose": str(20 + (seed % 5) * 10),
            "frequency": "QW",
            "drug_class": "ESA",
            "source": "mock",
        })
        if seed % 3 == 0:
            rows.append({
                "chart_no": p.chart_no,
                "deid": stable_deid(p.chart_no),
                "name": p.name,
                "year_month": year_month,
                "order_code": "IRON-MOCK",
                "drug_name": "Venofer",
                "dose": "100mg",
                "frequency": "Q2W",
                "drug_class": "IRON_IV",
                "source": "mock",
            })
        if seed % 2 == 0:
            rows.append({
                "chart_no": p.chart_no,
                "deid": stable_deid(p.chart_no),
                "name": p.name,
                "year_month": year_month,
                "order_code": "PBINDER-MOCK",
                "drug_name": "Calcium carbonate",
                "dose": "1#",
                "frequency": "TIDCC",
                "drug_class": "CALCIUM_BINDER",
                "source": "mock",
            })
    return rows


def _recommendation_rows(patients: list[Patient], year_month: str, exported_at: str) -> list[dict[str, Any]]:
    return [
        {
            "recommendation_id": "",
            "chart_no": p.chart_no,
            "deid": stable_deid(p.chart_no),
            "name": p.name,
            "year_month": year_month,
            "status": "draft",
            "severity": "",
            "rule_id": "",
            "title": "",
            "detail": "",
            "evidence_json": "",
            "claude_summary": "",
            "created_at": exported_at,
        }
        for p in patients
    ]


def _stable_int(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


def _staff_rows() -> list[dict[str, Any]]:
    created_at = datetime.now().isoformat(timespec="seconds")
    return [
        {"staff_id": "physician-1", "name": "醫師A", "role": "醫師", "active": "啟用", "created_by": "system", "created_at": created_at, "inactive_at": "", "note": "請改成實際人員"},
        {"staff_id": "head-nurse-1", "name": "護理長A", "role": "護理長", "active": "啟用", "created_by": "system", "created_at": created_at, "inactive_at": "", "note": "請改成實際人員"},
        {"staff_id": "nurse-1", "name": "護理師A", "role": "護理師", "active": "啟用", "created_by": "system", "created_at": created_at, "inactive_at": "", "note": "請改成實際人員"},
        {"staff_id": "nurse-2", "name": "護理師B", "role": "護理師", "active": "啟用", "created_by": "system", "created_at": created_at, "inactive_at": "", "note": "請改成實際人員"},
    ]


def _hospital_drug_rows() -> list[dict[str, Any]]:
    created_at = datetime.now().isoformat(timespec="seconds")
    return [
        {"drug_id": "esa-darbepoetin", "drug_type": "ESA", "drug_name": "Darbepoetin alfa", "default_unit": "mcg", "active": "啟用", "created_by": "system", "created_at": created_at, "inactive_at": "", "note": ""},
        {"drug_id": "esa-epoetin", "drug_type": "ESA", "drug_name": "Epoetin beta", "default_unit": "IU", "active": "啟用", "created_by": "system", "created_at": created_at, "inactive_at": "", "note": ""},
        {"drug_id": "phos-calcium-carbonate", "drug_type": "降磷藥", "drug_name": "Calcium carbonate", "default_unit": "tab", "active": "啟用", "created_by": "system", "created_at": created_at, "inactive_at": "", "note": ""},
        {"drug_id": "phos-sevelamer", "drug_type": "降磷藥", "drug_name": "Sevelamer", "default_unit": "tab", "active": "啟用", "created_by": "system", "created_at": created_at, "inactive_at": "", "note": ""},
        {"drug_id": "k-szc", "drug_type": "降鉀藥", "drug_name": "Sodium zirconium cyclosilicate", "default_unit": "g", "active": "啟用", "created_by": "system", "created_at": created_at, "inactive_at": "", "note": ""},
        {"drug_id": "shpt-cinacalcet", "drug_type": "副甲狀腺亢進藥物", "drug_name": "Cinacalcet", "default_unit": "mg", "active": "啟用", "created_by": "system", "created_at": created_at, "inactive_at": "", "note": ""},
    ]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    main()
