from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "dialysis_cdss.sqlite"
DEFAULT_SEED_DIR = ROOT / "exports" / "nocodb_seed"
PASSWORD_ITERATIONS = 260_000

SEED_TABLES = {
    "patients": "patients.csv",
    "dialysis_schedule": "dialysis_schedule.csv",
    "deid_map": "deid_map.csv",
    "problem_list": "problem_list.csv",
    "clinical_events": "clinical_events.csv",
    "dialysis_orders": "dialysis_orders.csv",
    "lab_results": "lab_results.csv",
    "medications": "medications.csv",
    "recommendations": "recommendations.csv",
    "staff": "staff.csv",
    "hospital_drugs": "hospital_drugs.csv",
}


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    db_path = Path(db_path or os.getenv("DIALYSIS_CDSS_DB_PATH", str(DEFAULT_DB_PATH)))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_database(seed_dir: Path = DEFAULT_SEED_DIR, db_path: Path | str | None = None) -> None:
    with connect(db_path) as conn:
        existing = _table_names(conn)
        missing = [table for table in SEED_TABLES if table not in existing]
        if missing:
            for table in missing:
                _import_seed_table(conn, table, seed_dir / SEED_TABLES[table], if_exists="replace")
            _ensure_ids(conn)
        _ensure_problem_list_columns(conn)
        _ensure_clinical_event_columns(conn)
        _ensure_patient_columns(conn)
        _ensure_staff_columns(conn)
        _ensure_hospital_drug_columns(conn)
        _ensure_dialysis_order_columns(conn)
        _ensure_handoffs_table(conn)


def sync_seed_csv(seed_dir: Path = DEFAULT_SEED_DIR, db_path: Path | str | None = None) -> None:
    with connect(db_path) as conn:
        existing_staff = pd.DataFrame()
        if "staff" in _table_names(conn):
            existing_staff = pd.read_sql_query("select * from staff", conn).fillna("")
        for table, filename in SEED_TABLES.items():
            _import_seed_table(conn, table, seed_dir / filename, if_exists="replace")
        _ensure_ids(conn)
        _ensure_problem_list_columns(conn)
        _ensure_clinical_event_columns(conn)
        _ensure_patient_columns(conn)
        _ensure_staff_columns(conn)
        _restore_staff_credentials(conn, existing_staff)
        _ensure_hospital_drug_columns(conn)
        _ensure_dialysis_order_columns(conn)
        _ensure_handoffs_table(conn)


def patients() -> pd.DataFrame:
    return _read("select * from patients order by frequency, shift, bed, name")


def schedules() -> pd.DataFrame:
    return _read(
        """
        select s.*
        from dialysis_schedule s
        left join patients p on p.chart_no = s.chart_no
        where coalesce(p.inactive_at, '') = ''
        order by s.frequency, s.shift, s.bed, s.name
        """
    )


def patient_registry() -> pd.DataFrame:
    return _read(
        """
        select
            p.chart_no,
            p.deid,
            p.name,
            coalesce(nullif(p.frequency, ''), s.frequency, '') as frequency,
            coalesce(nullif(p.shift, ''), s.shift, '') as shift,
            coalesce(nullif(p.bed, ''), s.bed, '') as bed,
            coalesce(s.dialyzer, '') as dialyzer,
            coalesce(s.dialysate_ca, '') as dialysate_ca,
            coalesce(p.active, '啟用') as active,
            coalesce(p.created_by, '') as created_by,
            coalesce(p.created_at, '') as created_at,
            coalesce(p.inactive_at, '') as inactive_at,
            coalesce(p.note, '') as note
        from patients p
        left join dialysis_schedule s on s.chart_no = p.chart_no
        order by case when coalesce(p.inactive_at, '') = '' then 0 else 1 end,
                 p.frequency, p.shift, p.bed, p.name
        """
    )


def patient_detail(chart_no: str) -> dict[str, pd.DataFrame]:
    return {
        "patient": _read("select * from patients where chart_no = ?", [chart_no]),
        "schedule": _read("select * from dialysis_schedule where chart_no = ?", [chart_no]),
        "problem_list": _read("select * from problem_list where chart_no = ? order by updated_at desc", [chart_no]),
        "clinical_events": _read("select * from clinical_events where chart_no = ? order by event_date desc, updated_at desc", [chart_no]),
        "handoffs": _read("select * from handoffs where chart_no = ? order by target_date desc, updated_at desc", [chart_no]),
        "dialysis_orders": _read("select * from dialysis_orders where chart_no = ? order by order_month desc, updated_at desc", [chart_no]),
        "lab_results": _read("select * from lab_results where chart_no = ? order by year_month desc, item_key", [chart_no]),
        "medications": _read("select * from medications where chart_no = ? order by year_month desc, drug_class, drug_name", [chart_no]),
        "recommendations": _read("select * from recommendations where chart_no = ? order by year_month desc, created_at desc", [chart_no]),
    }


def active_staff() -> pd.DataFrame:
    return _read("select * from staff where active in ('啟用', 'True', 'true', '1', 'Active') order by role, name")


def staff_role(name: str) -> str:
    if not name:
        return ""
    df = _read("select role from staff where name = ? and active in ('啟用', 'True', 'true', '1', 'Active') limit 1", [name])
    if df.empty:
        return ""
    return str(df.iloc[0].get("role", ""))


def staff_login_configured() -> bool:
    df = _read(
        """
        select 1 from staff
        where coalesce(username, '') != ''
          and coalesce(password_hash, '') != ''
          and active in ('啟用', 'True', 'true', '1', 'Active')
        limit 1
        """
    )
    return not df.empty


def authenticate_staff(username: str, password: str) -> dict[str, str] | None:
    if not username or not password:
        return None
    df = _read(
        """
        select * from staff
        where lower(username) = lower(?)
          and active in ('啟用', 'True', 'true', '1', 'Active')
        limit 1
        """,
        [username.strip()],
    )
    if df.empty:
        return None
    row = df.iloc[0].fillna("")
    if not verify_password(password, str(row.get("password_hash", ""))):
        return None
    return {key: str(row.get(key, "")) for key in row.index}


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, digest = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations_text),
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, TypeError):
        return False


def staff() -> pd.DataFrame:
    return _read("select * from staff order by active desc, role, name")


def replace_staff(rows: pd.DataFrame) -> None:
    rows = rows.fillna("")
    with connect() as conn:
        rows.to_sql("staff", conn, if_exists="replace", index=False)
        _ensure_staff_columns(conn)


def hospital_drugs() -> pd.DataFrame:
    return _read("select * from hospital_drugs order by active desc, drug_type, drug_name")


def active_hospital_drugs() -> pd.DataFrame:
    return _read("select * from hospital_drugs where active in ('啟用', 'True', 'true', '1', 'Active') order by drug_type, drug_name")


def replace_hospital_drugs(rows: pd.DataFrame) -> None:
    rows = rows.fillna("")
    with connect() as conn:
        rows.to_sql("hospital_drugs", conn, if_exists="replace", index=False)
        _ensure_hospital_drug_columns(conn)


def replace_patient_registry(rows: pd.DataFrame) -> None:
    rows = rows.fillna("").copy()
    rows = rows[rows["chart_no"].astype(str).str.strip() != ""]
    with connect() as conn:
        _ensure_patient_columns(conn)
        patient_cols = [row["name"] for row in conn.execute("pragma table_info(patients)")]
        schedule_cols = [row["name"] for row in conn.execute("pragma table_info(dialysis_schedule)")]
        existing_patients = pd.read_sql_query("select * from patients", conn).fillna("")
        existing_by_chart = {
            str(row.get("chart_no", "")).strip(): row
            for row in existing_patients.to_dict("records")
            if str(row.get("chart_no", "")).strip()
        }

        patient_records: list[dict[str, str]] = []
        schedule_records: list[dict[str, str]] = []
        deid_records: list[dict[str, str]] = []
        for _, row in rows.iterrows():
            chart_no = str(row.get("chart_no", "")).strip()
            if not chart_no:
                continue
            existing = existing_by_chart.get(chart_no, {})
            deid = str(row.get("deid", "")).strip() or str(existing.get("deid", "")).strip() or f"P{chart_no}"
            patient_base = dict(existing)
            patient_base.update({
                "chart_no": chart_no,
                "deid": deid,
                "name": str(row.get("name", "")).strip(),
                "frequency": str(row.get("frequency", "")).strip(),
                "shift": str(row.get("shift", "")).strip(),
                "bed": str(row.get("bed", "")).strip(),
                "created_by": str(row.get("created_by", "")).strip(),
                "created_at": str(row.get("created_at", "")).strip(),
                "inactive_at": str(row.get("inactive_at", "")).strip(),
                "note": str(row.get("note", "")).strip(),
            })
            patient_base["active"] = "停用" if patient_base["inactive_at"] else "啟用"
            if "last_synced_at" in patient_cols and not str(patient_base.get("last_synced_at", "")).strip():
                patient_base["last_synced_at"] = str(row.get("created_at", "")).strip()
            patient_records.append({col: str(patient_base.get(col, "")) for col in patient_cols})

            if not patient_base["inactive_at"]:
                schedule_base = {
                    "chart_no": chart_no,
                    "deid": deid,
                    "name": patient_base["name"],
                    "frequency": patient_base["frequency"],
                    "shift": patient_base["shift"],
                    "bed": patient_base["bed"],
                    "dialyzer": str(row.get("dialyzer", "")).strip(),
                    "dialysate_ca": str(row.get("dialysate_ca", "")).strip(),
                    "source_sheet": "patient_registry",
                    "source_updated_at": str(row.get("created_at", "")).strip(),
                }
                schedule_records.append({col: str(schedule_base.get(col, "")) for col in schedule_cols})
            deid_records.append({
                "chart_no": chart_no,
                "deid": deid,
                "created_at": str(row.get("created_at", "")).strip(),
            })

        pd.DataFrame(patient_records, columns=patient_cols).to_sql("patients", conn, if_exists="replace", index=False)
        pd.DataFrame(schedule_records, columns=schedule_cols).to_sql("dialysis_schedule", conn, if_exists="replace", index=False)
        pd.DataFrame(deid_records, columns=["chart_no", "deid", "created_at"]).to_sql("deid_map", conn, if_exists="replace", index=False)
        _ensure_patient_columns(conn)


def replace_patient_rows(table: str, chart_no: str, rows: pd.DataFrame) -> None:
    if table not in {"problem_list", "clinical_events", "handoffs", "dialysis_orders", "recommendations"}:
        raise ValueError(f"Unsupported editable table: {table}")
    with connect() as conn:
        conn.execute(f"delete from {table} where chart_no = ?", (chart_no,))
        if not rows.empty:
            rows = rows.fillna("")
            rows.to_sql(table, conn, if_exists="append", index=False)


def due_handoffs(today: str) -> pd.DataFrame:
    return _read(
        """
        select h.*, s.frequency, s.shift, s.bed
        from handoffs h
        left join dialysis_schedule s on s.chart_no = h.chart_no
        where h.target_date <= ?
          and coalesce(h.status, '') not in ('已處理', '已完成', '完成', 'Closed', 'closed')
        order by h.target_date asc, h.priority desc, s.frequency, s.shift, s.bed
        """,
        [today],
    )


def _read(sql: str, params: Iterable[str] | None = None) -> pd.DataFrame:
    with connect() as conn:
        return pd.read_sql_query(sql, conn, params=list(params or []))


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("select name from sqlite_master where type='table'").fetchall()
    return {str(row["name"]) for row in rows}


def _import_seed_table(conn: sqlite3.Connection, table: str, path: Path, if_exists: str) -> None:
    if not path.exists():
        return
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.to_sql(table, conn, if_exists=if_exists, index=False)


def _ensure_ids(conn: sqlite3.Connection) -> None:
    for table in ("problem_list", "clinical_events", "dialysis_orders"):
        cols = [row["name"] for row in conn.execute(f"pragma table_info({table})")]
        if "row_id" not in cols:
            conn.execute(f"alter table {table} add column row_id text")
        rows = conn.execute(f"select rowid from {table} where row_id is null or row_id = ''").fetchall()
        for row in rows:
            conn.execute(f"update {table} set row_id = ? where rowid = ?", (f"{table}-{row['rowid']}", row["rowid"]))


def _ensure_problem_list_columns(conn: sqlite3.Connection) -> None:
    if "problem_list" not in _table_names(conn):
        return
    cols = [row["name"] for row in conn.execute("pragma table_info(problem_list)")]
    if "problem_categories" not in cols:
        conn.execute(
            "alter table problem_list add column problem_categories text default '[\"現在待處理問題\"]'"
        )
    conn.execute(
        """
        update problem_list
        set problem_categories = '["現在待處理問題"]'
        where problem_categories is null or trim(problem_categories) = ''
        """
    )


def _ensure_clinical_event_columns(conn: sqlite3.Connection) -> None:
    if "clinical_events" not in _table_names(conn):
        return
    cols = [row["name"] for row in conn.execute("pragma table_info(clinical_events)")]
    defaults = {
        "event_content": "",
    }
    for col, default in defaults.items():
        if col not in cols:
            conn.execute(f"alter table clinical_events add column {col} text default '{default}'")


def _ensure_patient_columns(conn: sqlite3.Connection) -> None:
    if "patients" not in _table_names(conn):
        return
    cols = [row["name"] for row in conn.execute("pragma table_info(patients)")]
    defaults = {
        "created_by": "",
        "created_at": "",
        "inactive_at": "",
        "note": "",
    }
    for col, default in defaults.items():
        if col not in cols:
            conn.execute(f"alter table patients add column {col} text default '{default}'")


def _ensure_staff_columns(conn: sqlite3.Connection) -> None:
    if "staff" not in _table_names(conn):
        return
    cols = [row["name"] for row in conn.execute("pragma table_info(staff)")]
    defaults = {
        "staff_id": "",
        "name": "",
        "role": "護理師",
        "active": "啟用",
        "created_by": "",
        "created_at": "",
        "inactive_at": "",
        "note": "",
        "username": "",
        "password_hash": "",
        "password_set_at": "",
    }
    for col, default in defaults.items():
        if col not in cols:
            conn.execute(f"alter table staff add column {col} text default '{default}'")


def _restore_staff_credentials(conn: sqlite3.Connection, previous_staff: pd.DataFrame) -> None:
    if previous_staff.empty or "staff" not in _table_names(conn):
        return
    credential_cols = ["username", "password_hash", "password_set_at"]
    if not all(col in previous_staff.columns for col in credential_cols):
        return
    current = pd.read_sql_query("select rowid, * from staff", conn).fillna("")
    for _, row in current.iterrows():
        candidates = previous_staff
        staff_id = str(row.get("staff_id", "")).strip()
        name = str(row.get("name", "")).strip()
        if staff_id and "staff_id" in previous_staff.columns:
            by_id = previous_staff[previous_staff["staff_id"].astype(str).str.strip() == staff_id]
            if not by_id.empty:
                candidates = by_id
        if (candidates is previous_staff or candidates.empty) and name:
            by_name = previous_staff[previous_staff["name"].astype(str).str.strip() == name]
            if not by_name.empty:
                candidates = by_name
        if candidates.empty:
            continue
        prev = candidates.iloc[0]
        for col in credential_cols:
            value = str(prev.get(col, "")).strip()
            if value:
                conn.execute(f"update staff set {col} = ? where rowid = ?", (value, int(row["rowid"])))


def _ensure_hospital_drug_columns(conn: sqlite3.Connection) -> None:
    if "hospital_drugs" not in _table_names(conn):
        return
    cols = [row["name"] for row in conn.execute("pragma table_info(hospital_drugs)")]
    defaults = {
        "drug_id": "",
        "drug_type": "ESA",
        "drug_name": "",
        "default_unit": "",
        "active": "啟用",
        "created_by": "",
        "created_at": "",
        "inactive_at": "",
        "note": "",
    }
    for col, default in defaults.items():
        if col not in cols:
            conn.execute(f"alter table hospital_drugs add column {col} text default '{default}'")


def _ensure_dialysis_order_columns(conn: sqlite3.Connection) -> None:
    if "dialysis_orders" not in _table_names(conn):
        return
    cols = [row["name"] for row in conn.execute("pragma table_info(dialysis_orders)")]
    defaults = {
        "effective_date": "",
        "dialysis_days": "",
        "frequency": "",
        "shift": "",
        "bed": "",
        "dialysate_flow": "",
        "anticoagulant_loading": "",
        "anticoagulant_maintain": "",
        "access_side": "",
        "access_type": "",
    }
    for col, default in defaults.items():
        if col not in cols:
            conn.execute(f"alter table dialysis_orders add column {col} text default '{default}'")


def _ensure_handoffs_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        create table if not exists handoffs (
            chart_no text,
            deid text,
            name text,
            target_date text,
            handoff_type text,
            title text,
            content text,
            priority text,
            status text,
            created_by text,
            created_at text,
            updated_by text,
            updated_at text,
            row_id text
        )
        """
    )
    cols = [row["name"] for row in conn.execute("pragma table_info(handoffs)")]
    defaults = {
        "chart_no": "",
        "deid": "",
        "name": "",
        "target_date": "",
        "handoff_type": "共同交班",
        "title": "",
        "content": "",
        "priority": "一般",
        "status": "未處理",
        "created_by": "",
        "created_at": "",
        "updated_by": "",
        "updated_at": "",
        "row_id": "",
    }
    for col, default in defaults.items():
        if col not in cols:
            conn.execute(f"alter table handoffs add column {col} text default '{default}'")
