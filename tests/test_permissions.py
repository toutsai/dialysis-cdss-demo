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
