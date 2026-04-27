from pathlib import Path

import pandas as pd

from src import db


def test_sync_seed_csv_creates_tables(tmp_path: Path):
    seed = tmp_path / "seed"
    seed.mkdir()
    for table, filename in db.SEED_TABLES.items():
        if table == "patients":
            pd.DataFrame([{
                "chart_no": "12345A",
                "deid": "P000001",
                "name": "測試病人",
                "frequency": "一三五",
                "shift": "早班",
                "bed": "1",
                "identity": "",
                "active": "True",
                "source": "test",
                "last_synced_at": "2026-04-27T00:00:00",
            }]).to_csv(seed / filename, index=False, encoding="utf-8-sig")
        else:
            pd.DataFrame([{
                "chart_no": "12345A",
                "deid": "P000001",
                "name": "測試病人",
                "updated_at": "2026-04-27T00:00:00",
            }]).to_csv(seed / filename, index=False, encoding="utf-8-sig")

    db_path = tmp_path / "test.sqlite"
    db.sync_seed_csv(seed_dir=seed, db_path=db_path)
    with db.connect(db_path) as conn:
        names = db._table_names(conn)
    assert "patients" in names
    assert "problem_list" in names


def test_staff_replace_keeps_table(tmp_path: Path):
    db_path = tmp_path / "staff.sqlite"
    rows = pd.DataFrame([{
        "staff_id": "nurse-1",
        "name": "護理師A",
        "role": "護理師",
        "active": "啟用",
        "created_by": "tester",
        "created_at": "2026-04-27T00:00:00",
        "inactive_at": "",
        "note": "",
    }])
    with db.connect(db_path) as conn:
        rows.to_sql("staff", conn, if_exists="replace", index=False)
        db._ensure_staff_columns(conn)
        names = db._table_names(conn)
    assert "staff" in names


def test_hospital_drugs_columns(tmp_path: Path):
    db_path = tmp_path / "drugs.sqlite"
    rows = pd.DataFrame([{
        "drug_id": "esa-1",
        "drug_type": "ESA",
        "drug_name": "Darbepoetin alfa",
        "default_unit": "mcg",
        "active": "啟用",
        "created_by": "tester",
        "created_at": "2026-04-27T00:00:00",
        "inactive_at": "",
        "note": "",
    }])
    with db.connect(db_path) as conn:
        rows.to_sql("hospital_drugs", conn, if_exists="replace", index=False)
        db._ensure_hospital_drug_columns(conn)
        names = db._table_names(conn)
    assert "hospital_drugs" in names
