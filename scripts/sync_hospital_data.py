from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.hospital_sync import sync_hospital_data


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync hospital lab data into local CDSS database")
    parser.add_argument("--db-path", default="", help="Override DIALYSIS_CDSS_DB_PATH")
    parser.add_argument("--lab-csv", default="", help="CSV bridge file for lab results")
    parser.add_argument("--medication-csv", default="", help="Optional CSV bridge file for medication/order records")
    parser.add_argument(
        "--include-medications",
        action="store_true",
        help="Opt in to medication sync. Default is lab-only; medications are maintained from the front end.",
    )
    parser.add_argument("--chart-no", action="append", default=[], help="Optional chart number filter; repeatable")
    parser.add_argument("--start-date", default="", help="YYYY-MM-DD")
    parser.add_argument("--end-date", default="", help="YYYY-MM-DD")
    parser.add_argument("--source", default="hospital_csv", help="Source label written to lab_results/medications")
    args = parser.parse_args()

    if args.db_path:
        os.environ["DIALYSIS_CDSS_DB_PATH"] = args.db_path

    summary = sync_hospital_data(
        chart_nos=args.chart_no,
        start_date=args.start_date,
        end_date=args.end_date,
        lab_csv=Path(args.lab_csv) if args.lab_csv else None,
        medication_csv=Path(args.medication_csv) if args.medication_csv else None,
        sync_medications=args.include_medications or bool(args.medication_csv),
        source=args.source,
    )

    print(f"source: {summary.source}")
    print(f"synced_at: {summary.synced_at}")
    print(f"labs: {summary.lab_count}")
    print(f"medications: {summary.medication_count}")
    if summary.skipped:
        print("skipped:")
        for item in summary.skipped:
            print(f"- {item}")


if __name__ == "__main__":
    main()
