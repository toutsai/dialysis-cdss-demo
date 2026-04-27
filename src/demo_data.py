from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from src import db


DEMO_PATIENTS = [
    ("D00001", "P900001", "測試病人01", "一三五", "午班", "1", "Rex25A", "3.0"),
    ("D00002", "P900002", "測試病人02", "一三五", "午班", "3", "FX80", "2.5"),
    ("D00003", "P900003", "測試病人03", "一三五", "午班", "5(B)", "FX100", "3.0"),
    ("D00004", "P900004", "測試病人04", "一三五", "早班", "1", "BG1.8U", "3.5"),
    ("D00005", "P900005", "測試病人05", "一三五", "早班", "2", "FX80", "3.0"),
    ("D00006", "P900006", "測試病人06", "一三五", "早班", "6", "BG2.1U", "2.5"),
    ("D00007", "P900007", "測試病人07", "二四六", "午班", "1", "FX80", "3.0"),
    ("D00008", "P900008", "測試病人08", "二四六", "午班", "4", "FX100", "3.5"),
    ("D00009", "P900009", "測試病人09", "二四六", "午班", "8", "BG1.8U", "3.0"),
    ("D00010", "P900010", "測試病人10", "二四六", "早班", "2", "Rex25A", "2.5"),
    ("D00011", "P900011", "測試病人11", "二四六", "早班", "7", "FX80", "3.0"),
    ("D00012", "P900012", "測試病人12", "一五", "晚班", "1", "BG2.1U", "3.0"),
]


def create_demo_database(path: Path = db.ROOT / "data" / "dialysis_cdss_demo.sqlite") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    now = datetime.now().isoformat(timespec="seconds")
    today = date.today()
    tables = _build_demo_tables(now=now, today=today)
    with db.connect(path) as conn:
        for table_name, frame in tables.items():
            frame.fillna("").to_sql(table_name, conn, if_exists="replace", index=False)

    db.ensure_database(db_path=path)
    return path


def ensure_demo_database(path: Path = db.ROOT / "data" / "dialysis_cdss_demo.sqlite") -> Path:
    if not path.exists():
        return create_demo_database(path)
    return path


def _build_demo_tables(now: str, today: date) -> dict[str, pd.DataFrame]:
    patients = []
    schedules = []
    deid_map = []
    dialysis_orders = []
    problem_list = []
    clinical_events = []
    handoffs = []
    lab_results = []
    medications = []
    recommendations = []

    for index, (chart_no, deid, name, frequency, shift, bed, dialyzer, dialysate_ca) in enumerate(DEMO_PATIENTS, start=1):
        patients.append({
            "chart_no": chart_no,
            "deid": deid,
            "name": name,
            "frequency": frequency,
            "shift": shift,
            "bed": bed,
            "identity": "demo",
            "active": "啟用",
            "source": "demo",
            "last_synced_at": now,
            "created_by": "system",
            "created_at": now,
            "inactive_at": "",
            "note": "",
        })
        schedules.append({
            "chart_no": chart_no,
            "deid": deid,
            "name": name,
            "frequency": frequency,
            "shift": shift,
            "bed": bed,
            "dialyzer": dialyzer,
            "dialysate_ca": dialysate_ca,
            "source_sheet": "demo",
            "source_updated_at": now,
        })
        deid_map.append({"chart_no": chart_no, "deid": deid, "created_at": now})
        dialysis_orders.append(_dialysis_order(chart_no, deid, name, frequency, shift, bed, dialyzer, dialysate_ca, index, now))

        if index in {1, 3, 7}:
            problem_list.append({
                "chart_no": chart_no,
                "deid": deid,
                "name": name,
                "problem": "血磷控制待加強，需追蹤飲食與降磷藥服藥狀況",
                "status": "Active",
                "priority": "",
                "owner_role": "護理師",
                "updated_by": "護理師測試帳號",
                "updated_at": now,
                "note": "demo problem",
                "row_id": f"problem_list-{chart_no}-1",
            })
        if index in {2, 5, 9}:
            event_date = today - timedelta(days=index)
            clinical_events.append({
                "chart_no": chart_no,
                "deid": deid,
                "name": name,
                "event_type": "門診" if index != 5 else "急診",
                "event_date": event_date.isoformat(),
                "title": "血管通路問題" if index == 2 else "感染問題",
                "source": "demo",
                "updated_by": "護理長測試帳號",
                "updated_at": now,
                "note": "",
                "row_id": f"clinical_events-{chart_no}-1",
                "event_content": "此為 demo 近期事件，供測試查房頁面使用。",
            })
        if index in {1, 4, 8}:
            handoffs.append({
                "chart_no": chart_no,
                "deid": deid,
                "name": name,
                "target_date": today.isoformat(),
                "handoff_type": "共同交班",
                "title": "" if index == 1 else "追蹤血壓與乾體重",
                "content": "今日請協助追蹤透析中血壓、症狀與是否需要回報醫師。",
                "priority": "重要" if index == 4 else "一般",
                "status": "未處理",
                "created_by": "護理師測試帳號",
                "created_at": now,
                "updated_by": "護理師測試帳號",
                "updated_at": now,
                "row_id": f"handoffs-{chart_no}-1",
            })

        lab_results.extend(_lab_results(chart_no, index, today))
        medications.extend(_medications(chart_no, index))
        recommendations.append({
            "chart_no": chart_no,
            "deid": deid,
            "name": name,
            "year_month": today.strftime("%Y%m"),
            "recommendation_type": "demo",
            "summary": "demo 建議：請依規則引擎結果與臨床狀況確認。",
            "status": "draft",
            "created_at": now,
            "approved_by": "",
            "approved_at": "",
        })

    return {
        "patients": pd.DataFrame(patients),
        "dialysis_schedule": pd.DataFrame(schedules),
        "deid_map": pd.DataFrame(deid_map),
        "problem_list": pd.DataFrame(problem_list),
        "clinical_events": pd.DataFrame(clinical_events),
        "handoffs": pd.DataFrame(handoffs),
        "dialysis_orders": pd.DataFrame(dialysis_orders),
        "lab_results": pd.DataFrame(lab_results),
        "medications": pd.DataFrame(medications),
        "recommendations": pd.DataFrame(recommendations),
        "staff": pd.DataFrame(_staff(now)),
        "hospital_drugs": pd.DataFrame(_hospital_drugs(now)),
    }


def _dialysis_order(chart_no: str, deid: str, name: str, frequency: str, shift: str, bed: str, dialyzer: str, dialysate_ca: str, index: int, now: str) -> dict[str, str]:
    return {
        "chart_no": chart_no,
        "deid": deid,
        "name": name,
        "order_month": datetime.now().strftime("%Y%m"),
        "dialyzer": dialyzer,
        "dialysate_ca": dialysate_ca,
        "blood_flow": str(240 + (index % 4) * 20),
        "dry_weight": f"{52 + index * 1.4:.1f}",
        "anticoagulant": "Loading 1000U / Maintain 500U/hr",
        "vascular_access": "左 AVF" if index % 2 else "右 AVG",
        "updated_by": "醫師測試帳號",
        "updated_at": now,
        "note": "demo initial order",
        "row_id": f"dialysis_orders-{chart_no}-1",
        "effective_date": datetime.now().date().isoformat(),
        "dialysis_days": ",".join([day for day in ["一", "二", "三", "四", "五", "六"] if day in frequency]),
        "frequency": frequency,
        "shift": shift,
        "bed": bed,
        "dialysate_flow": "500",
        "anticoagulant_loading": "1000U",
        "anticoagulant_maintain": "500U/hr",
        "access_side": "左" if index % 2 else "右",
        "access_type": "AVF" if index % 2 else "AVG",
    }


def _lab_results(chart_no: str, index: int, today: date) -> list[dict[str, str]]:
    month = today.strftime("%Y%m")
    report_date = today.replace(day=15).isoformat()
    values = {
        "Hb": (9.2 + (index % 6) * 0.6, "g/dL"),
        "Albumin": (3.6 + (index % 4) * 0.15, "g/dL"),
        "P": (4.4 + (index % 5) * 0.55, "mg/dL"),
        "Ca": (8.4 + (index % 4) * 0.25, "mg/dL"),
        "cCa": (8.7 + (index % 4) * 0.28, "mg/dL"),
        "CaXP": (42 + (index % 5) * 4.5, ""),
        "Ferritin": (120 + (index % 6) * 80, "ng/mL"),
        "TSAT": (18 + (index % 6) * 5, "%"),
        "iPTH": (260 + (index % 7) * 95, "pg/mL"),
    }
    return [
        {
            "chart_no": chart_no,
            "year_month": month,
            "item_key": key,
            "value": f"{value:.1f}",
            "unit": unit,
            "report_date": report_date,
            "source": "demo",
        }
        for key, (value, unit) in values.items()
    ]


def _medications(chart_no: str, index: int) -> list[dict[str, str]]:
    month = datetime.now().strftime("%Y%m")
    return [
        {
            "chart_no": chart_no,
            "year_month": month,
            "drug_class": "ESA",
            "drug_name": "Darbepoetin alfa",
            "dose": str(20 + (index % 4) * 20),
            "frequency": "QW",
            "order_code": f"ESA{index:03d}",
            "source": "demo",
        },
        {
            "chart_no": chart_no,
            "year_month": month,
            "drug_class": "Phosphate binder",
            "drug_name": "Calcium carbonate",
            "dose": "1#",
            "frequency": "TID with meals",
            "order_code": f"P{index:03d}",
            "source": "demo",
        },
    ]


def _staff(now: str) -> list[dict[str, str]]:
    accounts = [
        ("admin", "管理員", "醫師", "admin123"),
        ("doctor", "醫師測試帳號", "醫師", "doctor123"),
        ("nurse", "護理師測試帳號", "護理師", "nurse123"),
        ("HN", "護理長測試帳號", "護理長", "HN123"),
    ]
    return [
        {
            "staff_id": username,
            "name": name,
            "role": role,
            "active": "啟用",
            "created_by": "system",
            "created_at": now,
            "inactive_at": "",
            "note": "demo account",
            "username": username,
            "password_hash": db.hash_password(password),
            "password_set_at": now,
        }
        for username, name, role, password in accounts
    ]


def _hospital_drugs(now: str) -> list[dict[str, str]]:
    return [
        {"drug_id": "demo-esa-1", "drug_type": "ESA", "drug_name": "Darbepoetin alfa", "default_unit": "mcg", "active": "啟用", "created_by": "system", "created_at": now, "inactive_at": "", "note": "demo"},
        {"drug_id": "demo-p-1", "drug_type": "降磷藥", "drug_name": "Calcium carbonate", "default_unit": "tab", "active": "啟用", "created_by": "system", "created_at": now, "inactive_at": "", "note": "demo"},
        {"drug_id": "demo-k-1", "drug_type": "降鉀藥", "drug_name": "Sodium zirconium cyclosilicate", "default_unit": "g", "active": "啟用", "created_by": "system", "created_at": now, "inactive_at": "", "note": "demo"},
        {"drug_id": "demo-pth-1", "drug_type": "副甲狀腺亢進藥物", "drug_name": "Cinacalcet", "default_unit": "mg", "active": "啟用", "created_by": "system", "created_at": now, "inactive_at": "", "note": "demo"},
    ]


if __name__ == "__main__":
    print(create_demo_database())
