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
    if not path.exists() or _needs_demo_refresh(path):
        return create_demo_database(path)
    return path


def _needs_demo_refresh(path: Path) -> bool:
    try:
        with db.connect(path) as conn:
            row = conn.execute(
                """
                select count(distinct year_month) as month_count
                from medications
                where source = 'demo'
                """
            ).fetchone()
            return int(row["month_count"] or 0) < 4
    except Exception:
        return True


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
                "problem_categories": '["現在待處理問題"]',
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

        lab_results.extend(_lab_results(chart_no, deid, name, index, today))
        medications.extend(_medications(chart_no, deid, name, index, today))
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


def _lab_results(chart_no: str, deid: str, name: str, index: int, today: date) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for month_index, month_start in enumerate(_recent_month_starts(today, 4)):
        month = month_start.strftime("%Y%m")
        report_date = month_start.replace(day=15).isoformat()
        patient_delta = (index % 5) * 0.12
        values = {
            "Hb": (10.8 - month_index * 0.35 + patient_delta, "g/dL"),
            "Albumin": (3.6 + (index % 4) * 0.12, "g/dL"),
            "P": (4.6 + month_index * 0.28 + (index % 4) * 0.18, "mg/dL"),
            "Ca": (8.5 + (index % 4) * 0.18, "mg/dL"),
            "cCa": (8.7 + (index % 4) * 0.22, "mg/dL"),
            "CaXP": (42 + month_index * 2.7 + (index % 4) * 2.5, ""),
            "Ferritin": (280 - month_index * 42 + (index % 3) * 35, "ng/mL"),
            "TSAT": (28 - month_index * 2.7 + (index % 3) * 2, "%"),
            "iPTH": (360 + month_index * 65 + (index % 5) * 35, "pg/mL"),
            "K": (4.7 + (index % 4) * 0.18, "mmol/L"),
            "Kt/V": (1.38 - month_index * 0.05 - (index % 3) * 0.03, ""),
            "URR": (71 - month_index * 1.4 - (index % 3), "%"),
        }
        for key, (value, unit) in values.items():
            rows.append({
                "chart_no": chart_no,
                "deid": deid,
                "name": name,
                "year_month": month,
                "item_key": key,
                "value": f"{value:.1f}",
                "unit": unit,
                "report_date": report_date,
                "source": "demo",
            })
    return rows


def _medications(chart_no: str, deid: str, name: str, index: int, today: date) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    esa_doses = [20, 20, 40, 40] if index % 3 else [20, 40, 40, 60]
    binder_doses = [1, 1, 2, 2] if index % 2 else [1, 2, 2, 2]
    for month_index, month_start in enumerate(_recent_month_starts(today, 4)):
        month = month_start.strftime("%Y%m")
        start_date = month_start.isoformat()
        common = {
            "chart_no": chart_no,
            "deid": deid,
            "name": name,
            "year_month": month,
            "source": "demo",
            "source_record_id": "",
            "start_date": start_date,
            "end_date": "",
            "status": "Active",
            "updated_by": "system",
            "updated_at": datetime.combine(month_start, datetime.min.time()).isoformat(timespec="seconds"),
        }
        rows.append({
            **common,
            "drug_class": "ESA",
            "drug_name": "Darbepoetin alfa",
            "dose": str(esa_doses[month_index]),
            "unit": "mcg",
            "frequency": "QW",
            "order_code": f"ESA{index:03d}",
            "note": "demo ESA history",
            "row_id": f"medications-{chart_no}-{month}-esa",
        })
        binder_name = "Sevelamer" if index % 4 == 0 and month_index >= 2 else "Calcium carbonate"
        rows.append({
            **common,
            "drug_class": "NON_CALCIUM_BINDER" if binder_name == "Sevelamer" else "CALCIUM_BINDER",
            "drug_name": binder_name,
            "dose": str(binder_doses[month_index]),
            "unit": "tab",
            "frequency": "TID with meals",
            "order_code": f"P{index:03d}",
            "note": "demo phosphate binder history",
            "row_id": f"medications-{chart_no}-{month}-binder",
        })
        if index % 4 == 0 and month_index >= 2:
            rows.append({
                **common,
                "drug_class": "K_BINDER",
                "drug_name": "Sodium zirconium cyclosilicate",
                "dose": "5",
                "unit": "g",
                "frequency": "QD",
                "order_code": f"K{index:03d}",
                "note": "demo potassium binder history",
                "row_id": f"medications-{chart_no}-{month}-k",
            })
        if index % 5 == 0 and month_index >= 1:
            rows.append({
                **common,
                "drug_class": "PTH",
                "drug_name": "Cinacalcet",
                "dose": "25",
                "unit": "mg",
                "frequency": "QD",
                "order_code": f"PTH{index:03d}",
                "note": "demo SHPT medication history",
                "row_id": f"medications-{chart_no}-{month}-pth",
            })
    return rows


def _recent_month_starts(today: date, count: int) -> list[date]:
    current = today.replace(day=1)
    return [_add_months(current, -months_ago) for months_ago in reversed(range(count))]


def _add_months(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    year = month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


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
