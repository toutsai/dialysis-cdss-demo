from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .entities import LabResult, Severity


@dataclass(frozen=True)
class MedicationTrendRecord:
    chart_no: str
    year_month: str
    drug_class: str
    drug_name: str
    dose: str = ""
    unit: str = ""
    frequency: str = ""
    start_date: str = ""
    status: str = ""


@dataclass(frozen=True)
class DialysisOrderTrendRecord:
    chart_no: str
    order_month: str
    dialyzer: str = ""
    blood_flow: str = ""
    dialysate_flow: str = ""
    dry_weight: str = ""
    dialysate_ca: str = ""
    frequency: str = ""
    shift: str = ""
    bed: str = ""
    effective_date: str = ""


@dataclass(frozen=True)
class TrendPoint:
    month: str
    value: float | None
    text: str


@dataclass(frozen=True)
class ExposurePoint:
    month: str
    value: float | None
    text: str


@dataclass(frozen=True)
class TreatmentTrendSuggestion:
    group: str
    severity: Severity
    action: str
    title: str
    rationale: str
    lab_trends: list[str]
    treatment_trends: list[str]
    target_tab: str
    target_kind: str
    draft: dict[str, str] = field(default_factory=dict)
    actionable: bool = True


DEFAULT_TREND_RULES: dict[str, Any] = {
    "window_months": 3,
    "lab_delta_thresholds": {
        "Hb": 0.3,
        "Ferritin": 30,
        "TSAT": 2,
        "P": 0.3,
        "cCa": 0.2,
        "CaXP": 3,
        "iPTH": 50,
        "K": 0.3,
        "Kt/V": 0.05,
        "URR": 2,
    },
    "frequency_per_month": {
        "QW": 4,
        "Q1W": 4,
        "Q2W": 2,
        "BIW": 8,
        "TIW": 12,
        "QOD": 15,
        "QD": 30,
        "BID": 60,
        "TID": 90,
        "TIDCC": 90,
        "TID WITH MEALS": 90,
        "QHS": 30,
    },
    "drug_factors": {
        "Darbepoetin alfa": 1,
        "Epoetin alfa": 1,
        "Calcium carbonate": 1,
        "Sevelamer": 1,
        "Lanthanum carbonate": 1,
        "Cinacalcet": 1,
        "Sodium zirconium cyclosilicate": 1,
    },
    "response": {
        "meaningful_exposure_increase_ratio": 1.2,
        "large_exposure_increase_ratio": 1.5,
        "minimal_lab_response_ratio": 1.03,
        "suggested_increase_percent": 25,
        "suggested_small_increase_percent": 15,
        "suggested_decrease_percent": 25,
    },
}


def build_trend_recommendations(
    *,
    selected_month: str,
    labs: list[LabResult],
    medications: list[MedicationTrendRecord],
    dialysis_orders: list[DialysisOrderTrendRecord],
    dose_rules: dict[str, Any],
    trend_rules: dict[str, Any] | None = None,
) -> list[TreatmentTrendSuggestion]:
    rules = _merge_rules(DEFAULT_TREND_RULES, trend_rules or {})
    window_months = int(rules.get("window_months", 3))
    months = _analysis_months(selected_month, labs, medications, dialysis_orders, window_months)
    suggestions: list[TreatmentTrendSuggestion] = []
    suggestions.extend(_anemia_suggestions(months, labs, medications, dose_rules, rules, selected_month))
    suggestions.extend(_mbd_suggestions(months, labs, medications, dose_rules, rules, selected_month))
    suggestions.extend(_adequacy_suggestions(months, labs, medications, dialysis_orders, dose_rules, rules, selected_month))
    return suggestions


def medication_exposure_points(
    medications: list[MedicationTrendRecord],
    months: list[str],
    classes: set[str],
    rules: dict[str, Any] | None = None,
) -> list[ExposurePoint]:
    cfg = _merge_rules(DEFAULT_TREND_RULES, rules or {})
    points: list[ExposurePoint] = []
    for month in months:
        row = _latest_medication_for_month(medications, month, classes)
        if row is None:
            points.append(ExposurePoint(month, None, "未見用藥"))
            continue
        exposure = _monthly_exposure(row, cfg)
        points.append(ExposurePoint(month, exposure, _medication_text(row)))
    return points


def lab_trend_points(labs: list[LabResult], months: list[str], item_key: str) -> list[TrendPoint]:
    points: list[TrendPoint] = []
    for month in months:
        value = _latest_lab_value(labs, month, item_key)
        points.append(TrendPoint(month, value, _format_value(value)))
    return points


def _anemia_suggestions(
    months: list[str],
    labs: list[LabResult],
    meds: list[MedicationTrendRecord],
    dose_rules: dict[str, Any],
    trend_rules: dict[str, Any],
    selected_month: str,
) -> list[TreatmentTrendSuggestion]:
    cfg = dose_rules.get("esa", {})
    hb_low = float(cfg.get("hb_low", 10.0))
    hb_high = float(cfg.get("hb_high", 11.5))
    hold_hb = float(cfg.get("hold_if_hb_above", 12.5))
    hb = lab_trend_points(labs, months, "Hb")
    ferritin = lab_trend_points(labs, months, "Ferritin")
    tsat = lab_trend_points(labs, months, "TSAT")
    esa = medication_exposure_points(meds, months, {"ESA", "HIF_PHI"}, trend_rules)
    latest_hb = _latest_value(hb)
    if latest_hb is None:
        return []

    hb_direction = _direction(hb, "Hb", trend_rules)
    exposure_direction = _exposure_direction(esa)
    exposure_ratio = _value_ratio(_first_value(esa), _latest_value(esa))
    hb_ratio = _value_ratio(_first_value(hb), latest_hb)
    current_esa = _latest_medication_for_month(meds, selected_month, {"ESA", "HIF_PHI"})
    iron_replete = _latest_value(ferritin) is not None and _latest_value(tsat) is not None and (
        _latest_value(ferritin) >= float(cfg.get("ferritin_replete_min", 100))
        and _latest_value(tsat) >= float(cfg.get("tsat_replete_min", 20))
    )
    treatment_lines = [_trend_line("ESA", esa)]
    lab_lines = [_trend_line("Hb", hb), _trend_line("Ferritin", ferritin), _trend_line("TSAT", tsat)]

    if latest_hb >= hold_hb:
        return [_suggestion(
            group="anemia",
            severity=Severity.WARNING,
            action="hold_or_decrease",
            title="Hb 明顯偏高，建議暫停或減少 ESA",
            rationale="Hb 高於暫停門檻；請搭配最近 ESA 暴露量變化，避免 Hb 過高或上升過快。",
            lab_trends=lab_lines,
            treatment_trends=treatment_lines,
            draft=_medication_draft(current_esa, selected_month, "暫停或至少減量", "Hb 明顯偏高，趨勢建議暫停或減少 ESA"),
        )]
    if latest_hb > hb_high:
        pct = int(_response_cfg(trend_rules).get("suggested_decrease_percent", 25))
        return [_suggestion(
            group="anemia",
            severity=Severity.WARNING,
            action="decrease",
            title=f"Hb 偏高，建議 ESA 減量 {pct}%",
            rationale=f"Hb 目前高於目標上限，趨勢為{_direction_label(hb_direction)}；建議降低 ESA 暴露量。",
            lab_trends=lab_lines,
            treatment_trends=treatment_lines,
            draft=_changed_medication_draft(current_esa, selected_month, -pct, "Hb 偏高，趨勢建議 ESA 減量"),
        )]
    if latest_hb < hb_low:
        if cfg.get("require_iron_replete_before_increase", True) and not iron_replete:
            return [_suggestion(
                group="anemia",
                severity=Severity.INFO,
                action="defer_increase_check_iron",
                title="Hb 偏低，且鐵狀態未達 ESA 增量條件",
                rationale="Ferritin 或 TSAT 仍偏低；直接增加 ESA 的反應可能有限，建議先處理鐵狀態或評估發炎/失血。",
                lab_trends=lab_lines,
                treatment_trends=treatment_lines,
                draft=_medication_draft(current_esa, selected_month, "", "Hb 偏低但鐵狀態未達條件，請先評估鐵劑或發炎/失血因素"),
            )]
        large_increase = exposure_ratio is not None and exposure_ratio >= float(_response_cfg(trend_rules).get("large_exposure_increase_ratio", 1.5))
        meaningful_increase = exposure_ratio is not None and exposure_ratio >= float(_response_cfg(trend_rules).get("meaningful_exposure_increase_ratio", 1.2))
        minimal_response = hb_ratio is not None and hb_ratio >= float(_response_cfg(trend_rules).get("minimal_lab_response_ratio", 1.03))
        if large_increase and not minimal_response:
            pct = int(_response_cfg(trend_rules).get("suggested_small_increase_percent", 15))
            return [_suggestion(
                group="anemia",
                severity=Severity.WARNING,
                action="increase_after_insufficient_response",
                title=f"ESA 已明顯增加但 Hb 反應不足，建議再小幅上調 {pct}% 或評估原因",
                rationale=f"ESA 暴露量約為起始的 {_format_ratio(exposure_ratio)}，但 Hb 反應未達 {_response_cfg(trend_rules).get('minimal_lab_response_ratio', 1.03)} 倍，需評估發炎、失血、營養與透析相關因素。",
                lab_trends=lab_lines,
                treatment_trends=treatment_lines,
                draft=_changed_medication_draft(current_esa, selected_month, pct, "ESA 已增加但 Hb 反應不足，趨勢建議小幅上調或評估原因"),
            )]
        if meaningful_increase and (minimal_response or hb_direction == "rising"):
            return [_suggestion(
                group="anemia",
                severity=Severity.INFO,
                action="observe_after_response",
                title="ESA 已調整且 Hb 有回升，建議先觀察追蹤",
                rationale="Hb 仍低於目標，但最近趨勢已有反應；可先追蹤下次月抽血，避免過度加量。",
                lab_trends=lab_lines,
                treatment_trends=treatment_lines,
                actionable=False,
                draft={},
            )]
        pct = int(_response_cfg(trend_rules).get("suggested_increase_percent", 25))
        return [_suggestion(
            group="anemia",
            severity=Severity.WARNING,
            action="increase",
            title=f"Hb 偏低且趨勢未改善，建議 ESA 上調 {pct}%",
            rationale=f"Hb 低於目標且趨勢為{_direction_label(hb_direction)}；ESA 暴露量趨勢為{_direction_label(exposure_direction)}，建議調整後追蹤。",
            lab_trends=lab_lines,
            treatment_trends=treatment_lines,
            draft=_changed_medication_draft(current_esa, selected_month, pct, "Hb 偏低且趨勢未改善，趨勢建議 ESA 上調"),
        )]
    return [_suggestion(
        group="anemia",
        severity=Severity.OK,
        action="stable",
        title="貧血指標目前穩定，暫無明顯 ESA 調整建議",
        rationale="Hb 目前位於目標區間，請持續追蹤 Hb、Ferritin 與 TSAT 趨勢。",
        lab_trends=lab_lines,
        treatment_trends=treatment_lines,
        actionable=False,
        draft={},
    )]


def _mbd_suggestions(
    months: list[str],
    labs: list[LabResult],
    meds: list[MedicationTrendRecord],
    dose_rules: dict[str, Any],
    trend_rules: dict[str, Any],
    selected_month: str,
) -> list[TreatmentTrendSuggestion]:
    cfg = dose_rules.get("mbd", {})
    p_high_threshold = float(cfg.get("phosphate_high", 5.5))
    ipth_high_threshold = float(cfg.get("ipth_high", 600))
    p = lab_trend_points(labs, months, "P")
    cca = lab_trend_points(labs, months, "cCa")
    caxp = lab_trend_points(labs, months, "CaXP")
    ipth = lab_trend_points(labs, months, "iPTH")
    binder = medication_exposure_points(meds, months, {"Phosphate binder", "CALCIUM_BINDER", "NON_CALCIUM_BINDER", "NON_CA_BINDER", "AL_BINDER"}, trend_rules)
    pth_meds = medication_exposure_points(meds, months, {"PTH", "ACTIVE_VITD", "CALCIMIMETIC"}, trend_rules)
    latest_p = _latest_value(p)
    latest_ipth = _latest_value(ipth)
    lab_lines = [_trend_line("P", p), _trend_line("cCa", cca), _trend_line("CaXP", caxp), _trend_line("iPTH", ipth)]
    treatment_lines = [_trend_line("降磷藥", binder), _trend_line("PTH 藥物", pth_meds)]
    suggestions: list[TreatmentTrendSuggestion] = []
    p_direction = _direction(p, "P", trend_rules)
    binder_ratio = _value_ratio(_first_value(binder), _latest_value(binder))
    current_binder = _latest_medication_for_month(meds, selected_month, {"Phosphate binder", "CALCIUM_BINDER", "NON_CALCIUM_BINDER", "NON_CA_BINDER", "AL_BINDER"})
    if latest_p is not None and (latest_p > p_high_threshold or p_direction == "rising"):
        large_binder_increase = binder_ratio is not None and binder_ratio >= float(_response_cfg(trend_rules).get("large_exposure_increase_ratio", 1.5))
        if large_binder_increase and p_direction in {"rising", "stable"} and latest_p > p_high_threshold:
            suggestions.append(_suggestion(
                group="mbd",
                severity=Severity.WARNING,
                action="binder_insufficient_response",
                title="降磷藥已增加但 P 反應不足，建議檢視飲食、服藥方式或換藥策略",
                rationale=f"降磷藥暴露量約為起始的 {_format_ratio(binder_ratio)}，但 P 仍偏高或未下降；請評估順從性、含鈣負荷與非鈣型降磷藥策略。",
                lab_trends=lab_lines,
                treatment_trends=treatment_lines,
                draft=_changed_medication_draft(current_binder, selected_month, int(_response_cfg(trend_rules).get("suggested_small_increase_percent", 15)), "P 偏高且反應不足，趨勢建議檢視控磷策略"),
            ))
        elif _latest_value(binder) is None:
            suggestions.append(_suggestion(
                group="mbd",
                severity=Severity.WARNING,
                action="start_phosphate_binder",
                title="P 偏高且未見降磷藥紀錄，建議建立控磷策略",
                rationale="血磷偏高或上升，但目前未見可解析降磷藥紀錄；請評估飲食、透析充分性與降磷藥。",
                lab_trends=lab_lines,
                treatment_trends=treatment_lines,
                draft=_medication_draft(current_binder, selected_month, "", "P 偏高，趨勢建議建立或調整控磷策略"),
            ))
        else:
            suggestions.append(_suggestion(
                group="mbd",
                severity=Severity.WARNING,
                action="intensify_phosphate_control",
                title="P 偏高或上升，建議調整降磷策略",
                rationale=f"P 趨勢為{_direction_label(p_direction)}，降磷藥暴露量未見足夠改善；請評估加強控磷或調整藥物。",
                lab_trends=lab_lines,
                treatment_trends=treatment_lines,
                draft=_changed_medication_draft(current_binder, selected_month, int(_response_cfg(trend_rules).get("suggested_increase_percent", 25)), "P 偏高或上升，趨勢建議調整降磷策略"),
            ))

    ipth_direction = _direction(ipth, "iPTH", trend_rules)
    current_pth = _latest_medication_for_month(meds, selected_month, {"PTH", "ACTIVE_VITD", "CALCIMIMETIC"})
    pth_ratio = _value_ratio(_first_value(pth_meds), _latest_value(pth_meds))
    if latest_ipth is not None and (latest_ipth > ipth_high_threshold or ipth_direction == "rising"):
        if pth_ratio is not None and pth_ratio >= float(_response_cfg(trend_rules).get("large_exposure_increase_ratio", 1.5)) and ipth_direction == "rising":
            title = "PTH 藥物已增加但 iPTH 持續上升，建議重新評估 SHPT 策略"
            rationale = "iPTH 仍上升且治療反應不足；請同步評估鈣磷控制、服藥順從性與後續 CKD-MBD 治療選項。"
        else:
            title = "iPTH 偏高或上升，建議評估副甲狀腺亢進治療"
            rationale = "iPTH 高於設定門檻或呈上升趨勢；請搭配 P、cCa、CaXP 決定是否調整 PTH 相關藥物。"
        suggestions.append(_suggestion(
            group="mbd",
            severity=Severity.INFO,
            action="evaluate_ipth_therapy",
            title=title,
            rationale=rationale,
            lab_trends=lab_lines,
            treatment_trends=treatment_lines,
            draft=_changed_medication_draft(current_pth, selected_month, int(_response_cfg(trend_rules).get("suggested_small_increase_percent", 15)), "iPTH 偏高或上升，趨勢建議評估 PTH 相關治療"),
        ))

    if suggestions:
        return suggestions
    return [_suggestion(
        group="mbd",
        severity=Severity.OK,
        action="stable",
        title="CKD-MBD 指標目前沒有明顯需調整建議",
        rationale="P、cCa、CaXP 與 iPTH 未達趨勢調整條件，請持續追蹤。",
        lab_trends=lab_lines,
        treatment_trends=treatment_lines,
        actionable=False,
        draft={},
    )]


def _adequacy_suggestions(
    months: list[str],
    labs: list[LabResult],
    meds: list[MedicationTrendRecord],
    orders: list[DialysisOrderTrendRecord],
    dose_rules: dict[str, Any],
    trend_rules: dict[str, Any],
    selected_month: str,
) -> list[TreatmentTrendSuggestion]:
    del dose_rules
    ktv = lab_trend_points(labs, months, "Kt/V")
    urr = lab_trend_points(labs, months, "URR")
    potassium = lab_trend_points(labs, months, "K")
    k_binder = medication_exposure_points(meds, months, {"K_BINDER"}, trend_rules)
    latest_ktv = _latest_value(ktv)
    latest_urr = _latest_value(urr)
    latest_k = _latest_value(potassium)
    ktv_direction = _direction(ktv, "Kt/V", trend_rules)
    urr_direction = _direction(urr, "URR", trend_rules)
    k_direction = _direction(potassium, "K", trend_rules)
    order_trend = _dialysis_order_trend(orders, selected_month, months)
    lab_lines = [_trend_line("Kt/V", ktv), _trend_line("URR", urr), _trend_line("K", potassium)]
    treatment_lines = [order_trend, _trend_line("降鉀藥", k_binder)]
    current_order = _latest_order_for_month(orders, selected_month)
    needs_adequacy = (
        (latest_ktv is not None and latest_ktv < 1.2)
        or (latest_urr is not None and latest_urr < 65)
        or ktv_direction == "falling"
        or urr_direction == "falling"
    )
    if needs_adequacy:
        has_recent_intervention = _order_changed_in_window(orders, months)
        if has_recent_intervention and (ktv_direction == "rising" or urr_direction == "rising"):
            return [_suggestion(
                group="adequacy",
                severity=Severity.INFO,
                action="observe_after_order_change",
                title="透析條件近期已調整且充分性有改善，建議先追蹤",
                rationale="Kt/V 或 URR 仍需追蹤，但近期醫囑介入後已呈改善方向。",
                lab_trends=lab_lines,
                treatment_trends=treatment_lines,
                target_kind="dialysis_order",
                target_tab="透析醫囑",
                actionable=False,
                draft={},
            )]
        return [_suggestion(
            group="adequacy",
            severity=Severity.WARNING,
            action="adjust_dialysis_order",
            title="透析充分性偏低或下降，建議評估 AK、BF、DF、時間與 access",
            rationale="Kt/V 或 URR 未達目標或呈下降趨勢；若近期已調整仍未改善，需同步評估血管通路與透析條件。",
            lab_trends=lab_lines,
            treatment_trends=treatment_lines,
            target_kind="dialysis_order",
            target_tab="透析醫囑",
            draft=_dialysis_order_draft(current_order, "透析充分性偏低或下降，趨勢建議檢視 AK / BF / DF / 時間 / access"),
        )]
    if latest_k is not None and (latest_k >= 5.5 or k_direction == "rising"):
        return [_suggestion(
            group="adequacy",
            severity=Severity.WARNING,
            action="evaluate_hyperkalemia",
            title="K 偏高或上升，建議評估飲食、降鉀藥與透析條件",
            rationale="鉀離子偏高或呈上升趨勢；請搭配降鉀藥與透析充分性判斷是否需調整。",
            lab_trends=lab_lines,
            treatment_trends=treatment_lines,
            target_kind="dialysis_order",
            target_tab="透析醫囑",
            draft=_dialysis_order_draft(current_order, "K 偏高或上升，趨勢建議評估透析條件與降鉀策略"),
        )]
    return [_suggestion(
        group="adequacy",
        severity=Severity.OK,
        action="stable",
        title="透析充分性與電解質目前沒有明顯需調整建議",
        rationale="Kt/V、URR 與 K 未達趨勢調整條件，請持續追蹤。",
        lab_trends=lab_lines,
        treatment_trends=treatment_lines,
        target_kind="dialysis_order",
        target_tab="透析醫囑",
        actionable=False,
        draft={},
    )]


def _suggestion(
    *,
    group: str,
    severity: Severity,
    action: str,
    title: str,
    rationale: str,
    lab_trends: list[str],
    treatment_trends: list[str],
    target_tab: str = "洗腎藥物",
    target_kind: str = "medication",
    draft: dict[str, str] | None = None,
    actionable: bool = True,
) -> TreatmentTrendSuggestion:
    return TreatmentTrendSuggestion(
        group=group,
        severity=severity,
        action=action,
        title=title,
        rationale=rationale,
        lab_trends=[line for line in lab_trends if line],
        treatment_trends=[line for line in treatment_trends if line],
        target_tab=target_tab,
        target_kind=target_kind,
        draft=draft or {},
        actionable=actionable,
    )


def _analysis_months(
    selected_month: str,
    labs: list[LabResult],
    medications: list[MedicationTrendRecord],
    orders: list[DialysisOrderTrendRecord],
    limit: int,
) -> list[str]:
    months = {
        lab.year_month for lab in labs if lab.year_month and lab.year_month <= selected_month
    }
    months.update(record.year_month for record in medications if record.year_month and record.year_month <= selected_month)
    months.update(record.order_month for record in orders if record.order_month and record.order_month <= selected_month)
    out = sorted(months)
    return out[-limit:] if out else [selected_month]


def _latest_lab_value(labs: Iterable[LabResult], month: str, item_key: str) -> float | None:
    values = [lab.value for lab in labs if lab.year_month == month and lab.item_key == item_key and lab.value is not None]
    return values[-1] if values else None


def _latest_medication_for_month(
    medications: list[MedicationTrendRecord],
    month: str,
    classes: set[str],
) -> MedicationTrendRecord | None:
    rows = [
        med for med in medications
        if med.year_month <= month and med.drug_class in classes and _active_medication(med)
    ]
    if not rows:
        return None
    return sorted(rows, key=lambda row: (row.year_month, row.start_date, row.drug_name))[-1]


def _latest_order_for_month(
    orders: list[DialysisOrderTrendRecord],
    month: str,
) -> DialysisOrderTrendRecord | None:
    rows = [order for order in orders if order.order_month <= month]
    if not rows:
        return None
    return sorted(rows, key=lambda row: (row.order_month, row.effective_date))[-1]


def _active_medication(med: MedicationTrendRecord) -> bool:
    status = med.status.strip().lower()
    return status not in {"inactive", "停用", "hold", "paused"}


def _monthly_exposure(med: MedicationTrendRecord, rules: dict[str, Any]) -> float | None:
    dose = _dose_number(med.dose)
    freq = _frequency_multiplier(med.frequency, rules)
    factor = _drug_factor(med.drug_name, rules)
    if dose is None or freq is None:
        return None
    return dose * freq * factor


def _dose_number(raw: str) -> float | None:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(raw))
    return float(match.group(1)) if match else None


def _frequency_multiplier(raw: str, rules: dict[str, Any]) -> float | None:
    text = str(raw or "").strip().upper()
    if not text:
        return 1.0
    text = text.replace(" ", " ")
    direct = rules.get("frequency_per_month", {}).get(text)
    if direct is not None:
        return float(direct)
    if "TID" in text:
        return 90.0
    if "BID" in text:
        return 60.0
    if text in {"QD", "DAILY", "QDAY"}:
        return 30.0
    match = re.search(r"Q([0-9]+)W", text)
    if match:
        weeks = float(match.group(1))
        return 4.0 / weeks if weeks else None
    return None


def _drug_factor(drug_name: str, rules: dict[str, Any]) -> float:
    factors = rules.get("drug_factors", {})
    if drug_name in factors:
        return float(factors[drug_name])
    lowered = str(drug_name).strip().lower()
    for name, factor in factors.items():
        if str(name).strip().lower() == lowered:
            return float(factor)
    return 1.0


def _direction(points: list[TrendPoint], item_key: str, rules: dict[str, Any]) -> str:
    values = [point.value for point in points if point.value is not None]
    if len(values) < 2:
        return "insufficient"
    delta = values[-1] - values[0]
    threshold = float(rules.get("lab_delta_thresholds", {}).get(item_key, 0))
    if abs(delta) < threshold:
        return "stable"
    return "rising" if delta > 0 else "falling"


def _exposure_direction(points: list[ExposurePoint]) -> str:
    values = [point.value for point in points if point.value is not None]
    if len(values) < 2:
        return "insufficient"
    first = values[0]
    latest = values[-1]
    if first == 0:
        return "rising" if latest > 0 else "stable"
    ratio = latest / first
    if ratio >= 1.1:
        return "rising"
    if ratio <= 0.9:
        return "falling"
    return "stable"


def _direction_label(direction: str) -> str:
    return {
        "rising": "上升",
        "falling": "下降",
        "stable": "穩定",
        "insufficient": "資料不足",
    }.get(direction, direction)


def _first_value(points: list[TrendPoint] | list[ExposurePoint]) -> float | None:
    for point in points:
        if point.value is not None:
            return point.value
    return None


def _latest_value(points: list[TrendPoint] | list[ExposurePoint]) -> float | None:
    for point in reversed(points):
        if point.value is not None:
            return point.value
    return None


def _value_ratio(first: float | None, latest: float | None) -> float | None:
    if first is None or latest is None or first == 0:
        return None
    return latest / first


def _response_cfg(rules: dict[str, Any]) -> dict[str, Any]:
    return rules.get("response", {})


def _format_ratio(value: float | None) -> str:
    if value is None:
        return "無法換算"
    return f"{value:.1f} 倍"


def _format_value(value: float | None) -> str:
    if value is None:
        return "-"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


def _trend_line(label: str, points: list[TrendPoint] | list[ExposurePoint]) -> str:
    values = " → ".join(point.text for point in points)
    return f"{label} {values}".strip()


def _medication_text(med: MedicationTrendRecord) -> str:
    dose_unit = " ".join(part for part in [med.dose.strip(), med.unit.strip()] if part)
    return " / ".join(part for part in [dose_unit, med.frequency.strip()] if part) or "已開立"


def _medication_draft(med: MedicationTrendRecord | None, selected_month: str, dose: str, note: str) -> dict[str, str]:
    if med is None:
        return {
            "year_month": selected_month,
            "drug_class": "",
            "drug_name": "",
            "dose": dose,
            "unit": "",
            "frequency": "",
            "note": note,
        }
    return {
        "year_month": selected_month,
        "drug_class": med.drug_class,
        "drug_name": med.drug_name,
        "dose": dose or med.dose,
        "unit": med.unit,
        "frequency": med.frequency,
        "note": note,
    }


def _changed_medication_draft(med: MedicationTrendRecord | None, selected_month: str, pct: int, note: str) -> dict[str, str]:
    if med is None:
        return _medication_draft(None, selected_month, "", note)
    dose = _dose_number(med.dose)
    if dose is None:
        return _medication_draft(med, selected_month, f"{'增加' if pct > 0 else '減少'} {abs(pct)}%", note)
    new_dose = round(dose * (1 + pct / 100), 1)
    if new_dose.is_integer():
        dose_text = str(int(new_dose))
    else:
        dose_text = str(new_dose)
    return _medication_draft(med, selected_month, dose_text, note)


def _dialysis_order_draft(order: DialysisOrderTrendRecord | None, note: str) -> dict[str, str]:
    if order is None:
        return {"note": note}
    return {
        "frequency": order.frequency,
        "shift": order.shift,
        "bed": order.bed,
        "dialyzer": order.dialyzer,
        "dialysate_ca": order.dialysate_ca,
        "dialysate_flow": order.dialysate_flow,
        "blood_flow": order.blood_flow,
        "dry_weight": order.dry_weight,
        "note": note,
    }


def _dialysis_order_trend(orders: list[DialysisOrderTrendRecord], selected_month: str, months: list[str]) -> str:
    first = _latest_order_for_month(orders, months[0]) if months else None
    latest = _latest_order_for_month(orders, selected_month)
    if latest is None:
        return "透析醫囑 未填"
    latest_text = _order_text(latest)
    if first is None or first == latest:
        return f"透析醫囑 {latest_text}"
    return f"透析醫囑 {_order_text(first)} → {latest_text}"


def _order_text(order: DialysisOrderTrendRecord) -> str:
    return " / ".join(part for part in [
        f"AK {order.dialyzer}".strip() if order.dialyzer else "",
        f"BF {order.blood_flow}".strip() if order.blood_flow else "",
        f"DF {order.dialysate_flow}".strip() if order.dialysate_flow else "",
        f"DW {order.dry_weight}".strip() if order.dry_weight else "",
        f"Ca {order.dialysate_ca}".strip() if order.dialysate_ca else "",
    ] if part) or "未填"


def _order_changed_in_window(orders: list[DialysisOrderTrendRecord], months: list[str]) -> bool:
    if len(months) < 2:
        return False
    states = [_order_text(_latest_order_for_month(orders, month)) for month in months if _latest_order_for_month(orders, month) is not None]
    return len(set(states)) > 1


def _merge_rules(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_rules(merged[key], value)
        else:
            merged[key] = value
    return merged
