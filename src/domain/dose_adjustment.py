from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .entities import LabResult, Medication, Severity


@dataclass(frozen=True)
class DoseAdjustmentSuggestion:
    drug_class: str
    severity: Severity
    action: str
    current_dose: str
    suggested_dose: str
    change_percent: int | None
    title: str
    rationale: str
    evidence: list[str] = field(default_factory=list)
    requires_physician_approval: bool = True


def build_dose_adjustments(
    labs: list[LabResult],
    medications: list[Medication],
    rules: dict[str, Any],
) -> list[DoseAdjustmentSuggestion]:
    """Build dose adjustment drafts for ESA, iron, and CKD-MBD.

    SAFETY: These suggestions are drafts for physician review. They should not
    automatically change medication orders.
    """
    suggestions: list[DoseAdjustmentSuggestion] = []
    if rules.get("esa", {}).get("enabled", True):
        suggestions.extend(_esa_adjustments(labs, medications, rules))
    if rules.get("iron", {}).get("enabled", True):
        suggestions.extend(_iron_adjustments(labs, medications, rules))
    if rules.get("mbd", {}).get("enabled", True):
        suggestions.extend(_mbd_adjustments(labs, medications, rules))
    return suggestions


def _esa_adjustments(labs: list[LabResult], meds: list[Medication], rules: dict[str, Any]) -> list[DoseAdjustmentSuggestion]:
    cfg = rules.get("esa", {})
    safety = rules.get("safety", {})
    hb = _lab(labs, "Hb")
    ferritin = _lab(labs, "Ferritin")
    tsat = _lab(labs, "TSAT")
    esa = _first_med(meds, {"ESA", "HIF_PHI"})
    if hb is None or esa is None:
        return []

    current = _dose_number(esa.dose)
    current_text = _dose_text(esa)
    require_approval = bool(safety.get("require_physician_approval", True))
    out: list[DoseAdjustmentSuggestion] = []

    if hb >= float(cfg.get("hold_if_hb_above", 12.5)):
        out.append(DoseAdjustmentSuggestion(
            drug_class="ESA",
            severity=Severity.WARNING,
            action="hold_or_decrease",
            current_dose=current_text,
            suggested_dose="暫停或至少減量，需醫師確認",
            change_percent=None,
            title="Hb 明顯偏高，建議暫停或減少 ESA",
            rationale="Hb 高於暫停門檻，避免 Hb 過高或上升過快。",
            evidence=[f"Hb={hb}", f"目前 {current_text}"],
            requires_physician_approval=require_approval,
        ))
    elif hb > float(cfg.get("hb_high", 11.5)):
        pct = int(cfg.get("decrease_percent", 25))
        out.append(DoseAdjustmentSuggestion(
            drug_class="ESA",
            severity=Severity.WARNING,
            action="decrease",
            current_dose=current_text,
            suggested_dose=_changed_dose_text(current, esa, -pct),
            change_percent=-pct,
            title=f"Hb 偏高，建議 ESA 減量 {pct}%",
            rationale="Hb 高於目標上限，建議降低 ESA 暴露量。",
            evidence=[f"Hb={hb}", f"目前 {current_text}"],
            requires_physician_approval=require_approval,
        ))
    elif hb < float(cfg.get("hb_low", 10.0)):
        iron_replete = (
            ferritin is not None and ferritin >= float(cfg.get("ferritin_replete_min", 100))
            and tsat is not None and tsat >= float(cfg.get("tsat_replete_min", 20))
        )
        if cfg.get("require_iron_replete_before_increase", True) and not iron_replete:
            out.append(DoseAdjustmentSuggestion(
                drug_class="ESA",
                severity=Severity.INFO,
                action="defer_increase_check_iron",
                current_dose=current_text,
                suggested_dose="先評估/處理鐵狀態，再決定 ESA 是否增量",
                change_percent=None,
                title="Hb 偏低但鐵狀態未達增量條件",
                rationale="若缺鐵未處理，直接增加 ESA 反應可能有限。",
                evidence=[f"Hb={hb}", f"Ferritin={ferritin}", f"TSAT={tsat}", f"目前 {current_text}"],
                requires_physician_approval=require_approval,
            ))
        else:
            pct = int(cfg.get("increase_percent", 25))
            out.append(DoseAdjustmentSuggestion(
                drug_class="ESA",
                severity=Severity.WARNING,
                action="increase",
                current_dose=current_text,
                suggested_dose=_changed_dose_text(current, esa, pct),
                change_percent=pct,
                title=f"Hb 偏低且鐵狀態可接受，建議 ESA 增量 {pct}%",
                rationale="Hb 低於目標下限，且鐵狀態未顯示明顯不足。",
                evidence=[f"Hb={hb}", f"Ferritin={ferritin}", f"TSAT={tsat}", f"目前 {current_text}"],
                requires_physician_approval=require_approval,
            ))
    return out


def _iron_adjustments(labs: list[LabResult], meds: list[Medication], rules: dict[str, Any]) -> list[DoseAdjustmentSuggestion]:
    cfg = rules.get("iron", {})
    safety = rules.get("safety", {})
    ferritin = _lab(labs, "Ferritin")
    tsat = _lab(labs, "TSAT")
    iron = _first_med(meds, {"IRON_IV", "IRON_PO"})
    require_approval = bool(safety.get("require_physician_approval", True))
    out: list[DoseAdjustmentSuggestion] = []

    if ferritin is None and tsat is None:
        return out

    if (ferritin is not None and ferritin >= float(cfg.get("ferritin_hold_above", 500))) or (
        tsat is not None and tsat >= float(cfg.get("tsat_hold_above", 45))
    ):
        out.append(DoseAdjustmentSuggestion(
            drug_class="IRON",
            severity=Severity.INFO,
            action="hold",
            current_dose=_dose_text(iron) if iron else "未見鐵劑",
            suggested_dose="暫停或延後鐵劑，需醫師確認",
            change_percent=None,
            title="鐵狀態偏高，建議暫緩鐵劑",
            rationale="Ferritin 或 TSAT 已達偏高門檻。",
            evidence=[f"Ferritin={ferritin}", f"TSAT={tsat}"],
            requires_physician_approval=require_approval,
        ))
    elif (ferritin is not None and ferritin < float(cfg.get("ferritin_low", 100))) or (
        tsat is not None and tsat < float(cfg.get("tsat_low", 20))
    ):
        out.append(DoseAdjustmentSuggestion(
            drug_class="IRON",
            severity=Severity.WARNING,
            action="supplement",
            current_dose=_dose_text(iron) if iron else "未見鐵劑",
            suggested_dose=f"{cfg.get('suggested_iv_iron_dose', 'Venofer 100mg')}，{cfg.get('suggested_iv_iron_frequency', '需醫師確認')}",
            change_percent=None,
            title="鐵狀態偏低，建議補鐵評估",
            rationale="Ferritin 或 TSAT 低於門檻。",
            evidence=[f"Ferritin={ferritin}", f"TSAT={tsat}"],
            requires_physician_approval=require_approval,
        ))
    return out


def _mbd_adjustments(labs: list[LabResult], meds: list[Medication], rules: dict[str, Any]) -> list[DoseAdjustmentSuggestion]:
    cfg = rules.get("mbd", {})
    safety = rules.get("safety", {})
    p = _lab(labs, "P")
    cca = _lab(labs, "cCa")
    caxp = _lab(labs, "CaXP")
    ipth = _lab(labs, "iPTH")
    binder = _first_med(meds, {"CALCIUM_BINDER", "NON_CA_BINDER", "AL_BINDER"})
    vitd = _first_med(meds, {"ACTIVE_VITD", "CALCIMIMETIC"})
    require_approval = bool(safety.get("require_physician_approval", True))
    out: list[DoseAdjustmentSuggestion] = []

    p_high = p is not None and p > float(cfg.get("phosphate_high", 5.5))
    ca_high = cca is not None and cca > float(cfg.get("corrected_calcium_high", 10.2))
    caxp_high = caxp is not None and caxp > float(cfg.get("calcium_phosphate_product_high", 55))
    ipth_high = ipth is not None and ipth > float(cfg.get("ipth_high", 600))

    if p_high and (ca_high or caxp_high) and binder and binder.drug_class == "CALCIUM_BINDER":
        pct = int(cfg.get("calcium_binder_decrease_percent", 25))
        out.append(DoseAdjustmentSuggestion(
            drug_class="CKD-MBD",
            severity=Severity.WARNING,
            action="decrease_or_switch_binder",
            current_dose=_dose_text(binder),
            suggested_dose=f"含鈣降磷藥減量 {pct}% 或改非鈣型，需醫師確認",
            change_percent=-pct,
            title="高磷合併鈣/鈣磷乘積偏高，避免增加含鈣降磷藥",
            rationale="高鈣或 CaXP 偏高時，含鈣降磷藥可能增加鈣負荷。",
            evidence=[f"P={p}", f"cCa={cca}", f"CaXP={caxp}", f"目前 {binder.name} {binder.dose} {binder.frequency}"],
            requires_physician_approval=require_approval,
        ))
    elif p_high:
        out.append(DoseAdjustmentSuggestion(
            drug_class="CKD-MBD",
            severity=Severity.WARNING,
            action="intensify_phosphate_control",
            current_dose=_dose_text(binder) if binder else "未見降磷藥",
            suggested_dose="評估飲食、透析充分性與降磷藥調整",
            change_percent=None,
            title="血磷偏高，建議加強控磷策略",
            rationale="血磷高於設定門檻。",
            evidence=[f"P={p}", f"cCa={cca}", f"CaXP={caxp}"],
            requires_physician_approval=require_approval,
        ))

    if ipth_high and not (ca_high or p_high):
        out.append(DoseAdjustmentSuggestion(
            drug_class="CKD-MBD",
            severity=Severity.INFO,
            action="evaluate_ipth_therapy",
            current_dose=_dose_text(vitd) if vitd else "未見 VitD/calcimimetic",
            suggested_dose="評估活性 VitD 或 calcimimetic 治療策略",
            change_percent=None,
            title="iPTH 偏高，建議評估 CKD-MBD 治療",
            rationale="iPTH 高於設定門檻，且目前鈣磷未同時偏高。",
            evidence=[f"iPTH={ipth}", f"P={p}", f"cCa={cca}"],
            requires_physician_approval=require_approval,
        ))
    elif ipth_high and cfg.get("vitamin_d_hold_when_calcium_or_phosphate_high", True):
        out.append(DoseAdjustmentSuggestion(
            drug_class="CKD-MBD",
            severity=Severity.INFO,
            action="avoid_vitd_escalation",
            current_dose=_dose_text(vitd) if vitd else "未見 VitD/calcimimetic",
            suggested_dose="暫不建議直接增加活性 VitD；先處理高鈣/高磷風險",
            change_percent=None,
            title="iPTH 偏高但鈣或磷也偏高，需謹慎調整 VitD",
            rationale="增加活性 VitD 可能加重高鈣或高磷。",
            evidence=[f"iPTH={ipth}", f"P={p}", f"cCa={cca}", f"CaXP={caxp}"],
            requires_physician_approval=require_approval,
        ))
    return out


def _lab(labs: list[LabResult], item_key: str) -> float | None:
    values = [lab.value for lab in labs if lab.item_key == item_key and lab.value is not None]
    return values[-1] if values else None


def _first_med(meds: list[Medication], classes: set[str]) -> Medication | None:
    return next((med for med in meds if med.drug_class in classes), None)


def _dose_number(raw: str) -> float | None:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(raw))
    return float(match.group(1)) if match else None


def _dose_text(med: Medication | None) -> str:
    if med is None:
        return "未見用藥"
    bits = [med.name, med.dose, med.frequency]
    return " ".join(str(bit) for bit in bits if str(bit).strip())


def _changed_dose_text(current: float | None, med: Medication, pct: int) -> str:
    if current is None:
        return f"{'增加' if pct > 0 else '減少'} {abs(pct)}%，需醫師確認"
    new_dose = round(current * (1 + pct / 100), 1)
    if new_dose.is_integer():
        dose_text = str(int(new_dose))
    else:
        dose_text = str(new_dose)
    return f"{med.name} {dose_text} {med.frequency}".strip()
