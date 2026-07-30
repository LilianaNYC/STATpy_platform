"""Unit tests for SAAS workspace selector helpers."""

from __future__ import annotations

from STATpy_platform.features.saas.domain import selectors


def test_selector_normalizers_do_not_require_dash():
    assert selectors.normalize_selected_models(["model-a", "", " model-b "]) == ["model-a", "model-b"]
    assert selectors.normalize_selected_mev_mode(None) == selectors.DEFAULT_MEV_TYPE
    assert selectors.normalize_snapshot_period("unknown") == selectors.DEFAULT_SUBNAV_VIEW


def test_compare_against_excludes_primary_cycle():
    values = [option["value"] for option in selectors.RUN_FOR_OPTIONS]
    if len(values) < 2:
        return

    primary, other = values[:2]
    assert selectors.normalize_compare_against_values([primary, other, "missing"], primary) == [other]


def test_run_for_and_compare_against_labels(monkeypatch):
    monkeypatch.setattr(
        selectors,
        "RUN_FOR_OPTIONS",
        [
            {"label": "Cycle A", "value": "Cycle A"},
            {"label": "Cycle B", "value": "Cycle B"},
        ],
    )

    assert selectors.run_for_meta_label([]) == "No Model Use Case / Cycle selected"
    assert selectors.run_for_meta_label(["Cycle A", "Cycle B"]) == "All Model Use Case / Cycle values"
    assert selectors.run_for_meta_label(["Cycle A"]) == "Cycle A"

    assert selectors.build_compare_against_options("Cycle A") == [
        {"label": "None", "value": selectors.COMPARE_AGAINST_NONE_VALUE},
        {"label": "Cycle B", "value": "Cycle B"},
    ]
    assert selectors.compare_against_toggle_label([], "Cycle A") == "None"
    assert selectors.compare_against_toggle_label(["Cycle B"], "Cycle A") == "Cycle B"


def test_model_toggle_label_uses_descriptive_name():
    # Specific-Models options are keyed by Descriptive Name (the "parent"
    # of one or more Model Names, see model_options_for_filters), so the
    # selection values passed in here already are descriptive names.
    options = [
        {"label": "Model A", "value": "Model A"},
        {"label": "Model B", "value": "Model B"},
    ]

    assert selectors.model_toggle_label(["Model A"], options, True) == "Disabled while Segment is selected"
    assert selectors.model_toggle_label([], options, False) == "Select models"
    assert selectors.model_toggle_label(["Model A", "Model B"], options, False) == "All"
    assert selectors.model_toggle_label(["Model A"], options, False) == "Model A"
    assert selectors.model_toggle_label(["Model A", "Model C"], options, False) == "2 models selected"


def test_group_effective_models_groups_children_under_parent(monkeypatch):
    # Two Model Names sharing a Descriptive Name collapse into one parent group
    # (even when not adjacent in the effective list); a model that is its own
    # parent stays a singleton. Both parents are the same Model Group here, so
    # they keep first-appearance order (the Model Group sort is a no-op tie).
    monkeypatch.setattr(
        selectors,
        "effective_model_names",
        lambda *args, **kwargs: ["PD_model_d", "PD_model_a", "PD_model_e"],
    )
    labels = {"PD_model_d": "PD Model D", "PD_model_e": "PD Model D", "PD_model_a": "PD Model A"}
    monkeypatch.setattr(selectors, "model_descriptive_label", lambda name: labels[name])
    monkeypatch.setitem(
        selectors.SAAS_PAGE_DATA,
        "model_group_map",
        {"PD_model_d": ["PD"], "PD_model_e": ["PD"], "PD_model_a": ["PD"]},
    )
    monkeypatch.setitem(selectors.SAAS_PAGE_DATA, "model_group_values", ["PD"])

    assert selectors.group_effective_models(None, []) == [
        ("PD Model D", ["PD_model_d", "PD_model_e"]),
        ("PD Model A", ["PD_model_a"]),
    ]


def test_group_effective_models_orders_parents_by_model_group(monkeypatch):
    # Parents are ordered by their (first member's) Model Group, following the
    # workbook's natural model_group_values order -- not first-appearance --
    # with first-appearance only breaking ties within the same group.
    monkeypatch.setattr(
        selectors,
        "effective_model_names",
        lambda *args, **kwargs: ["EAD_model_a", "PD_model_a", "PD_model_b", "LGD_model_a"],
    )
    labels = {
        "EAD_model_a": "EAD Model A", "PD_model_a": "PD Model A",
        "PD_model_b": "PD Model B", "LGD_model_a": "LGD Model A",
    }
    monkeypatch.setattr(selectors, "model_descriptive_label", lambda name: labels[name])
    monkeypatch.setitem(
        selectors.SAAS_PAGE_DATA,
        "model_group_map",
        {
            "EAD_model_a": ["EAD"], "PD_model_a": ["PD"],
            "PD_model_b": ["PD"], "LGD_model_a": ["LGD"],
        },
    )
    monkeypatch.setitem(selectors.SAAS_PAGE_DATA, "model_group_values", ["PD", "EAD", "LGD"])

    assert selectors.group_effective_models(None, []) == [
        ("PD Model A", ["PD_model_a"]),
        ("PD Model B", ["PD_model_b"]),
        ("EAD Model A", ["EAD_model_a"]),
        ("LGD Model A", ["LGD_model_a"]),
    ]


def test_model_scope_summary_counts_distinct_descriptive_names_not_all(monkeypatch):
    # Two Model Names share a Descriptive Name, one more model exists in scope
    # under a *different* name but is not selected -- 2 distinct Descriptive
    # Names are in scope, and it is not "All" since a third is reachable.
    monkeypatch.setattr(
        selectors,
        "effective_model_names",
        lambda *args, **kwargs: ["PD_model_d", "PD_model_e"],
    )
    monkeypatch.setattr(
        selectors,
        "model_names_for_filters",
        lambda *args, **kwargs: ["PD_model_d", "PD_model_e", "PD_model_a"],
    )
    labels = {"PD_model_d": "PD Model D", "PD_model_e": "PD Model D", "PD_model_a": "PD Model A"}
    monkeypatch.setattr(selectors, "model_descriptive_label", lambda name: labels[name])

    count, is_all = selectors.model_scope_summary(None, ["PD Model D"])

    assert count == 1
    assert is_all is False


def test_model_scope_summary_detects_all_reachable_models_selected(monkeypatch):
    monkeypatch.setattr(
        selectors,
        "effective_model_names",
        lambda *args, **kwargs: ["PD_model_d", "PD_model_a"],
    )
    monkeypatch.setattr(
        selectors,
        "model_names_for_filters",
        lambda *args, **kwargs: ["PD_model_d", "PD_model_a"],
    )
    labels = {"PD_model_d": "PD Model D", "PD_model_a": "PD Model A"}
    monkeypatch.setattr(selectors, "model_descriptive_label", lambda name: labels[name])

    count, is_all = selectors.model_scope_summary(None, ["PD Model D", "PD Model A"])

    assert count == 2
    assert is_all is True


def test_scenario_and_historical_stat_labels():
    assert selectors.format_scenario_label(selectors.DEFAULT_SCENARIO_FILTER) == "All"
    assert selectors.format_scenario_label("int_severe") == "Int Severe"

    assert selectors.show_historical_statistics("ON") is True
    assert selectors.show_historical_statistics(None) is False


def test_resolve_date_range_selection_applies_window_presets():
    periods = ["2024-03-31", "2024-06-30", "2024-09-30"]

    assert selectors.resolve_date_range_selection(
        periods,
        "last-2",
        None,
        None,
        {"type": "window"},
        window_trigger_type="window",
        from_trigger_type="from",
        to_trigger_type="to",
        range_preset_counts={"last-2": 2},
    ) == {"from": "2024-06-30", "to": "2024-09-30"}
    assert selectors.resolve_date_range_selection(
        periods,
        "all",
        "2024-03-31",
        "2024-09-30",
        {"type": "window"},
        window_trigger_type="window",
        from_trigger_type="from",
        to_trigger_type="to",
    ) == {"from": "", "to": ""}


def test_resolve_date_range_selection_keeps_valid_manual_bounds():
    periods = ["2024-03-31", "2024-06-30", "2024-09-30"]

    assert selectors.resolve_date_range_selection(
        periods,
        None,
        "2024-03-31",
        "2024-09-30",
        {"type": "from"},
        window_trigger_type="window",
        from_trigger_type="from",
        to_trigger_type="to",
    ) == {"from": "2024-03-31", "to": "2024-09-30"}
    assert selectors.resolve_date_range_selection(
        periods,
        None,
        "not-a-period",
        "2024-09-30",
        {"type": "from"},
        window_trigger_type="window",
        from_trigger_type="from",
        to_trigger_type="to",
    ) == {"from": "", "to": "2024-09-30"}


def test_resolve_date_range_selection_corrects_crossed_bounds_by_trigger():
    periods = ["2024-03-31", "2024-06-30", "2024-09-30"]

    assert selectors.resolve_date_range_selection(
        periods,
        None,
        "2024-09-30",
        "2024-03-31",
        {"type": "from"},
        window_trigger_type="window",
        from_trigger_type="from",
        to_trigger_type="to",
    ) == {"from": "2024-09-30", "to": "2024-09-30"}
    assert selectors.resolve_date_range_selection(
        periods,
        None,
        "2024-09-30",
        "2024-03-31",
        {"type": "to"},
        window_trigger_type="window",
        from_trigger_type="from",
        to_trigger_type="to",
    ) == {"from": "2024-03-31", "to": "2024-03-31"}
