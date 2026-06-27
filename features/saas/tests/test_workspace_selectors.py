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

    assert selectors.run_for_meta_label([]) == "No Reporting Cycle selected"
    assert selectors.run_for_meta_label(["Cycle A", "Cycle B"]) == "All Reporting Cycle values"
    assert selectors.run_for_meta_label(["Cycle A"]) == "Cycle A"

    assert selectors.build_compare_against_options("Cycle A") == [
        {"label": "None", "value": selectors.COMPARE_AGAINST_NONE_VALUE},
        {"label": "Cycle B", "value": "Cycle B"},
    ]
    assert selectors.compare_against_toggle_label([], "Cycle A") == "None"
    assert selectors.compare_against_toggle_label(["Cycle B"], "Cycle A") == "Cycle B"


def test_model_toggle_label_uses_descriptive_name(monkeypatch):
    monkeypatch.setitem(
        selectors.SAAS_PAGE_DATA,
        "model_descriptive_name_map",
        {"model-a": "Model A"},
    )
    options = [
        {"label": "Model A", "value": "model-a"},
        {"label": "Model B", "value": "model-b"},
    ]

    assert selectors.model_toggle_label(["model-a"], options, True) == "Disabled while Segment is selected"
    assert selectors.model_toggle_label([], options, False) == "Select models"
    assert selectors.model_toggle_label(["model-a", "model-b"], options, False) == "All"
    assert selectors.model_toggle_label(["model-a"], options, False) == "Model A"
    assert selectors.model_toggle_label(["model-a", "model-c"], options, False) == "2 models selected"


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
