from __future__ import annotations

import os
import re
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from src import db
from src.domain.entities import LabResult, Medication
from src.domain.dose_adjustment import build_dose_adjustments
from src.domain.rules import Thresholds, evaluate_month
from src.settings import load_dose_rules, save_dose_rules


COLUMN_LABELS = {
    "staff_id": "人員 ID",
    "username": "帳號",
    "name": "姓名",
    "role": "角色",
    "active": "啟用",
    "created_by": "新增者",
    "created_at": "新增時間",
    "inactive_at": "停用時間",
    "drug_id": "藥物 ID",
    "drug_type": "類型",
    "drug_name": "藥名",
    "default_unit": "預設單位",
    "problem": "主要問題",
    "status": "狀態",
    "owner_role": "負責角色",
    "updated_by": "更新者",
    "updated_at": "更新時間",
    "note": "備註",
    "event_type": "事件類型",
    "event_date": "事件日期",
    "title": "事件標題",
    "event_content": "事件內容",
    "source": "來源",
    "target_date": "目標日期",
    "handoff_type": "交班類型",
    "content": "交班內容",
    "priority": "優先度",
    "created_by": "建立者",
    "effective_date": "生效日期",
    "dialysis_days": "透析日",
    "frequency": "頻率",
    "shift": "班別",
    "bed": "床位",
    "order_month": "醫囑月份",
    "dialyzer": "人工腎臟",
    "dialysate_ca": "透析液 Ca",
    "dialysate_flow": "Dialysate flow",
    "blood_flow": "Blood flow",
    "dry_weight": "Dry weight",
    "anticoagulant": "抗凝",
    "anticoagulant_loading": "抗凝 Loading",
    "anticoagulant_maintain": "抗凝 Maintain",
    "access_side": "血管通路側別",
    "access_type": "血管通路類型",
    "vascular_access": "血管通路",
}


st.set_page_config(
    page_title="Dialysis CDSS 查房工作台",
    page_icon="🩺",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2rem;
        padding-left: 1.25rem;
        padding-right: 1.25rem;
        max-width: 100%;
    }
    html, body, [class*="css"] {
        font-size: 17px;
    }
    h1 {
        font-size: 1.55rem !important;
        margin-bottom: 0.45rem !important;
        line-height: 1.45 !important;
        padding-top: 0.35rem !important;
    }
    h2 {
        line-height: 1.55 !important;
        padding-top: 0.4rem !important;
        margin-top: 0.2rem !important;
        margin-bottom: 0.35rem !important;
    }
    h4, h5 {
        margin-top: 0.35rem !important;
        margin-bottom: 0.35rem !important;
    }
    div[data-testid="stRadio"] label p {
        font-size: 1rem;
    }
    div[role="radiogroup"] label {
        background: #ffffff;
        border: 1px solid #dbeafe;
        border-radius: 8px;
        padding: 0.4rem 0.55rem;
        margin: 0.18rem 0;
    }
    div[role="radiogroup"] label:has(input:checked) {
        background: #dbeafe;
        border-color: #2563eb;
        color: #1d4ed8;
        font-weight: 800;
    }
    div[data-testid="stButton"] > button {
        justify-content: flex-start;
        min-height: 2.18rem;
        font-size: 0.9rem;
        border-radius: 8px;
        border-color: #dbeafe;
        background: #ffffff;
        color: #0f172a;
        padding: 0.18rem 0.34rem;
        text-align: left;
    }
    div[data-testid="stButton"] > button p {
        text-align: left;
        width: 100%;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    div[data-testid="stButton"] > button[kind="primary"],
    button[data-testid="stBaseButton-primary"] {
        background: #dbeafe !important;
        border-color: #2563eb !important;
        color: #0f172a !important;
        font-weight: 850 !important;
        box-shadow: inset 5px 0 0 #2563eb;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover {
        background: #bfdbfe !important;
        border-color: #1d4ed8 !important;
        color: #0f172a !important;
    }
    div[data-testid="stButton"] > button:hover {
        border-color: #2563eb;
        color: #1d4ed8;
        background: #eff6ff;
    }
    [data-testid="stSidebar"] {
        background: #eef6ff;
        border-right: 1px solid #dbeafe;
    }
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 0.65rem 0.8rem;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        overflow: hidden;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.2rem;
        border-bottom: 1px solid #e2e8f0;
    }
    .stTabs [data-baseweb="tab"] {
        color: #334155;
        padding: 0.6rem 0.75rem;
        font-size: 1rem;
        white-space: nowrap;
    }
    .stTabs [aria-selected="true"] {
        color: #1d4ed8;
        font-weight: 700;
    }
    .cdss-card {
        border: 1px solid #dbeafe;
        border-left: 5px solid #2563eb;
        border-radius: 10px;
        padding: 0.48rem 0.7rem;
        margin: 0.1rem 0 0.45rem 0;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
    }
    .cdss-card .label {
        color: #475569;
        font-size: 0.76rem;
        font-weight: 650;
        margin-bottom: 0.06rem;
    }
    .cdss-card .value {
        color: #0f172a;
        font-size: 1.2rem;
        line-height: 1.2;
        font-weight: 800;
    }
    .cdss-card .subvalue {
        color: #475569;
        font-size: 0.78rem;
        margin-top: 0.08rem;
    }
    .cdss-blue {
        background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
        border-left-color: #2563eb;
    }
    .cdss-teal {
        background: linear-gradient(135deg, #ecfeff 0%, #ccfbf1 100%);
        border-left-color: #0d9488;
    }
    .cdss-amber {
        background: linear-gradient(135deg, #fffbeb 0%, #fde68a 100%);
        border-left-color: #d97706;
    }
    .cdss-rose {
        background: linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%);
        border-left-color: #e11d48;
    }
    .cdss-patient-banner {
        background: linear-gradient(135deg, #e0f2fe 0%, #f8fafc 60%, #fef3c7 100%);
        border: 1px solid #bae6fd;
        border-left: 6px solid #0284c7;
        border-radius: 12px;
        padding: 1.05rem 0.95rem 0.75rem 0.95rem;
        margin: 0.55rem 0 0.55rem 0;
    }
    .cdss-patient-name {
        color: #0f172a;
        font-size: 1.45rem;
        font-weight: 850;
        line-height: 1.5;
        padding-top: 0.1rem;
    }
    .cdss-patient-meta {
        color: #334155;
        font-size: 1rem;
        margin-top: 0.22rem;
    }
    .cdss-pill {
        display: inline-block;
        background: rgba(255, 255, 255, 0.72);
        border: 1px solid rgba(148, 163, 184, 0.45);
        border-radius: 999px;
        padding: 0.18rem 0.55rem;
        margin-right: 0.35rem;
        margin-top: 0.25rem;
        font-weight: 700;
    }
    .cdss-compact-summary {
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-left: 5px solid #0d9488;
        border-radius: 9px;
        color: #0f172a;
        font-weight: 750;
        padding: 0.5rem 0.65rem;
        margin: 0.2rem 0 0.5rem 0;
    }
    .cdss-alert-summary {
        background: #fff7ed;
        border: 1px solid #fdba74;
        border-left: 6px solid #ea580c;
        border-radius: 9px;
        color: #9a3412;
        font-weight: 850;
        padding: 0.55rem 0.7rem;
        margin: 0.2rem 0 0.5rem 0;
    }
    .cdss-handoff-alert {
        display: block;
        background: #fff7ed;
        border: 1px solid #fdba74;
        border-left: 6px solid #ea580c;
        border-radius: 10px;
        color: #0f172a;
        padding: 0.55rem 0.65rem;
        margin: 0.35rem 0 0.22rem 0;
        text-decoration: none !important;
        transition: border-color 120ms ease, box-shadow 120ms ease, transform 120ms ease;
    }
    .cdss-handoff-alert:hover {
        border-color: #ea580c;
        box-shadow: 0 3px 10px rgba(234, 88, 12, 0.16);
        transform: translateY(-1px);
        text-decoration: none !important;
    }
    .cdss-handoff-alert.urgent {
        background: #fef2f2;
        border-color: #fca5a5;
        border-left-color: #dc2626;
    }
    .cdss-handoff-alert.urgent:hover {
        border-color: #dc2626;
        box-shadow: 0 3px 10px rgba(220, 38, 38, 0.16);
    }
    .cdss-handoff-alert .meta {
        color: #7c2d12;
        font-size: 0.82rem;
        font-weight: 800;
        margin-bottom: 0.18rem;
    }
    .cdss-handoff-alert.urgent .meta {
        color: #991b1b;
    }
    .cdss-handoff-alert .headline {
        font-size: 0.95rem;
        font-weight: 850;
        line-height: 1.35;
    }
    .cdss-handoff-alert .detail {
        color: #475569;
        font-size: 0.82rem;
        line-height: 1.35;
        margin-top: 0.16rem;
    }
    .cdss-handoff-reminders div[data-testid="stButton"] > button,
    .cdss-handoff-reminders button[data-testid="stBaseButton-primary"],
    .cdss-handoff-reminders button[data-testid="stBaseButton-secondary"] {
        background: #fff7ed !important;
        border-color: #fb923c !important;
        color: #7c2d12 !important;
        font-weight: 850 !important;
        box-shadow: inset 5px 0 0 #ea580c !important;
    }
    .cdss-handoff-reminders div[data-testid="stButton"] > button:hover,
    .cdss-handoff-reminders button[data-testid="stBaseButton-primary"]:hover,
    .cdss-handoff-reminders button[data-testid="stBaseButton-secondary"]:hover {
        background: #fed7aa !important;
        border-color: #ea580c !important;
        color: #7c2d12 !important;
    }
    .cdss-panel {
        background: #f8fafc;
        border: 1px solid #dbeafe;
        border-radius: 10px;
        padding: 0.55rem 0.65rem;
        margin-bottom: 0.55rem;
    }
    .cdss-panel-title {
        color: #0f172a;
        font-size: 1.05rem;
        font-weight: 850;
        margin-bottom: 0.35rem;
    }
    .cdss-selected-row button {
        background: #dbeafe !important;
        border-color: #2563eb !important;
        color: #1d4ed8 !important;
        font-weight: 800 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _value_text(value: object, default: str = "未填") -> str:
    if value is None or pd.isna(value):
        return default
    text = str(value).strip()
    return text if text else default


def _highlight_card(label: str, value: object, subvalue: str = "", tone: str = "blue") -> None:
    safe_label = escape(label)
    safe_value = escape(_value_text(value))
    safe_subvalue = escape(subvalue)
    sub_html = f'<div class="subvalue">{safe_subvalue}</div>' if safe_subvalue else ""
    st.markdown(
        f"""
        <div class="cdss-card cdss-{tone}">
            <div class="label">{safe_label}</div>
            <div class="value">{safe_value}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _patient_banner(patient: pd.Series, schedule: pd.Series | None) -> None:
    name = escape(_value_text(patient.get("name")))
    chart_no = escape(_value_text(patient.get("chart_no")))
    pills = []
    if schedule is not None:
        pills = [
            f"頻率 {_value_text(schedule.get('frequency'))}",
            f"班別 {_value_text(schedule.get('shift'))}",
            f"床位 {_value_text(schedule.get('bed'))}",
            f"透析液 Ca {_value_text(schedule.get('dialysate_ca'))}",
        ]
    pill_html = "".join(f'<span class="cdss-pill">{escape(pill)}</span>' for pill in pills)
    st.markdown(
        f"""
        <div class="cdss-patient-banner">
            <div class="cdss-patient-name">{name}｜{chart_no}</div>
            <div class="cdss-patient-meta">{pill_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _compact_summary(text: str) -> None:
    st.markdown(f'<div class="cdss-compact-summary">{escape(text)}</div>', unsafe_allow_html=True)


def _alert_summary(text: str) -> None:
    st.markdown(f'<div class="cdss-alert-summary">{escape(text)}</div>', unsafe_allow_html=True)


def _panel_title(text: str) -> None:
    st.markdown(f'<div class="cdss-panel-title">{escape(text)}</div>', unsafe_allow_html=True)


def _patient_compact_header(
    patient: pd.Series,
    schedule: pd.Series | None,
    dry_weight: object,
    dialyzer: object,
    dialysate_ca: object,
) -> None:
    name = escape(_value_text(patient.get("name")))
    chart_no = escape(_value_text(patient.get("chart_no")))
    pill_values = [
        f"DW {_value_text(dry_weight)}",
        f"AK {_value_text(dialyzer)}",
        f"藥水 Ca {_value_text(dialysate_ca)}",
    ]
    if schedule is not None:
        pill_values.extend([
            f"{_value_text(schedule.get('frequency'))}",
            f"{_value_text(schedule.get('shift'))}",
            f"{_value_text(schedule.get('bed'))}床",
        ])
    pill_html = "".join(f'<span class="cdss-pill">{escape(pill)}</span>' for pill in pill_values)
    st.markdown(
        f"""
        <div class="cdss-patient-banner">
            <div class="cdss-patient-name">{name}｜{chart_no}</div>
            <div class="cdss-patient-meta">{pill_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _latest_order_value(detail: dict[str, pd.DataFrame], field: str, fallback: object = "") -> object:
    orders = detail.get("dialysis_orders", pd.DataFrame())
    if not orders.empty and field in orders.columns:
        values = orders[field].dropna().astype(str).str.strip()
        values = values[values != ""]
        if not values.empty:
            return values.iloc[0]
    return fallback


def _consume_navigation_query_params() -> None:
    selected_chart_no = _query_param_value(st.query_params.get("selected_chart_no"))
    patient_tab = _query_param_value(st.query_params.get("patient_tab"))
    handoff_row_id = _query_param_value(st.query_params.get("handoff_row_id"))
    if not selected_chart_no and not patient_tab and not handoff_row_id:
        return

    if selected_chart_no:
        st.session_state["selected_chart_no"] = selected_chart_no
    if patient_tab:
        st.session_state["patient_tab"] = patient_tab
        st.session_state["patient_tab_target"] = patient_tab
    if handoff_row_id:
        st.session_state["handoff_focus_row_id"] = handoff_row_id
    st.query_params.clear()


def _query_param_value(value: object) -> str:
    if isinstance(value, list):
        return str(value[0]).strip() if value else ""
    if value is None:
        return ""
    return str(value).strip()


def main() -> None:
    _load_deployment_settings()
    _ensure_demo_mode_database()
    db.ensure_database()
    _consume_navigation_query_params()
    page, current_user, current_role = _render_sidebar()
    if not current_user:
        st.info("請先在左側登入。第一次使用若尚未建立帳號，可用初始化登入進入人員設定建立帳號密碼。")
        return
    if page == "規則設定":
        _render_rule_settings(current_role)
        return
    if page == "病人清單":
        _render_patient_settings(current_user, current_role)
        return
    if page == "人員設定":
        _render_staff_settings(current_user, current_role)
        return
    if page == "本院藥物清單":
        _render_drug_settings(current_user, current_role)
        return

    schedules = db.schedules()
    list_col, detail_col = st.columns([0.8, 3.2], gap="medium")
    with list_col:
        filtered = _render_bed_filters(schedules)
        _render_due_handoff_alerts(filtered)
        selected_chart_no = _render_bed_board(filtered)
    with detail_col:
        if selected_chart_no:
            _render_patient_panel(selected_chart_no, current_user, current_role)
        else:
            st.info("請先從左側病人列表選取病人。")


def _load_deployment_settings() -> None:
    for key in ["DIALYSIS_CDSS_DEMO", "DIALYSIS_CDSS_DB_PATH"]:
        if os.getenv(key):
            continue
        try:
            value = st.secrets.get(key)
        except Exception:
            value = None
        if value is not None:
            os.environ[key] = str(value)


def _ensure_demo_mode_database() -> None:
    if os.getenv("DIALYSIS_CDSS_DEMO", "").strip() != "1":
        return
    from src.demo_data import ensure_demo_database

    demo_path = Path(os.getenv("DIALYSIS_CDSS_DB_PATH", str(db.ROOT / "data" / "dialysis_cdss_demo.sqlite")))
    os.environ["DIALYSIS_CDSS_DB_PATH"] = str(demo_path)
    ensure_demo_database(demo_path)


def _render_sidebar() -> None:
    st.sidebar.title("Dialysis CDSS")
    st.sidebar.caption("本機原型：CSV → SQLite → Streamlit")

    current_user, current_role = _render_login_sidebar()
    if not current_user:
        return "", "", ""

    page = st.sidebar.radio("頁面", ["查房工作台", "病人清單", "人員設定", "本院藥物清單", "規則設定"])

    if st.sidebar.button("重新同步 CSV", use_container_width=True):
        db.sync_seed_csv()
        st.sidebar.success("已同步")
        st.rerun()

    st.sidebar.divider()
    st.sidebar.caption("HIS/API 串接點仍保留在 src/adapters/hospital。")
    return page, current_user, current_role


def _render_login_sidebar() -> tuple[str, str]:
    if st.session_state.get("auth_user"):
        current_user = str(st.session_state.get("auth_user", ""))
        current_role = str(st.session_state.get("auth_role", ""))
        st.sidebar.caption(f"目前使用者：{current_user}")
        st.sidebar.caption(f"角色：{current_role or '未設定'}")
        if st.sidebar.button("登出", use_container_width=True):
            for key in ["auth_user", "auth_role", "auth_username", "auth_staff_id"]:
                st.session_state.pop(key, None)
            st.rerun()
        return current_user, current_role

    st.sidebar.subheader("登入")
    if db.staff_login_configured():
        with st.sidebar.form("login-form"):
            username = st.text_input("帳號")
            password = st.text_input("密碼", type="password")
            submitted = st.form_submit_button("登入", type="primary")
        if submitted:
            account = db.authenticate_staff(username, password)
            if account:
                st.session_state["auth_user"] = account.get("name", "")
                st.session_state["auth_role"] = account.get("role", "")
                st.session_state["auth_username"] = account.get("username", "")
                st.session_state["auth_staff_id"] = account.get("staff_id", "")
                st.rerun()
            st.sidebar.error("帳號或密碼錯誤。")
    else:
        st.sidebar.warning("尚未建立帳號密碼。請先用初始化登入進入人員設定。")
        staff = db.active_staff()
        names = staff["name"].dropna().astype(str).tolist() if not staff.empty else []
        bootstrap_user = st.sidebar.selectbox("初始化使用者", ["", *names])
        if st.sidebar.button("初始化登入", type="primary", use_container_width=True):
            if not bootstrap_user:
                st.sidebar.error("請選擇初始化使用者。")
            else:
                st.session_state["auth_user"] = bootstrap_user
                st.session_state["auth_role"] = db.staff_role(bootstrap_user)
                st.session_state["auth_username"] = ""
                st.session_state["auth_staff_id"] = ""
                st.rerun()
    return "", ""


def _render_bed_filters(schedules: pd.DataFrame) -> pd.DataFrame:
    total_count = len(schedules)
    st.markdown(f"## 床位總表｜{total_count} 人")
    if schedules.empty:
        st.warning("尚無床位資料，請先產生 seed CSV。")
        return schedules

    frequencies = sorted([x for x in schedules["frequency"].dropna().unique() if str(x).strip()])
    if not frequencies:
        frequencies = ["全部"]
    default_freq = st.session_state.get("bed_freq")
    if default_freq not in frequencies:
        default_freq = frequencies[0]

    freq_col, shift_col = st.columns(2, gap="small")
    with freq_col:
        _panel_title("頻率")
        freq = st.radio(
            "透析頻率",
            frequencies,
            index=frequencies.index(default_freq),
            label_visibility="collapsed",
            key="bed_freq",
        )

    shift_base = schedules[schedules["frequency"] == freq]
    shifts = sorted([x for x in shift_base["shift"].dropna().unique() if str(x).strip()])
    if not shifts:
        shifts = ["全部"]
    default_shift = st.session_state.get("bed_shift")
    if default_shift not in shifts:
        default_shift = shifts[0]

    with shift_col:
        _panel_title("班別")
        shift = st.radio(
            "班別",
            shifts,
            label_visibility="collapsed",
            key="bed_shift",
        )

    keyword = st.text_input("搜尋姓名 / 病歷號 / 床號", "", label_visibility="collapsed", placeholder="搜尋姓名 / 病歷號 / 床號")

    out = schedules.copy()
    out = out[out["frequency"] == freq]
    out = out[out["shift"] == shift]
    if keyword.strip():
        needle = keyword.strip()
        mask = (
            out["name"].astype(str).str.contains(needle, case=False, na=False)
            | out["chart_no"].astype(str).str.contains(needle, case=False, na=False)
            | out["bed"].astype(str).str.contains(needle, case=False, na=False)
        )
        out = out[mask]
    _compact_summary(f"{freq} > {shift}｜{len(out)} 人")
    return out


def _render_due_handoff_alerts(filtered_schedules: pd.DataFrame) -> None:
    due = db.due_handoffs(datetime.now().date().isoformat())
    if due.empty:
        return
    if not filtered_schedules.empty:
        visible_chart_nos = set(filtered_schedules["chart_no"].astype(str))
        due = due[due["chart_no"].astype(str).isin(visible_chart_nos)]
    if due.empty:
        return

    st.markdown("### 今日提醒")
    _alert_summary(f"待處理交班：{len(due)} 件")
    st.markdown('<div class="cdss-handoff-reminders">', unsafe_allow_html=True)
    with st.container():
        for row in due.head(5).itertuples(index=False):
            title = _clean_text(getattr(row, "title", ""))
            content = _clean_text(getattr(row, "content", ""))
            reminder_text = _truncate_text(content, 42) or title or "未填寫內容"
            label = f"{getattr(row, 'bed', '')}床 {getattr(row, 'name', '')}｜{reminder_text}"
            if st.button(
                label,
                key=f"handoff-reminder-{getattr(row, 'row_id', row.chart_no)}",
                use_container_width=True,
                type="primary",
            ):
                st.session_state["selected_chart_no"] = str(row.chart_no)
                st.session_state["patient_tab"] = "醫護交班"
                st.session_state["patient_tab_target"] = "醫護交班"
                st.session_state["handoff_focus_row_id"] = str(getattr(row, "row_id", ""))
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _render_bed_board(schedules: pd.DataFrame) -> str | None:
    if schedules.empty:
        st.info("目前篩選條件下沒有病人。")
        return None

    st.markdown("### 病人列表")
    schedules = _sort_by_bed(schedules)
    schedules = schedules.reset_index(drop=True)
    available_chart_nos = schedules["chart_no"].astype(str).tolist()
    selected_chart_no = st.session_state.get("selected_chart_no")
    if selected_chart_no not in available_chart_nos:
        selected_chart_no = available_chart_nos[0]
        st.session_state["selected_chart_no"] = selected_chart_no

    with st.container(height=640, border=True):
        for row in schedules.itertuples(index=False):
            chart_no = str(row.chart_no)
            selected_mark = "▶ " if chart_no == selected_chart_no else ""
            label = f"{selected_mark}{row.bed}床 {row.name} {row.chart_no} AK {row.dialyzer} Ca {row.dialysate_ca}"
            button_type = "primary" if chart_no == selected_chart_no else "secondary"
            if st.button(label, key=f"patient-row-{chart_no}", use_container_width=True, type=button_type):
                st.session_state["selected_chart_no"] = chart_no
                selected_chart_no = chart_no
                st.rerun()

    return selected_chart_no


def _render_patient_panel(chart_no: str, current_user: str, current_role: str) -> None:
    detail = db.patient_detail(chart_no)
    patient = detail["patient"]
    if patient.empty:
        st.warning("找不到病人資料。")
        return

    p = patient.iloc[0]

    schedule = detail["schedule"]
    if not schedule.empty:
        s = schedule.iloc[0]
        dry_weight = _latest_order_value(detail, "dry_weight", "")
        dialyzer = _latest_order_value(detail, "dialyzer", s.get("dialyzer", ""))
        dialysate_ca = _latest_order_value(detail, "dialysate_ca", s.get("dialysate_ca", ""))
        _patient_compact_header(p, s, dry_weight, dialyzer, dialysate_ca)
    else:
        _patient_compact_header(
            p,
            None,
            _latest_order_value(detail, "dry_weight", ""),
            _latest_order_value(detail, "dialyzer", ""),
            _latest_order_value(detail, "dialysate_ca", ""),
        )

    tab_options = [
        "主要問題",
        "近期事件",
        "醫護交班",
        "透析醫囑",
        "抽血 / 藥物建議",
    ]
    tab_key = f"patient-tab-{chart_no}"
    target_tab = st.session_state.pop("patient_tab_target", None)
    if target_tab in tab_options:
        st.session_state[tab_key] = target_tab
    elif tab_key not in st.session_state:
        st.session_state[tab_key] = st.session_state.get("patient_tab", tab_options[0])

    selected_tab = st.segmented_control(
        "病人資料頁籤",
        tab_options,
        key=tab_key,
        required=True,
        label_visibility="collapsed",
        width="stretch",
    )
    st.session_state["patient_tab"] = selected_tab

    if selected_tab == "主要問題":
        _render_problem_list(chart_no, p, detail["problem_list"], current_user, current_role)
    elif selected_tab == "近期事件":
        _render_clinical_events(chart_no, p, detail["clinical_events"], current_user, current_role)
    elif selected_tab == "醫護交班":
        _render_handoffs(chart_no, p, detail["handoffs"], current_user, current_role)
    elif selected_tab == "透析醫囑":
        _render_dialysis_orders(chart_no, p, schedule, detail["dialysis_orders"], current_user, current_role)
    elif selected_tab == "抽血 / 藥物建議":
        _render_recommendations(chart_no, detail)


def _render_rule_settings(current_role: str) -> None:
    st.header("規則設定")
    if not _can_edit(current_role, "rule_settings"):
        st.info("你可以查看規則設定；只有醫師可以編輯。")
        _render_rule_summary(load_dose_rules())
        return
    st.warning("第一版設定頁：調整後會影響前台劑量建議草稿。正式臨床使用前仍需院內規則審核。")
    rules = load_dose_rules()

    with st.form("dose-rules-form"):
        st.subheader("ESA")
        esa = rules.setdefault("esa", {})
        esa["enabled"] = st.checkbox("啟用 ESA 劑量建議", bool(esa.get("enabled", True)))
        c1, c2, c3 = st.columns(3)
        esa["hb_low"] = c1.number_input("Hb 下限", value=float(esa.get("hb_low", 10.0)), step=0.1)
        esa["hb_high"] = c2.number_input("Hb 上限", value=float(esa.get("hb_high", 11.5)), step=0.1)
        esa["hold_if_hb_above"] = c3.number_input("Hb 達此值建議暫停/大幅減量", value=float(esa.get("hold_if_hb_above", 12.5)), step=0.1)
        c4, c5 = st.columns(2)
        esa["increase_percent"] = c4.number_input("ESA 增量百分比", value=int(esa.get("increase_percent", 25)), step=5)
        esa["decrease_percent"] = c5.number_input("ESA 減量百分比", value=int(esa.get("decrease_percent", 25)), step=5)
        esa["require_iron_replete_before_increase"] = st.checkbox("ESA 增量前需鐵狀態足夠", bool(esa.get("require_iron_replete_before_increase", True)))

        st.subheader("鐵劑")
        iron = rules.setdefault("iron", {})
        iron["enabled"] = st.checkbox("啟用鐵劑建議", bool(iron.get("enabled", True)))
        c1, c2, c3, c4 = st.columns(4)
        iron["ferritin_low"] = c1.number_input("Ferritin 低值", value=float(iron.get("ferritin_low", 100)), step=10.0)
        iron["tsat_low"] = c2.number_input("TSAT 低值", value=float(iron.get("tsat_low", 20)), step=1.0)
        iron["ferritin_hold_above"] = c3.number_input("Ferritin 暫緩值", value=float(iron.get("ferritin_hold_above", 500)), step=10.0)
        iron["tsat_hold_above"] = c4.number_input("TSAT 暫緩值", value=float(iron.get("tsat_hold_above", 45)), step=1.0)
        iron["suggested_iv_iron_dose"] = st.text_input("建議 IV iron 劑量文字", value=str(iron.get("suggested_iv_iron_dose", "Venofer 100mg")))
        iron["suggested_iv_iron_frequency"] = st.text_input("建議 IV iron 頻率文字", value=str(iron.get("suggested_iv_iron_frequency", "每次透析後，連續 5 次；需醫師確認")))

        st.subheader("CKD-MBD")
        mbd = rules.setdefault("mbd", {})
        mbd["enabled"] = st.checkbox("啟用 CKD-MBD 建議", bool(mbd.get("enabled", True)))
        c1, c2, c3, c4 = st.columns(4)
        mbd["phosphate_high"] = c1.number_input("P 高值", value=float(mbd.get("phosphate_high", 5.5)), step=0.1)
        mbd["corrected_calcium_high"] = c2.number_input("cCa 高值", value=float(mbd.get("corrected_calcium_high", 10.2)), step=0.1)
        mbd["calcium_phosphate_product_high"] = c3.number_input("CaXP 高值", value=float(mbd.get("calcium_phosphate_product_high", 55)), step=1.0)
        mbd["ipth_high"] = c4.number_input("iPTH 高值", value=float(mbd.get("ipth_high", 600)), step=10.0)
        mbd["calcium_binder_decrease_percent"] = st.number_input("含鈣降磷藥減量百分比", value=int(mbd.get("calcium_binder_decrease_percent", 25)), step=5)

        st.subheader("安全")
        safety = rules.setdefault("safety", {})
        safety["require_physician_approval"] = st.checkbox("所有劑量建議都需醫師簽核", bool(safety.get("require_physician_approval", True)))
        safety["show_mock_data_warning"] = st.checkbox("顯示 mock data 警示", bool(safety.get("show_mock_data_warning", True)))

        submitted = st.form_submit_button("儲存規則設定", type="primary")
        if submitted:
            rules["last_updated"] = _now().split("T", 1)[0]
            save_dose_rules(rules)
            st.success("已儲存規則設定")


def _render_rule_summary(rules: dict) -> None:
    esa = rules.get("esa", {})
    iron = rules.get("iron", {})
    mbd = rules.get("mbd", {})
    safety = rules.get("safety", {})

    st.subheader("ESA")
    st.dataframe(pd.DataFrame([
        {"項目": "是否啟用", "設定值": _yes_no(esa.get("enabled", True))},
        {"項目": "Hb 下限", "設定值": esa.get("hb_low", "")},
        {"項目": "Hb 上限", "設定值": esa.get("hb_high", "")},
        {"項目": "暫停/大幅減量門檻", "設定值": esa.get("hold_if_hb_above", "")},
        {"項目": "建議增量百分比", "設定值": f"{esa.get('increase_percent', '')}%"},
        {"項目": "建議減量百分比", "設定值": f"{esa.get('decrease_percent', '')}%"},
        {"項目": "增量前需鐵狀態足夠", "設定值": _yes_no(esa.get("require_iron_replete_before_increase", True))},
    ]), use_container_width=True, hide_index=True)

    st.subheader("鐵劑")
    st.dataframe(pd.DataFrame([
        {"項目": "是否啟用", "設定值": _yes_no(iron.get("enabled", True))},
        {"項目": "Ferritin 低值", "設定值": iron.get("ferritin_low", "")},
        {"項目": "TSAT 低值", "設定值": iron.get("tsat_low", "")},
        {"項目": "Ferritin 暫緩值", "設定值": iron.get("ferritin_hold_above", "")},
        {"項目": "TSAT 暫緩值", "設定值": iron.get("tsat_hold_above", "")},
        {"項目": "建議 IV iron 劑量", "設定值": iron.get("suggested_iv_iron_dose", "")},
        {"項目": "建議 IV iron 頻率", "設定值": iron.get("suggested_iv_iron_frequency", "")},
    ]), use_container_width=True, hide_index=True)

    st.subheader("CKD-MBD")
    st.dataframe(pd.DataFrame([
        {"項目": "是否啟用", "設定值": _yes_no(mbd.get("enabled", True))},
        {"項目": "P 高值", "設定值": mbd.get("phosphate_high", "")},
        {"項目": "cCa 高值", "設定值": mbd.get("corrected_calcium_high", "")},
        {"項目": "CaXP 高值", "設定值": mbd.get("calcium_phosphate_product_high", "")},
        {"項目": "iPTH 高值", "設定值": mbd.get("ipth_high", "")},
        {"項目": "含鈣降磷藥減量百分比", "設定值": f"{mbd.get('calcium_binder_decrease_percent', '')}%"},
    ]), use_container_width=True, hide_index=True)

    st.subheader("安全設定")
    st.dataframe(pd.DataFrame([
        {"項目": "所有劑量建議都需醫師簽核", "設定值": _yes_no(safety.get("require_physician_approval", True))},
        {"項目": "顯示 mock data 警示", "設定值": _yes_no(safety.get("show_mock_data_warning", True))},
    ]), use_container_width=True, hide_index=True)


def _render_patient_settings(current_user: str, current_role: str) -> None:
    st.header("病人清單")
    st.caption("維護洗腎室現有病人與床位資料。轉出病人不會刪除既有問題、事件、交班或醫囑紀錄。")

    patient_columns = [
        "chart_no",
        "deid",
        "name",
        "frequency",
        "shift",
        "bed",
        "dialyzer",
        "dialysate_ca",
        "active",
        "created_by",
        "created_at",
        "inactive_at",
        "note",
    ]
    visible_columns = [
        "chart_no",
        "deid",
        "name",
        "frequency",
        "shift",
        "bed",
        "dialyzer",
        "dialysate_ca",
        "created_by",
        "created_at",
        "inactive_at",
    ]
    patients = db.patient_registry()
    if patients.empty:
        patients = pd.DataFrame(columns=patient_columns)
    for col in patient_columns:
        if col not in patients.columns:
            patients[col] = ""
    patients = patients[patient_columns].copy()
    patients["inactive_at"] = pd.to_datetime(patients["inactive_at"], errors="coerce").dt.date

    if not _can_edit(current_role, "patient_settings"):
        st.info("你可以查看病人清單；只有醫師或護理長可以新增與編輯。")
        display = patients[visible_columns].copy()
        display.columns = [
            "病歷號",
            "去識別 ID",
            "姓名",
            "頻率",
            "班別",
            "床位",
            "人工腎臟",
            "藥水 Ca",
            "新增者",
            "新增時間",
            "轉出時間",
        ]
        st.dataframe(display, use_container_width=True, hide_index=True)
        return

    st.caption(f"目前操作人員：{current_user or '未選擇'}")
    st.info("新增病人時至少填寫病歷號、姓名與透析日。新增後會同步建立第一筆透析醫囑。")

    with st.form("new-patient-form", clear_on_submit=True):
        st.markdown("#### 新增病人")
        c1, c2, c3 = st.columns([1, 1, 1])
        chart_no = c1.text_input("病歷號")
        deid = c2.text_input("去識別 ID", placeholder="可留空自動產生")
        name = c3.text_input("姓名")

        c1, c2 = st.columns([2, 1])
        dialysis_days = c1.segmented_control(
            "透析日",
            ["一", "二", "三", "四", "五", "六"],
            selection_mode="multi",
            width="stretch",
        )
        frequency = _days_to_frequency(dialysis_days or [])
        shift = c2.segmented_control(
            "班別",
            ["早班", "午班", "晚班"],
            default="午班",
            width="stretch",
        )

        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        bed = c1.text_input("床位")
        dialyzer = c2.text_input("人工腎臟")
        dialysate_ca = c3.text_input("藥水 Ca")
        dry_weight = c4.text_input("DW")

        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        blood_flow = c1.text_input("Blood flow")
        dialysate_flow = c2.text_input("Dialysate flow")
        anticoagulant_loading = c3.text_input("抗凝 Loading")
        anticoagulant_maintain = c4.text_input("抗凝 Maintain")
        submitted = st.form_submit_button("新增病人", type="primary")

    if submitted:
        if not chart_no.strip() or not name.strip():
            st.warning("請至少填寫病歷號與姓名。")
        elif not dialysis_days:
            st.warning("請至少選擇一個透析日。")
        elif chart_no.strip() in set(patients["chart_no"].astype(str).str.strip()):
            st.warning("這個病歷號已存在，請在下方既有病人清單編輯。")
        else:
            now = _now()
            deid_value = deid.strip() or f"P{now.replace(':', '').replace('-', '')[-6:]}00"
            new = pd.DataFrame([{
                "chart_no": chart_no.strip(),
                "deid": deid_value,
                "name": name.strip(),
                "frequency": frequency.strip(),
                "shift": str(shift).strip(),
                "bed": bed.strip(),
                "dialyzer": dialyzer.strip(),
                "dialysate_ca": dialysate_ca.strip(),
                "active": "啟用",
                "created_by": current_user.strip() or "unknown",
                "created_at": now,
                "inactive_at": "",
                "note": "",
            }])
            saved = pd.concat([patients.fillna(""), new], ignore_index=True)
            saved["inactive_at"] = saved["inactive_at"].map(_format_date_value)
            db.replace_patient_registry(saved)
            db.replace_patient_rows(
                "dialysis_orders",
                chart_no.strip(),
                pd.DataFrame([_initial_dialysis_order_record(
                    chart_no=chart_no.strip(),
                    deid=deid_value,
                    name=name.strip(),
                    frequency=frequency,
                    dialysis_days=dialysis_days,
                    shift=str(shift).strip(),
                    bed=bed.strip(),
                    dialyzer=dialyzer.strip(),
                    dialysate_ca=dialysate_ca.strip(),
                    dry_weight=dry_weight.strip(),
                    blood_flow=blood_flow.strip(),
                    dialysate_flow=dialysate_flow.strip(),
                    anticoagulant_loading=anticoagulant_loading.strip(),
                    anticoagulant_maintain=anticoagulant_maintain.strip(),
                    current_user=current_user,
                    now=now,
                )]),
            )
            st.success("已新增病人")
            st.rerun()

    st.markdown("#### 既有病人清單")
    edited = st.data_editor(
        patients[visible_columns],
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "chart_no": st.column_config.TextColumn("病歷號", required=True),
            "deid": st.column_config.TextColumn("去識別 ID", help="可留空，儲存時自動產生"),
            "name": st.column_config.TextColumn("姓名", required=True),
            "frequency": st.column_config.TextColumn("頻率", help="例如：一三五、二四六、一五"),
            "shift": st.column_config.TextColumn("班別", help="例如：早班、午班、晚班"),
            "bed": st.column_config.TextColumn("床位"),
            "dialyzer": st.column_config.TextColumn("人工腎臟"),
            "dialysate_ca": st.column_config.TextColumn("藥水 Ca"),
            "created_by": st.column_config.TextColumn("新增者", disabled=True),
            "created_at": st.column_config.TextColumn("新增時間", disabled=True),
            "inactive_at": st.column_config.DateColumn("轉出時間", format="YYYY-MM-DD"),
        },
        disabled=["created_by", "created_at"],
        key="patient-registry-editor",
    )

    if st.button("儲存病人清單", type="primary"):
        saved = edited.fillna("").copy()
        saved["active"] = ""
        now = _now()
        for idx, row in saved.iterrows():
            chart_no = str(row.get("chart_no", "")).strip()
            name = str(row.get("name", "")).strip()
            if not chart_no and not name:
                continue
            if not chart_no or not name:
                st.warning("病人清單中有資料列缺少病歷號或姓名，請補齊後再儲存。")
                return
            if not str(row.get("deid", "")).strip():
                saved.at[idx, "deid"] = f"P{now.replace(':', '').replace('-', '')[-6:]}{idx:02d}"
            saved.at[idx, "inactive_at"] = _format_date_value(row.get("inactive_at"))
            saved.at[idx, "active"] = "停用" if saved.at[idx, "inactive_at"] else "啟用"
            if not str(row.get("created_at", "")).strip():
                saved.at[idx, "created_at"] = now
            if not str(row.get("created_by", "")).strip():
                saved.at[idx, "created_by"] = current_user.strip() or "unknown"

        saved = saved[
            (saved["chart_no"].astype(str).str.strip() != "")
            & (saved["name"].astype(str).str.strip() != "")
        ]
        db.replace_patient_registry(saved)
        st.success("已儲存病人清單")
        st.rerun()


def _render_staff_settings(current_user: str, current_role: str) -> None:
    st.header("人員設定")
    first_setup = not db.staff_login_configured()
    can_edit = _can_edit(current_role, "staff_settings") or first_setup
    if not can_edit:
        st.info("你可以查看人員名單；只有醫師或護理長可以編輯。")
        view = db.staff()
        if not view.empty:
            safe_view = _staff_display_frame(view)
            st.dataframe(safe_view, use_container_width=True, hide_index=True)
        return
    if first_setup:
        st.warning("目前尚未建立正式登入帳號。請至少建立一位醫師或護理長帳號密碼。")
    st.caption("新增、停用人員與帳號都在這裡處理。密碼只會儲存 hash，不會儲存明碼。")
    st.caption(f"目前操作人員：{current_user or '未選擇'}")

    staff = db.staff()
    if staff.empty:
        staff = pd.DataFrame(columns=_staff_columns())
    for col in _staff_columns():
        if col not in staff.columns:
            staff[col] = ""
    staff = staff[_staff_columns()].copy()
    staff["active"] = staff["active"].map(_normalize_active_label)

    with st.form("new-staff-form", clear_on_submit=True):
        st.markdown("#### 新增人員")
        c1, c2, c3 = st.columns([1, 1, 1])
        name = c1.text_input("姓名")
        role = c2.selectbox("角色", ["醫師", "護理長", "護理師"], index=2)
        username = c3.text_input("帳號")
        c1, c2 = st.columns([1, 2])
        password = c1.text_input("初始密碼", type="password")
        note = c2.text_input("備註")
        submitted = st.form_submit_button("新增人員", type="primary")

    if submitted:
        if not name.strip() or not username.strip() or not password:
            st.warning("請填寫姓名、帳號與初始密碼。")
        elif username.strip().lower() in set(staff["username"].astype(str).str.lower().str.strip()):
            st.warning("此帳號已存在，請使用其他帳號。")
        else:
            now = _now()
            new = pd.DataFrame([{
                "staff_id": f"staff-{now.replace(':', '').replace('-', '')}",
                "name": name.strip(),
                "role": role,
                "active": "啟用",
                "created_by": current_user.strip() or "bootstrap",
                "created_at": now,
                "inactive_at": "",
                "note": note.strip(),
                "username": username.strip(),
                "password_hash": db.hash_password(password),
                "password_set_at": now,
            }])
            db.replace_staff(pd.concat([staff.fillna(""), new], ignore_index=True))
            st.success("已新增人員")
            st.rerun()

    st.markdown("#### 既有人員")
    visible_columns = ["staff_id", "name", "role", "username", "active", "created_by", "created_at", "inactive_at", "note"]
    edited = st.data_editor(
        staff[visible_columns],
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config={
            "staff_id": st.column_config.TextColumn("人員 ID", help="可留空，儲存時自動產生"),
            "name": st.column_config.TextColumn("姓名", required=True),
            "role": st.column_config.SelectboxColumn("角色", options=["醫師", "護理長", "護理師"], required=True),
            "username": st.column_config.TextColumn("帳號"),
            "active": st.column_config.SelectboxColumn("狀態", options=["啟用", "停用"], required=True),
            "created_by": st.column_config.TextColumn("新增者", disabled=True),
            "created_at": st.column_config.TextColumn("新增時間", disabled=True),
            "inactive_at": st.column_config.TextColumn("停用時間", disabled=True),
            "note": st.column_config.TextColumn("備註"),
        },
        disabled=["staff_id", "created_by", "created_at", "inactive_at"],
        key="staff-editor",
    )

    if st.button("儲存人員設定", type="primary"):
        saved = staff.copy()
        edited = edited.fillna("").copy()
        for col in ["name", "role", "username", "active", "note"]:
            saved[col] = edited[col]
        now = _now()
        for idx, row in saved.iterrows():
            if not str(row.get("name", "")).strip():
                continue
            if not str(row.get("staff_id", "")).strip():
                saved.at[idx, "staff_id"] = f"staff-{now.replace(':', '').replace('-', '')}-{idx}"
            if not str(row.get("role", "")).strip():
                saved.at[idx, "role"] = "護理師"
            if not str(row.get("active", "")).strip():
                saved.at[idx, "active"] = "啟用"
            if not str(row.get("created_at", "")).strip():
                saved.at[idx, "created_at"] = now
            if not str(row.get("created_by", "")).strip():
                saved.at[idx, "created_by"] = current_user.strip() or "unknown"
            if str(row.get("active", "")).strip() == "停用" and not str(row.get("inactive_at", "")).strip():
                saved.at[idx, "inactive_at"] = now
            if str(row.get("active", "")).strip() == "啟用":
                saved.at[idx, "inactive_at"] = ""

        saved = saved[saved["name"].astype(str).str.strip() != ""]
        db.replace_staff(saved)
        st.success("已儲存人員設定")
        st.rerun()

    st.markdown("#### 重設密碼")
    active_staff = staff[staff["active"].map(_normalize_active_label) == "啟用"].copy()
    staff_options = active_staff["name"].dropna().astype(str).tolist()
    if not staff_options:
        st.info("目前沒有啟用中的人員可重設密碼。")
    else:
        with st.form("reset-password-form"):
            c1, c2 = st.columns([1, 1])
            reset_name = c1.selectbox("人員", staff_options)
            new_password = c2.text_input("新密碼", type="password")
            reset_submitted = st.form_submit_button("重設密碼")
        if reset_submitted:
            if not reset_name or not new_password:
                st.warning("請選擇人員並輸入新密碼。")
            else:
                now = _now()
                saved = staff.copy()
                mask = saved["name"].astype(str) == reset_name
                saved.loc[mask, "password_hash"] = db.hash_password(new_password)
                saved.loc[mask, "password_set_at"] = now
                db.replace_staff(saved)
                st.success("已重設密碼")
                st.rerun()


def _render_drug_settings(current_user: str, current_role: str) -> None:
    st.header("本院藥物清單")
    st.caption("維護本院常用透析相關藥物。停用不會刪除紀錄，會保留新增者與新增時間。")
    if not _can_edit(current_role, "drug_settings"):
        st.info("你可以查看藥物清單；只有醫師可以編輯。")
        view = db.hospital_drugs()
        if not view.empty:
            st.dataframe(view, use_container_width=True, hide_index=True)
        return

    st.caption(f"目前操作人員：{current_user or '未選擇'}")
    drugs = db.hospital_drugs()
    if drugs.empty:
        drugs = pd.DataFrame(columns=["drug_id", "drug_type", "drug_name", "default_unit", "active", "created_by", "created_at", "inactive_at", "note"])
    for col in ["drug_id", "drug_type", "drug_name", "default_unit", "active", "created_by", "created_at", "inactive_at", "note"]:
        if col not in drugs.columns:
            drugs[col] = ""
    drugs = drugs[["drug_id", "drug_type", "drug_name", "default_unit", "active", "created_by", "created_at", "inactive_at", "note"]].copy()
    drugs["active"] = drugs["active"].map(lambda x: "啟用" if str(x).strip() in {"True", "true", "1", "Active", "啟用"} else "停用")

    edited = st.data_editor(
        drugs,
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "drug_id": st.column_config.TextColumn("藥物 ID", help="可留空，儲存時自動產生"),
            "drug_type": st.column_config.SelectboxColumn("類型", options=["ESA", "降磷藥", "降鉀藥", "副甲狀腺亢進藥物"], required=True),
            "drug_name": st.column_config.TextColumn("藥名", required=True),
            "default_unit": st.column_config.TextColumn("預設單位"),
            "active": st.column_config.SelectboxColumn("狀態", options=["啟用", "停用"], required=True),
            "created_by": st.column_config.TextColumn("新增者", disabled=True),
            "created_at": st.column_config.TextColumn("新增時間", disabled=True),
            "inactive_at": st.column_config.TextColumn("停用時間", disabled=True),
            "note": st.column_config.TextColumn("備註"),
        },
        key="drug-editor",
    )

    if st.button("儲存藥物清單", type="primary"):
        saved = edited.fillna("").copy()
        now = _now()
        for idx, row in saved.iterrows():
            if not str(row.get("drug_name", "")).strip():
                continue
            if not str(row.get("drug_id", "")).strip():
                saved.at[idx, "drug_id"] = f"drug-{now.replace(':', '').replace('-', '')}-{idx}"
            if not str(row.get("drug_type", "")).strip():
                saved.at[idx, "drug_type"] = "ESA"
            if not str(row.get("active", "")).strip():
                saved.at[idx, "active"] = "啟用"
            if not str(row.get("created_at", "")).strip():
                saved.at[idx, "created_at"] = now
            if not str(row.get("created_by", "")).strip():
                saved.at[idx, "created_by"] = current_user.strip() or "unknown"
            if str(row.get("active", "")).strip() == "停用" and not str(row.get("inactive_at", "")).strip():
                saved.at[idx, "inactive_at"] = now
            if str(row.get("active", "")).strip() == "啟用":
                saved.at[idx, "inactive_at"] = ""

        saved = saved[saved["drug_name"].astype(str).str.strip() != ""]
        db.replace_hospital_drugs(saved)
        st.success("已儲存藥物清單")
        st.rerun()


def _render_problem_list(chart_no: str, patient: pd.Series, problems: pd.DataFrame, current_user: str, current_role: str) -> None:
    can_edit = _can_edit(current_role, "problem_list")
    if can_edit:
        with st.form(f"problem-form-{chart_no}", clear_on_submit=True):
            problem = st.text_area("主要問題", height=90)
            c1, c2 = st.columns([1, 1])
            status = c1.selectbox("狀態", ["Active", "Inactive"])
            owner_role = c2.selectbox("負責角色", ["醫師", "護理長", "護理師"], index=2)
            note = st.text_input("備註")
            submitted = st.form_submit_button("新增主要問題", type="primary")

        if submitted:
            if not problem.strip():
                st.warning("請填寫主要問題。")
            else:
                now = _now()
                new = pd.DataFrame([{
                    "chart_no": chart_no,
                    "deid": patient.get("deid", ""),
                    "name": patient.get("name", ""),
                    "problem": problem.strip(),
                    "status": status,
                    "owner_role": owner_role,
                    "updated_by": current_user or "unknown",
                    "updated_at": now,
                    "note": note.strip(),
                    "row_id": f"problem_list-{chart_no}-{now.replace(':', '').replace('-', '')}",
                }])
                saved = pd.concat([problems.fillna(""), new], ignore_index=True)
                db.replace_patient_rows("problem_list", chart_no, saved)
                st.success("已新增主要問題")
                st.rerun()
    else:
        st.info("目前角色可查看主要問題，沒有編輯權限。")

    if problems.empty:
        st.info("目前沒有主要問題紀錄。")
        return

    st.markdown("#### 既有主要問題")
    _editable_existing_records(
        "problem_list",
        chart_no,
        problems,
        ["problem", "status", "owner_role", "updated_by", "updated_at", "note"],
        can_edit,
        current_user,
        key_suffix="problem",
    )


def _render_clinical_events(chart_no: str, patient: pd.Series, events: pd.DataFrame, current_user: str, current_role: str) -> None:
    can_edit = _can_edit(current_role, "clinical_events")
    event_titles = [
        "血管通路問題",
        "心臟問題(心肌梗塞、心衰竭)",
        "感染問題",
        "周邊血管問題(PAOD)",
        "呼吸衰竭(插管、BiPAP)",
        "其他",
    ]
    if can_edit:
        with st.form(f"event-form-{chart_no}", clear_on_submit=True):
            c1, c2, c3 = st.columns([1, 1, 2])
            event_date = c1.date_input("事件日期", value=datetime.now().date())
            event_type = c2.selectbox("事件類型", ["急診", "住院", "門診"])
            title = c3.selectbox("事件標題", event_titles)
            event_content = st.text_area("事件內容", height=110)
            submitted = st.form_submit_button("新增近期事件", type="primary")

        if submitted:
            now = _now()
            new = pd.DataFrame([{
                "chart_no": chart_no,
                "deid": patient.get("deid", ""),
                "name": patient.get("name", ""),
                "event_type": event_type,
                "event_date": event_date.isoformat(),
                "title": title,
                "event_content": event_content.strip(),
                "source": "manual",
                "updated_by": current_user or "unknown",
                "updated_at": now,
                "note": "",
                "row_id": f"clinical_events-{chart_no}-{now.replace(':', '').replace('-', '')}",
            }])
            saved = pd.concat([events.fillna(""), new], ignore_index=True)
            db.replace_patient_rows("clinical_events", chart_no, saved)
            st.success("已新增近期事件")
            st.rerun()
    else:
        st.info("目前角色可查看近期事件，沒有編輯權限。")

    if events.empty:
        st.info("目前沒有近期事件紀錄。")
        return

    st.markdown("#### 既有近期事件")
    _editable_existing_records(
        "clinical_events",
        chart_no,
        events,
        ["event_date", "event_type", "title", "event_content", "updated_by", "updated_at"],
        can_edit,
        current_user,
        key_suffix="events",
    )


def _render_handoffs(chart_no: str, patient: pd.Series, handoffs: pd.DataFrame, current_user: str, current_role: str) -> None:
    can_edit = _can_edit(current_role, "handoffs")
    if can_edit:
        st.caption("新增交班後，目標日期到期且狀態未完成時，會出現在左側今日提醒。")
        with st.form(f"handoff-form-{chart_no}", clear_on_submit=True):
            c1, c2, c3 = st.columns([1, 1, 1])
            target_date = c1.date_input("目標日期", value=datetime.now().date())
            handoff_type = c2.selectbox("交班類型", ["共同交班", "醫師交班", "護理交班"])
            priority = c3.selectbox("優先度", ["一般", "重要", "緊急"])
            title = st.text_input("事件標題")
            content = st.text_area("交班內容", height=110)
            submitted = st.form_submit_button("新增交班", type="primary")

        if submitted:
            if not title.strip() and not content.strip():
                st.warning("請至少填寫事件標題或交班內容。")
            else:
                now = _now()
                new = pd.DataFrame([{
                    "chart_no": chart_no,
                    "deid": patient.get("deid", ""),
                    "name": patient.get("name", ""),
                    "target_date": target_date.isoformat(),
                    "handoff_type": handoff_type,
                    "title": title.strip(),
                    "content": content.strip(),
                    "priority": priority,
                    "status": "未處理",
                    "created_by": current_user or "unknown",
                    "created_at": now,
                    "updated_by": current_user or "unknown",
                    "updated_at": now,
                    "row_id": f"handoffs-{chart_no}-{now.replace(':', '').replace('-', '')}",
                }])
                saved = pd.concat([handoffs.fillna(""), new], ignore_index=True)
                db.replace_patient_rows("handoffs", chart_no, saved)
                st.success("已新增交班")
                st.rerun()
    else:
        st.info("目前角色可查看交班，沒有編輯權限。")

    if handoffs.empty:
        st.info("目前沒有交班紀錄。")
        return

    st.markdown("#### 既有交班")
    focus_row_id = st.session_state.get("handoff_focus_row_id")
    if focus_row_id and "row_id" in handoffs.columns:
        focus_mask = handoffs["row_id"].astype(str) == str(focus_row_id)
        if focus_mask.any():
            focused = handoffs[focus_mask].iloc[0]
            focus_text = _clean_text(focused.get("title")) or _truncate_text(focused.get("content"), 40) or "未填寫內容"
            st.info(f"已從今日提醒開啟：{focus_text}")
            handoffs = pd.concat([handoffs[focus_mask], handoffs[~focus_mask]], ignore_index=True)
    _editable_existing_records(
        "handoffs",
        chart_no,
        handoffs,
        ["target_date", "handoff_type", "title", "content", "priority", "status", "created_by", "created_at", "updated_by", "updated_at"],
        can_edit,
        current_user,
        key_suffix="handoffs",
    )


def _initial_dialysis_order_record(
    chart_no: str,
    deid: str,
    name: str,
    frequency: str,
    dialysis_days: list[str],
    shift: str,
    bed: str,
    dialyzer: str,
    dialysate_ca: str,
    dry_weight: str,
    blood_flow: str,
    dialysate_flow: str,
    anticoagulant_loading: str,
    anticoagulant_maintain: str,
    current_user: str,
    now: str,
) -> dict[str, str]:
    effective_date = datetime.now().date()
    anticoagulant_parts = []
    if anticoagulant_loading:
        anticoagulant_parts.append(f"Loading {anticoagulant_loading}")
    if anticoagulant_maintain:
        anticoagulant_parts.append(f"Maintain {anticoagulant_maintain}")
    return {
        "chart_no": chart_no,
        "deid": deid,
        "name": name,
        "order_month": effective_date.strftime("%Y%m"),
        "effective_date": effective_date.isoformat(),
        "dialysis_days": ",".join(dialysis_days),
        "frequency": frequency,
        "shift": shift,
        "bed": bed,
        "dialyzer": dialyzer,
        "dialysate_ca": dialysate_ca,
        "dialysate_flow": dialysate_flow,
        "blood_flow": blood_flow,
        "dry_weight": dry_weight,
        "anticoagulant_loading": anticoagulant_loading,
        "anticoagulant_maintain": anticoagulant_maintain,
        "anticoagulant": " / ".join(anticoagulant_parts),
        "access_side": "",
        "access_type": "",
        "vascular_access": "",
        "updated_by": current_user.strip() or "unknown",
        "updated_at": now,
        "note": "新增病人時自動建立",
        "row_id": f"dialysis_orders-{chart_no}-{now.replace(':', '').replace('-', '')}",
    }


def _render_dialysis_orders(
    chart_no: str,
    patient: pd.Series,
    schedule: pd.DataFrame,
    orders: pd.DataFrame,
    current_user: str,
    current_role: str,
) -> None:
    can_edit = _can_edit(current_role, "dialysis_orders")
    current_schedule = schedule.iloc[0] if not schedule.empty else pd.Series(dtype=object)
    if can_edit:
        with st.form(f"dialysis-order-form-{chart_no}", clear_on_submit=True):
            c1, c2 = st.columns([1, 2])
            effective_date = c1.date_input("生效日期", value=datetime.now().date())
            default_days = _frequency_to_days(current_schedule.get("frequency", ""))
            dialysis_days = c2.segmented_control(
                "透析日",
                ["一", "二", "三", "四", "五", "六"],
                selection_mode="multi",
                default=default_days,
                width="stretch",
            )
            frequency = _days_to_frequency(dialysis_days)
            st.caption(f"系統解讀頻率：{frequency or '未選擇'}")

            c1, c2, c3, c4 = st.columns(4)
            shift_options = ["早班", "午班", "晚班"]
            current_shift = str(current_schedule.get("shift", "")).strip()
            shift_index = shift_options.index(current_shift) if current_shift in shift_options else 1
            shift = c1.radio("班別", shift_options, index=shift_index, horizontal=True)
            bed = c2.text_input("床位", value=str(current_schedule.get("bed", "")).strip())
            dialyzer = c3.text_input("AK", value=str(current_schedule.get("dialyzer", "")).strip())
            dialysate_ca = c4.text_input("藥水 Ca", value=str(current_schedule.get("dialysate_ca", "")).strip())

            c1, c2, c3 = st.columns(3)
            blood_flow = c1.text_input("Blood flow")
            dialysate_flow = c2.text_input("Dialysate flow")
            dry_weight = c3.text_input("Dry weight")

            c1, c2 = st.columns(2)
            anticoagulant_loading = c1.text_input("抗凝 Loading")
            anticoagulant_maintain = c2.text_input("抗凝 Maintain")

            c1, c2 = st.columns(2)
            access_side = c1.radio("血管通路側別", ["左", "右"], horizontal=True)
            access_type = c2.radio("血管通路類型", ["FVC", "PERM", "AVF", "AVG"], horizontal=True)
            note = st.text_input("備註")
            submitted = st.form_submit_button("新增透析醫囑", type="primary")

        if submitted:
            if not dialysis_days:
                st.warning("請至少選擇一個透析日。")
            else:
                now = _now()
                anticoagulant = f"Loading {anticoagulant_loading.strip()} / Maintain {anticoagulant_maintain.strip()}".strip()
                vascular_access = f"{access_side} {access_type}".strip()
                new = pd.DataFrame([{
                    "chart_no": chart_no,
                    "deid": patient.get("deid", ""),
                    "name": patient.get("name", ""),
                    "effective_date": effective_date.isoformat(),
                    "dialysis_days": ",".join(dialysis_days),
                    "frequency": frequency,
                    "shift": shift,
                    "bed": bed.strip(),
                    "order_month": effective_date.strftime("%Y%m"),
                    "dialyzer": dialyzer.strip(),
                    "dialysate_ca": dialysate_ca.strip(),
                    "dialysate_flow": dialysate_flow.strip(),
                    "blood_flow": blood_flow.strip(),
                    "dry_weight": dry_weight.strip(),
                    "anticoagulant_loading": anticoagulant_loading.strip(),
                    "anticoagulant_maintain": anticoagulant_maintain.strip(),
                    "anticoagulant": anticoagulant,
                    "access_side": access_side,
                    "access_type": access_type,
                    "vascular_access": vascular_access,
                    "updated_by": current_user or "unknown",
                    "updated_at": now,
                    "note": note.strip(),
                    "row_id": f"dialysis_orders-{chart_no}-{now.replace(':', '').replace('-', '')}",
                }])
                saved = pd.concat([orders.fillna(""), new], ignore_index=True)
                db.replace_patient_rows("dialysis_orders", chart_no, saved)
                st.success("已新增透析醫囑")
                st.rerun()
    else:
        st.info("目前角色可查看透析醫囑，沒有編輯權限。")

    if orders.empty:
        st.info("目前沒有透析醫囑紀錄。")
        return

    st.markdown("#### 既有透析醫囑")
    display_columns = [
        "effective_date",
        "frequency",
        "shift",
        "bed",
        "dialyzer",
        "dialysate_ca",
        "dialysate_flow",
        "blood_flow",
        "dry_weight",
        "anticoagulant_loading",
        "anticoagulant_maintain",
        "vascular_access",
        "updated_by",
        "updated_at",
        "note",
    ]
    display = orders.copy()
    for col in display_columns:
        if col not in display.columns:
            display[col] = ""
    display = display[display_columns]
    display.columns = [COLUMN_LABELS.get(col, col) for col in display_columns]
    st.dataframe(display, use_container_width=True, hide_index=True)


def _editable_existing_records(
    table: str,
    chart_no: str,
    df: pd.DataFrame,
    visible_columns: list[str],
    can_edit: bool,
    current_user: str,
    key_suffix: str,
) -> None:
    data = df.copy().fillna("")
    for col in visible_columns:
        if col not in data.columns:
            data[col] = ""

    date_columns = [col for col in ("event_date", "target_date") if col in visible_columns]
    for col in date_columns:
        data[col] = pd.to_datetime(data[col], errors="coerce").dt.date

    column_config = _existing_record_column_config(table, visible_columns)
    disabled_columns = [
        col
        for col in visible_columns
        if col in {"created_by", "created_at", "updated_by", "updated_at"}
    ]

    if not can_edit:
        display = data[visible_columns].copy()
        display.columns = [COLUMN_LABELS.get(col, col) for col in visible_columns]
        st.dataframe(display, use_container_width=True, hide_index=True)
        return

    edited = st.data_editor(
        data[visible_columns],
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        column_config=column_config,
        disabled=disabled_columns,
        key=f"existing-editor-{table}-{chart_no}-{key_suffix}",
    )

    if st.button("儲存紀錄變更", type="primary", key=f"save-existing-{table}-{chart_no}-{key_suffix}"):
        saved = data.copy()
        editable_columns = [col for col in visible_columns if col not in disabled_columns]
        edited_for_save = edited.copy()
        for col in date_columns:
            if col in edited_for_save.columns:
                edited_for_save[col] = edited_for_save[col].map(_format_date_value)
                saved[col] = saved[col].map(_format_date_value)
        if table == "problem_list" and "status" in edited_for_save.columns:
            edited_for_save["status"] = edited_for_save["status"].map(_normalize_problem_status)

        before = saved[editable_columns].fillna("").astype(str) if editable_columns else pd.DataFrame()
        after = edited_for_save[editable_columns].fillna("").astype(str) if editable_columns else pd.DataFrame()
        changed = (before != after).any(axis=1) if editable_columns else pd.Series(False, index=saved.index)

        for col in editable_columns:
            saved[col] = edited_for_save[col]
        if changed.any():
            now = _now()
            if "updated_by" in saved.columns:
                saved.loc[changed, "updated_by"] = current_user or "unknown"
            if "updated_at" in saved.columns:
                saved.loc[changed, "updated_at"] = now

        db.replace_patient_rows(table, chart_no, saved)
        st.success("已儲存紀錄變更")
        st.rerun()


def _existing_record_column_config(table: str, visible_columns: list[str]) -> dict[str, object]:
    column_config = {
        col: st.column_config.TextColumn(COLUMN_LABELS.get(col, col))
        for col in visible_columns
    }
    if table == "problem_list":
        if "problem" in visible_columns:
            column_config["problem"] = st.column_config.TextColumn("主要問題", width="large")
        if "status" in visible_columns:
            column_config["status"] = st.column_config.SelectboxColumn(
                "狀態",
                options=["Active", "Inactive"],
                required=True,
            )
        if "owner_role" in visible_columns:
            column_config["owner_role"] = st.column_config.SelectboxColumn(
                "負責角色",
                options=["醫師", "護理長", "護理師"],
            )
        if "note" in visible_columns:
            column_config["note"] = st.column_config.TextColumn("備註", width="medium")
    if table == "clinical_events":
        if "event_date" in visible_columns:
            column_config["event_date"] = st.column_config.DateColumn("事件日期", format="YYYY-MM-DD")
        if "event_type" in visible_columns:
            column_config["event_type"] = st.column_config.SelectboxColumn(
                "事件類型",
                options=["急診", "住院", "門診"],
            )
        if "title" in visible_columns:
            column_config["title"] = st.column_config.SelectboxColumn(
                "事件標題",
                options=[
                    "血管通路問題",
                    "心臟問題(心肌梗塞、心衰竭)",
                    "感染問題",
                    "周邊血管問題(PAOD)",
                    "呼吸衰竭(插管、BiPAP)",
                    "其他",
                ],
            )
        if "event_content" in visible_columns:
            column_config["event_content"] = st.column_config.TextColumn("事件內容", width="large")
    if table == "handoffs":
        if "target_date" in visible_columns:
            column_config["target_date"] = st.column_config.DateColumn("目標日期", format="YYYY-MM-DD")
        if "handoff_type" in visible_columns:
            column_config["handoff_type"] = st.column_config.SelectboxColumn(
                "交班類型",
                options=["共同交班", "醫師交班", "護理交班"],
            )
        if "priority" in visible_columns:
            column_config["priority"] = st.column_config.SelectboxColumn(
                "優先度",
                options=["一般", "重要", "緊急"],
            )
        if "status" in visible_columns:
            column_config["status"] = st.column_config.SelectboxColumn(
                "狀態",
                options=["未處理", "已知悉", "已處理", "已完成"],
            )
        if "title" in visible_columns:
            column_config["title"] = st.column_config.TextColumn("事件標題", width="medium")
        if "content" in visible_columns:
            column_config["content"] = st.column_config.TextColumn("交班內容", width="large")

    for col in ("created_by", "created_at", "updated_by", "updated_at"):
        if col in visible_columns:
            column_config[col] = st.column_config.TextColumn(COLUMN_LABELS.get(col, col), disabled=True)
    return column_config


def _editable_table(table: str, chart_no: str, df: pd.DataFrame, visible_columns: list[str], new_row: dict[str, str], can_edit: bool) -> None:
    data = df.copy()
    if table == "problem_list" and "status" in data.columns:
        data["status"] = data["status"].map(_normalize_problem_status)
    if table == "clinical_events" and "event_date" in data.columns:
        data["event_date"] = pd.to_datetime(data["event_date"], errors="coerce").dt.date
    if table == "handoffs" and "target_date" in data.columns:
        data["target_date"] = pd.to_datetime(data["target_date"], errors="coerce").dt.date
    if can_edit:
        if st.button("新增一列", key=f"add-{table}-{chart_no}"):
            data = pd.concat([data, pd.DataFrame([new_row])], ignore_index=True)
            if table == "clinical_events" and "event_date" in data.columns:
                data["event_date"] = pd.to_datetime(data["event_date"], errors="coerce").dt.date
            if table == "handoffs" and "target_date" in data.columns:
                data["target_date"] = pd.to_datetime(data["target_date"], errors="coerce").dt.date
    else:
        st.info("目前角色可查看此區，沒有編輯權限。")

    if data.empty:
        data = pd.DataFrame([new_row])

    columns = ["chart_no", "deid", "name", *visible_columns, "row_id"]
    for col in columns:
        if col not in data.columns:
            data[col] = ""
    data = data[columns]
    if table == "clinical_events" and "event_date" in data.columns:
        data["event_date"] = pd.to_datetime(data["event_date"], errors="coerce").dt.date
    if table == "handoffs" and "target_date" in data.columns:
        data["target_date"] = pd.to_datetime(data["target_date"], errors="coerce").dt.date

    column_config = {col: st.column_config.TextColumn(COLUMN_LABELS.get(col, col)) for col in visible_columns}
    if table == "problem_list" and "status" in visible_columns:
        column_config["status"] = st.column_config.SelectboxColumn(
            COLUMN_LABELS.get("status", "status"),
            options=["Active", "Inactive"],
            required=True,
        )
    if table == "problem_list" and "owner_role" in visible_columns:
        column_config["owner_role"] = st.column_config.SelectboxColumn(
            COLUMN_LABELS.get("owner_role", "owner_role"),
            options=["醫師", "護理長", "護理師"],
        )
    if table == "problem_list" and "updated_by" in visible_columns:
        staff = db.active_staff()
        names = staff["name"].dropna().astype(str).tolist() if not staff.empty else []
        column_config["updated_by"] = st.column_config.SelectboxColumn(
            COLUMN_LABELS.get("updated_by", "updated_by"),
            options=["", *names],
        )
    if table == "clinical_events":
        if "event_date" in visible_columns:
            column_config["event_date"] = st.column_config.DateColumn(
                COLUMN_LABELS.get("event_date", "event_date"),
                format="YYYY-MM-DD",
            )
        if "event_type" in visible_columns:
            column_config["event_type"] = st.column_config.SelectboxColumn(
                COLUMN_LABELS.get("event_type", "event_type"),
                options=["", "急診", "住院", "門診"],
            )
        if "title" in visible_columns:
            column_config["title"] = st.column_config.SelectboxColumn(
                COLUMN_LABELS.get("title", "title"),
                options=[
                    "",
                    "血管通路問題",
                    "心臟問題(心肌梗塞、心衰竭)",
                    "感染問題",
                    "周邊血管問題(PAOD)",
                    "呼吸衰竭(插管、BiPAP)",
                    "其他",
                ],
            )
        if "event_content" in visible_columns:
            column_config["event_content"] = st.column_config.TextColumn(
                COLUMN_LABELS.get("event_content", "event_content"),
                width="large",
            )
        if "updated_by" in visible_columns:
            staff = db.active_staff()
            names = staff["name"].dropna().astype(str).tolist() if not staff.empty else []
            column_config["updated_by"] = st.column_config.SelectboxColumn(
                COLUMN_LABELS.get("updated_by", "updated_by"),
                options=["", *names],
            )
    if table == "handoffs":
        if "target_date" in visible_columns:
            column_config["target_date"] = st.column_config.DateColumn(
                COLUMN_LABELS.get("target_date", "target_date"),
                format="YYYY-MM-DD",
                required=True,
            )
        if "handoff_type" in visible_columns:
            column_config["handoff_type"] = st.column_config.SelectboxColumn(
                COLUMN_LABELS.get("handoff_type", "handoff_type"),
                options=["共同交班", "醫師交班", "護理交班"],
                required=True,
            )
        if "priority" in visible_columns:
            column_config["priority"] = st.column_config.SelectboxColumn(
                COLUMN_LABELS.get("priority", "priority"),
                options=["一般", "重要", "緊急"],
                required=True,
            )
        if "status" in visible_columns:
            column_config["status"] = st.column_config.SelectboxColumn(
                COLUMN_LABELS.get("status", "status"),
                options=["未處理", "已知悉", "已完成"],
                required=True,
            )
        if "content" in visible_columns:
            column_config["content"] = st.column_config.TextColumn(
                COLUMN_LABELS.get("content", "content"),
                width="large",
            )
        staff = db.active_staff()
        names = staff["name"].dropna().astype(str).tolist() if not staff.empty else []
        if "created_by" in visible_columns:
            column_config["created_by"] = st.column_config.SelectboxColumn(
                COLUMN_LABELS.get("created_by", "created_by"),
                options=["", *names],
            )
        if "updated_by" in visible_columns:
            column_config["updated_by"] = st.column_config.SelectboxColumn(
                COLUMN_LABELS.get("updated_by", "updated_by"),
                options=["", *names],
            )

    if can_edit:
        edited = st.data_editor(
            data[visible_columns],
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config=column_config,
            key=f"editor-{table}-{chart_no}",
        )
    else:
        display = data[visible_columns].copy()
        display.columns = [COLUMN_LABELS.get(col, col) for col in visible_columns]
        st.dataframe(display, use_container_width=True, hide_index=True)
        edited = data[visible_columns]

    if can_edit and st.button("儲存", type="primary", key=f"save-{table}-{chart_no}"):
        saved = edited.copy()
        if table == "clinical_events" and "event_date" in saved.columns:
            saved["event_date"] = saved["event_date"].map(_format_date_value)
        if table == "handoffs" and "target_date" in saved.columns:
            saved["target_date"] = saved["target_date"].map(_format_date_value)
        if table == "handoffs":
            now = _now()
            if "created_at" in saved.columns:
                saved["created_at"] = saved["created_at"].replace("", now)
            if "created_by" in saved.columns:
                saved["created_by"] = saved["created_by"].replace("", "unknown")
            if "updated_at" in saved.columns:
                saved["updated_at"] = now
        saved.insert(0, "name", data["name"].iloc[0] if "name" in data else "")
        saved.insert(0, "deid", data["deid"].iloc[0] if "deid" in data else "")
        saved.insert(0, "chart_no", chart_no)
        saved["row_id"] = [f"{table}-{chart_no}-{i}" for i in range(len(saved))]
        db.replace_patient_rows(table, chart_no, saved)
        st.success("已儲存")
        st.rerun()


def _render_recommendations(chart_no: str, detail: dict[str, pd.DataFrame]) -> None:
    rules = load_dose_rules()
    labs = detail["lab_results"].copy()
    meds = detail["medications"].copy()
    if labs.empty:
        st.warning("目前沒有抽血資料。下一版會改由 HIS lab API 或正式匯入來源提供。")
        return
    if rules.get("safety", {}).get("show_mock_data_warning", True):
        st.warning("目前抽血與藥物資料來源含 mock，禁止直接臨床使用；請待 HIS/正式匯入資料接上後再用於決策。")

    months = sorted(labs["year_month"].dropna().unique(), reverse=True)
    selected_month = st.selectbox("分析月份", months)
    month_labs = labs[labs["year_month"] == selected_month].copy()
    month_meds = meds[meds["year_month"] == selected_month].copy() if not meds.empty else pd.DataFrame()

    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("#### 本月抽血")
        lab_view = month_labs[["item_key", "value", "unit", "report_date", "source"]].copy()
        lab_view.columns = ["項目", "數值", "單位", "報告日", "來源"]
        st.dataframe(lab_view, use_container_width=True, hide_index=True, height=330)

    with c2:
        st.markdown("#### 本月藥物")
        if month_meds.empty:
            st.info("本月沒有藥物資料。")
        else:
            med_view = month_meds[["drug_class", "drug_name", "dose", "frequency", "source"]].copy()
            med_view.columns = ["類別", "藥名", "劑量", "頻率", "來源"]
            st.dataframe(med_view, use_container_width=True, hide_index=True, height=330)

    lab_entities = _lab_entities(month_labs)
    med_entities = _med_entities(month_meds)
    recs = evaluate_month(
        chart_no=chart_no,
        year_month=selected_month,
        labs=lab_entities,
        medications=med_entities,
        thresholds=Thresholds(),
    )

    st.markdown("#### 規則引擎建議")
    if not recs:
        st.success("目前規則引擎沒有產生需處理建議。")
        return

    rec_rows = []
    for rec in recs:
        rec_rows.append({
            "severity": rec.severity.value,
            "rule_id": rec.rule_id,
            "title": rec.title,
            "evidence": "；".join(rec.evidence),
            "status": rec.status.value,
        })
    st.dataframe(pd.DataFrame(rec_rows), use_container_width=True, hide_index=True)

    st.markdown("#### 劑量調整草稿")
    dose_suggestions = build_dose_adjustments(lab_entities, med_entities, rules)
    if not dose_suggestions:
        st.success("目前沒有產生劑量調整草稿。")
    else:
        dose_rows = []
        for suggestion in dose_suggestions:
            dose_rows.append({
                "類別": suggestion.drug_class,
                "嚴重度": suggestion.severity.value,
                "動作": suggestion.action,
                "目前劑量": suggestion.current_dose,
                "建議劑量": suggestion.suggested_dose,
                "調整幅度": "" if suggestion.change_percent is None else f"{suggestion.change_percent}%",
                "標題": suggestion.title,
                "理由": suggestion.rationale,
                "證據": "；".join(suggestion.evidence),
                "需醫師簽核": "是" if suggestion.requires_physician_approval else "否",
            })
        st.dataframe(pd.DataFrame(dose_rows), use_container_width=True, hide_index=True)

    st.caption("安全設計：這裡的建議由 deterministic rule engine 產生；Claude 後續只負責摘要文字，不直接做臨床判斷。")


def _lab_entities(rows: pd.DataFrame) -> list[LabResult]:
    out: list[LabResult] = []
    for row in rows.to_dict("records"):
        out.append(LabResult(
            chart_no=str(row.get("chart_no", "")),
            year_month=str(row.get("year_month", "")),
            item_key=str(row.get("item_key", "")),
            value=_to_float(row.get("value")),
            unit=str(row.get("unit", "")),
            source=str(row.get("source", "")),
        ))
    return out


def _med_entities(rows: pd.DataFrame) -> list[Medication]:
    out: list[Medication] = []
    if rows.empty:
        return out
    for row in rows.to_dict("records"):
        out.append(Medication(
            chart_no=str(row.get("chart_no", "")),
            year_month=str(row.get("year_month", "")),
            order_code=str(row.get("order_code", "")),
            name=str(row.get("drug_name", "")),
            dose=str(row.get("dose", "")),
            frequency=str(row.get("frequency", "")),
            drug_class=str(row.get("drug_class", "OTHER")),
            source=str(row.get("source", "")),
        ))
    return out


def _to_float(value: object) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except ValueError:
        return None


def _format_date_value(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)[:10]


def _clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _truncate_text(value: object, limit: int) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _sort_by_bed(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty or "bed" not in rows.columns:
        return rows
    sorted_rows = rows.copy()
    sort_keys = sorted_rows["bed"].map(_bed_sort_key)
    sorted_rows["_bed_number"] = sort_keys.map(lambda item: item[0])
    sorted_rows["_bed_suffix"] = sort_keys.map(lambda item: item[1])
    sorted_rows["_bed_text"] = sorted_rows["bed"].astype(str)
    sorted_rows = sorted_rows.sort_values(
        by=["_bed_number", "_bed_suffix", "_bed_text", "name"],
        kind="stable",
    )
    return sorted_rows.drop(columns=["_bed_number", "_bed_suffix", "_bed_text"])


def _bed_sort_key(value: object) -> tuple[int, str]:
    text = _clean_text(value)
    match = re.search(r"\d+", text)
    if not match:
        return 9999, text
    return int(match.group()), text[match.end():].strip()


def _staff_columns() -> list[str]:
    return [
        "staff_id",
        "name",
        "role",
        "active",
        "created_by",
        "created_at",
        "inactive_at",
        "note",
        "username",
        "password_hash",
        "password_set_at",
    ]


def _staff_display_frame(staff: pd.DataFrame) -> pd.DataFrame:
    display_columns = ["staff_id", "name", "role", "username", "active", "created_by", "created_at", "inactive_at", "note"]
    view = staff.copy()
    for col in display_columns:
        if col not in view.columns:
            view[col] = ""
    view = view[display_columns].copy()
    view.columns = ["人員 ID", "姓名", "角色", "帳號", "狀態", "新增者", "新增時間", "停用時間", "備註"]
    return view


def _normalize_problem_status(value: object) -> str:
    text = "" if value is None else str(value).strip().lower()
    if text in {"inactive", "resolved", "archived", "false", "0"}:
        return "Inactive"
    return "Active"


def _normalize_active_label(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return "啟用" if text in {"啟用", "True", "true", "1", "Active", "active"} else "停用"


def _frequency_to_days(value: object) -> list[str]:
    text = "" if value is None else str(value)
    days = [day for day in ["一", "二", "三", "四", "五", "六"] if day in text]
    return days


def _days_to_frequency(days: list[str]) -> str:
    order = ["一", "二", "三", "四", "五", "六"]
    selected = [day for day in order if day in days]
    return "".join(selected)


def _yes_no(value: object) -> str:
    return "是" if bool(value) else "否"


def _can_edit(role: str, area: str) -> bool:
    permissions = {
        "rule_settings": {"醫師"},
        "drug_settings": {"醫師"},
        "staff_settings": {"醫師", "護理長"},
        "patient_settings": {"醫師", "護理長"},
        "dialysis_orders": {"醫師"},
        "problem_list": {"醫師", "護理長", "護理師"},
        "clinical_events": {"醫師", "護理長", "護理師"},
        "handoffs": {"醫師", "護理長", "護理師"},
    }
    return role in permissions.get(area, set())


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


if __name__ == "__main__":
    main()
