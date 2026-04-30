import pandas as pd

import app


def test_permissions_match_requested_roles():
    assert app._can_edit("醫師", "rule_settings")
    assert app._can_edit("醫師", "dialysis_orders")
    assert app._can_edit("醫師", "drug_settings")
    assert app._can_edit("醫師", "staff_settings")
    assert app._can_edit("護理長", "staff_settings")

    assert not app._can_edit("護理師", "rule_settings")
    assert not app._can_edit("護理長", "rule_settings")
    assert not app._can_edit("護理師", "drug_settings")
    assert not app._can_edit("護理長", "drug_settings")
    assert not app._can_edit("護理師", "staff_settings")
    assert not app._can_edit("護理長", "dialysis_orders")

    for role in ["醫師", "護理長", "護理師"]:
        assert app._can_edit(role, "problem_list")
        assert app._can_edit(role, "clinical_events")


def test_problem_categories_can_filter_and_merge_without_dropping_rows():
    rows = pd.DataFrame([
        {
            "row_id": "row-1",
            "chart_no": "12345A",
            "problem": "背景疾病",
            "problem_categories": '["Underlying disease"]',
            "status": "Active",
        },
        {
            "row_id": "row-2",
            "chart_no": "12345A",
            "problem": "同時需要追蹤",
            "problem_categories": '["Underlying disease","現在待處理問題"]',
            "status": "Active",
        },
        {
            "row_id": "row-3",
            "chart_no": "12345A",
            "problem": "待處理",
            "problem_categories": '["現在待處理問題"]',
            "status": "Active",
        },
    ])

    current = app._filter_problem_rows(rows, "現在待處理問題")
    assert set(current["row_id"]) == {"row-2", "row-3"}

    edited = current.copy()
    edited.loc[edited["row_id"] == "row-3", "status"] = "Inactive"
    merged = app._merge_problem_rows(rows, edited)

    assert set(merged["row_id"]) == {"row-1", "row-2", "row-3"}
    assert merged.loc[merged["row_id"] == "row-1", "status"].iloc[0] == "Active"
    assert merged.loc[merged["row_id"] == "row-3", "status"].iloc[0] == "Inactive"


def test_problem_owner_role_defaults_to_current_role():
    options = ["醫師", "護理長", "護理師"]
    assert app._default_problem_owner_role_index("醫師", options) == 0
    assert app._default_problem_owner_role_index("護理長", options) == 1
    assert app._default_problem_owner_role_index("護理師", options) == 2
    assert app._default_problem_owner_role_index("管理員", options) == 2


def test_patient_email_mask_name_never_uses_chart_no():
    assert app._patient_email_mask_name("黃大明") == "黃O明"
    assert app._patient_email_mask_name("王美") == "王O"
    assert app._patient_email_mask_name("") == "未填"
