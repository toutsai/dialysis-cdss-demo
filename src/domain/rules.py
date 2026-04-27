from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import uuid4

from .entities import LabResult, Medication, Recommendation, Severity


@dataclass(frozen=True)
class Thresholds:
    hb_low: float = 10.0
    hb_high: float = 11.5
    ferritin_low: float = 100
    tsat_low: float = 20
    phosphate_high: float = 5.5
    corrected_calcium_high: float = 10.2
    calcium_phosphate_product_high: float = 55
    ipth_high: float = 600


def _latest_value(labs: Iterable[LabResult], item_key: str) -> float | None:
    values = [lab.value for lab in labs if lab.item_key == item_key and lab.value is not None]
    return values[-1] if values else None


def evaluate_month(
    chart_no: str,
    year_month: str,
    labs: list[LabResult],
    medications: list[Medication],
    thresholds: Thresholds,
) -> list[Recommendation]:
    """Small first-pass rule engine.

    SAFETY: Claude should summarize these outputs, not replace this logic.
    """
    del medications  # Reserved for dose-aware rules in the next milestone.
    recs: list[Recommendation] = []
    hb = _latest_value(labs, "Hb")
    ferritin = _latest_value(labs, "Ferritin")
    tsat = _latest_value(labs, "TSAT")
    phosphate = _latest_value(labs, "P")
    cca = _latest_value(labs, "cCa")
    caxp = _latest_value(labs, "CaXP")
    ipth = _latest_value(labs, "iPTH")

    if hb is not None and hb > thresholds.hb_high:
        recs.append(_rec(chart_no, year_month, Severity.WARNING, "esa.hb_high", "Hb 偏高，請檢視 ESA 是否需減量或暫停", [f"Hb={hb}"]))
    if hb is not None and hb < thresholds.hb_low:
        recs.append(_rec(chart_no, year_month, Severity.WARNING, "esa.hb_low", "Hb 偏低，請檢視 ESA 劑量與缺鐵/發炎因素", [f"Hb={hb}"]))
    if (ferritin is not None and ferritin < thresholds.ferritin_low) or (tsat is not None and tsat < thresholds.tsat_low):
        recs.append(_rec(chart_no, year_month, Severity.INFO, "iron.possible_deficiency", "鐵狀態偏低，請評估是否需補鐵", [f"Ferritin={ferritin}", f"TSAT={tsat}"]))
    if phosphate is not None and phosphate > thresholds.phosphate_high:
        recs.append(_rec(chart_no, year_month, Severity.WARNING, "mbd.phosphate_high", "血磷偏高，請檢視飲食、透析充分性與降磷藥", [f"P={phosphate}"]))
    if cca is not None and cca > thresholds.corrected_calcium_high:
        recs.append(_rec(chart_no, year_month, Severity.WARNING, "mbd.cca_high", "校正鈣偏高，請檢視含鈣降磷藥與活性維生素 D", [f"cCa={cca}"]))
    if caxp is not None and caxp > thresholds.calcium_phosphate_product_high:
        recs.append(_rec(chart_no, year_month, Severity.WARNING, "mbd.caxp_high", "鈣磷乘積偏高，請優先處理 CKD-MBD 風險", [f"CaXP={caxp}"]))
    if ipth is not None and ipth > thresholds.ipth_high:
        recs.append(_rec(chart_no, year_month, Severity.INFO, "mbd.ipth_high", "iPTH 偏高，請整體評估 CKD-MBD 治療策略", [f"iPTH={ipth}"]))
    return recs


def _rec(chart_no: str, ym: str, severity: Severity, rule_id: str, title: str, evidence: list[str]) -> Recommendation:
    return Recommendation(
        recommendation_id=str(uuid4()),
        chart_no=chart_no,
        year_month=ym,
        severity=severity,
        rule_id=rule_id,
        title=title,
        detail=title,
        evidence=evidence,
    )
