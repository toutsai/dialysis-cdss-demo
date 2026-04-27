from __future__ import annotations

from collections import defaultdict

from src.domain.entities import LabResult, Medication, Recommendation
from src.domain.rules import Thresholds, evaluate_month


def build_recommendations(
    chart_nos: list[str],
    year_month: str,
    labs: list[LabResult],
    medications: list[Medication],
    thresholds: Thresholds,
) -> list[Recommendation]:
    labs_by_chart: dict[str, list[LabResult]] = defaultdict(list)
    meds_by_chart: dict[str, list[Medication]] = defaultdict(list)
    for lab in labs:
        labs_by_chart[lab.chart_no].append(lab)
    for med in medications:
        meds_by_chart[med.chart_no].append(med)

    out: list[Recommendation] = []
    for chart_no in chart_nos:
        out.extend(evaluate_month(
            chart_no=chart_no,
            year_month=year_month,
            labs=labs_by_chart.get(chart_no, []),
            medications=meds_by_chart.get(chart_no, []),
            thresholds=thresholds,
        ))
    return out
