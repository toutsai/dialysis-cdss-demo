from __future__ import annotations

import argparse
import os
from pathlib import Path

from src.adapters.patient_source_excel import load_schedule_workbook
from src.domain.deidentify import stable_deid
from src.services.notify import notify_pending_approvals


def main() -> None:
    _load_dotenv(Path(".env"))
    parser = argparse.ArgumentParser(description="Dialysis CDSS workflow")
    parser.add_argument("--schedule-xlsx", default=os.getenv("SCHEDULE_XLSX"))
    parser.add_argument("--year-month", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.schedule_xlsx:
        raise SystemExit("SCHEDULE_XLSX is required")

    result = load_schedule_workbook(Path(args.schedule_xlsx))
    print(f"patients: {len(result.patients)}")
    print(f"schedules: {len(result.schedules)}")
    print(f"source_updated_at: {result.source_updated_at}")
    for patient in result.patients[:10]:
        print(f"{stable_deid(patient.chart_no)} {patient.frequency} {patient.shift.value} {patient.bed or '-'} {patient.name}")

    # TODO(HIS): fetch labs/medications/admissions/procedures/exams from hospital adapters.
    # TODO(NOCODB): upsert patients and schedule records after table IDs are configured.
    notify_pending_approvals("CDSS dry-run finished; no records were written.", dry_run=True)


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
