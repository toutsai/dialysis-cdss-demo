from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.hospital_inbox import DEFAULT_GLOB, DEFAULT_STABLE_SECONDS, scan_inbox


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan a hospital drop folder once and ingest any new lab CSV files. "
        "Designed to be run on a schedule (cron / Windows Task Scheduler)."
    )
    parser.add_argument(
        "--inbox-dir",
        default=os.getenv("HOSPITAL_LAB_INBOX", ""),
        help="Folder the hospital writes monthly lab CSVs into (or set HOSPITAL_LAB_INBOX)",
    )
    parser.add_argument("--pattern", default=DEFAULT_GLOB, help="Glob for lab files (default: *.csv)")
    parser.add_argument("--archive-dir", default="", help="Where processed files move (default: <inbox>/archive)")
    parser.add_argument("--failed-dir", default="", help="Where unparseable files move (default: <inbox>/failed)")
    parser.add_argument(
        "--stable-seconds",
        type=int,
        default=DEFAULT_STABLE_SECONDS,
        help="Skip files whose mtime is younger than this, to avoid reading a half-written export",
    )
    parser.add_argument("--db-path", default="", help="Override DIALYSIS_CDSS_DB_PATH")
    parser.add_argument("--chart-no", action="append", default=[], help="Optional chart number filter; repeatable")
    parser.add_argument("--source", default="hospital_csv", help="Source label written to lab_results")
    args = parser.parse_args()

    if not args.inbox_dir:
        raise SystemExit("--inbox-dir or HOSPITAL_LAB_INBOX is required")
    if args.db_path:
        os.environ["DIALYSIS_CDSS_DB_PATH"] = args.db_path

    summary = scan_inbox(
        args.inbox_dir,
        pattern=args.pattern,
        archive_dir=args.archive_dir or None,
        failed_dir=args.failed_dir or None,
        stable_seconds=args.stable_seconds,
        chart_nos=args.chart_no,
        source=args.source,
    )

    print(f"inbox: {summary.inbox_dir}")
    print(f"scanned_at: {summary.scanned_at}")
    print(f"processed: {len(summary.processed)} | failed: {len(summary.failed)} | skipped: {len(summary.skipped)}")
    for result in summary.processed:
        print(f"- processed {result.file} -> labs={result.lab_count} moved_to={result.moved_to}"
              + (f" ({result.note})" if result.note else ""))
    for result in summary.failed:
        print(f"- failed {result.file} -> {result.error} moved_to={result.moved_to}")
    for result in summary.skipped:
        print(f"- skipped {result.file} ({result.note})")


if __name__ == "__main__":
    main()
