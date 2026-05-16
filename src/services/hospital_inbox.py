from __future__ import annotations

import hashlib
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from src.audit import audit_payload
from src.services.hospital_sync import sync_hospital_data

DEFAULT_GLOB = "*.csv"
DEFAULT_STABLE_SECONDS = 60


@dataclass(frozen=True)
class InboxFileResult:
    file: str
    status: str  # processed | failed | skipped_unstable
    lab_count: int = 0
    sha256: str = ""
    moved_to: str = ""
    note: str = ""
    error: str = ""


@dataclass(frozen=True)
class InboxScanSummary:
    inbox_dir: str
    scanned_at: str
    processed: list[InboxFileResult] = field(default_factory=list)
    failed: list[InboxFileResult] = field(default_factory=list)
    skipped: list[InboxFileResult] = field(default_factory=list)


def scan_inbox(
    inbox_dir: Path | str,
    *,
    pattern: str = DEFAULT_GLOB,
    archive_dir: Path | str | None = None,
    failed_dir: Path | str | None = None,
    stable_seconds: int = DEFAULT_STABLE_SECONDS,
    chart_nos: Iterable[str] | None = None,
    source: str = "hospital_csv",
) -> InboxScanSummary:
    """Scan a hospital drop folder once and ingest any new lab CSV files.

    Designed to be invoked on a schedule (cron / Windows Task Scheduler). The
    underlying ``sync_hospital_data`` is idempotent per
    ``(source, chart_no, year_month)``, so re-running a month is safe; here the
    folder is also drained by moving consumed files out, keeping the watch
    directory clean and giving an auditable trail.

    Files whose mtime is younger than ``stable_seconds`` are treated as still
    being written by the hospital export and are left for the next scan.
    """

    inbox = Path(inbox_dir).expanduser()
    archive = Path(archive_dir).expanduser() if archive_dir else inbox / "archive"
    failed = Path(failed_dir).expanduser() if failed_dir else inbox / "failed"
    scanned_at = datetime.now().isoformat(timespec="seconds")

    summary = InboxScanSummary(inbox_dir=str(inbox), scanned_at=scanned_at)
    if not inbox.is_dir():
        _audit_scan(summary, source, status="error")
        raise FileNotFoundError(f"inbox directory not found: {inbox}")

    reserved = {archive.resolve(), failed.resolve()}
    candidates = sorted(
        path
        for path in inbox.glob(pattern)
        if path.is_file() and path.parent.resolve() not in reserved
    )

    for path in candidates:
        if not _is_stable(path, stable_seconds):
            summary.skipped.append(
                InboxFileResult(file=path.name, status="skipped_unstable", note="mtime younger than stable window")
            )
            continue

        digest = _sha256(path)
        try:
            sync = sync_hospital_data(
                chart_nos=chart_nos,
                lab_csv=path,
                sync_medications=False,
                source=source,
            )
        except Exception as exc:  # noqa: BLE001 - record and quarantine bad files
            moved = _move(path, failed)
            result = InboxFileResult(
                file=path.name,
                status="failed",
                sha256=digest,
                moved_to=str(moved),
                error=f"{type(exc).__name__}: {exc}",
            )
            summary.failed.append(result)
            _audit_file(result, source)
            continue

        moved = _move(path, archive)
        note = "no_rows_imported" if sync.lab_count == 0 else ""
        result = InboxFileResult(
            file=path.name,
            status="processed",
            lab_count=sync.lab_count,
            sha256=digest,
            moved_to=str(moved),
            note=note,
        )
        summary.processed.append(result)
        _audit_file(result, source)

    _audit_scan(summary, source, status="ok")
    return summary


def _is_stable(path: Path, stable_seconds: int) -> bool:
    if stable_seconds <= 0:
        return True
    age = datetime.now().timestamp() - path.stat().st_mtime
    return age >= stable_seconds


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _move(path: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = dest_dir / f"{stamp}__{path.name}"
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{stamp}-{counter}__{path.name}"
        counter += 1
    shutil.move(str(path), str(dest))
    return dest


def _audit_file(result: InboxFileResult, source: str) -> None:
    audit_payload(
        service="hospital_inbox_file",
        model=source,
        payload={"file": result.file, "sha256": result.sha256},
        response=asdict(result),
        status="ok" if result.status == "processed" else "error",
    )


def _audit_scan(summary: InboxScanSummary, source: str, status: str) -> None:
    audit_payload(
        service="hospital_inbox",
        model=source,
        payload={"inbox_dir": summary.inbox_dir, "scanned_at": summary.scanned_at},
        response={
            "processed": len(summary.processed),
            "failed": len(summary.failed),
            "skipped": len(summary.skipped),
        },
        status=status,
    )
