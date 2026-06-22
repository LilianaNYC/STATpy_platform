"""Unit tests for small SAAS workspace view helpers."""

from __future__ import annotations

from datetime import datetime

from STATpy_platform.features.saas.pages.workspace import page, views


def test_single_select_option_classes_marks_selected_value():
    option_ids = [{"value": "a"}, {"value": "b"}]

    assert views.single_select_option_classes("b", option_ids) == [
        "single-select-option",
        "single-select-option is-selected",
    ]


def test_toggle_menu_class_toggles_open_class():
    base_class = "checkbox-dropdown-menu"

    assert views.toggle_menu_class(base_class, base_class=base_class) == f"{base_class} open"
    assert views.toggle_menu_class(f"{base_class} open", base_class=base_class) == base_class


def test_build_single_mev_option_buttons_uses_model_option_id():
    buttons = views.build_single_mev_option_buttons(
        [{"label": "MEV A", "value": "mev_a"}],
        "mev_a",
        "Model A",
    )

    assert len(buttons) == 1
    assert buttons[0].id == {
        "type": page.MODEL_MEV_SINGLE_OPTION_TYPE,
        "model": "Model A",
        "value": "mev_a",
    }
    assert buttons[0].className == "single-select-option is-selected"


def test_model_panel_id_creates_stable_anchor():
    assert views.model_panel_id("Model A / B") == "saas-model-panel-model-a-b"


def test_build_subnav_models_uses_model_panel_anchor(monkeypatch):
    monkeypatch.setattr(views.selectors, "effective_model_names", lambda _segment, _selected: ["Model A"])
    monkeypatch.setattr(views.selectors, "model_descriptive_label", lambda model_name: f"Label {model_name}")

    subnav_children = views.build_subnav_models(None, None)
    button = subnav_children[0].children[0]

    assert button.children == "Label Model A"
    assert button.__dict__["data-saas-scroll-target"] == "saas-model-panel-model-a"


def test_scenario_dropdown_uses_single_select_ids():
    dropdown = views.build_model_scenario_dropdown(
        "Model A",
        "baseline",
        [
            {"label": "Baseline", "value": "baseline"},
            {"label": "Severe", "value": "intsevere"},
        ],
        single_select=True,
    )

    hidden_dropdown = dropdown.children[0]
    toggle_button = dropdown.children[2]

    assert hidden_dropdown.id == {
        "type": page.MODEL_SCENARIO_FILTER_TYPE,
        "model": "Model A",
    }
    assert hidden_dropdown.value == "baseline"
    assert toggle_button.children == "Baseline"


def test_mev_type_dropdown_marks_selected_mode():
    dropdown = views.build_model_mev_type_dropdown(
        "Model A",
        "raw_only",
        [
            {"label": "Transformed only", "value": "transformed_only"},
            {"label": "Raw only", "value": "raw_only"},
        ],
    )

    hidden_dropdown = dropdown.children[0]
    option_buttons = dropdown.children[2].children

    assert hidden_dropdown.id == {
        "type": page.MODEL_MEV_TYPE_FILTER_TYPE,
        "model": "Model A",
    }
    assert hidden_dropdown.value == "raw_only"
    assert option_buttons[1].className == "single-select-option is-selected"


def test_mev_toggle_label_handles_all_raw_mevs():
    label = views.mev_toggle_label(
        "raw_only",
        None,
        ["raw_a", "raw_b"],
        [],
        [
            {"label": "Raw A", "value": "raw_a"},
            {"label": "Raw B", "value": "raw_b"},
        ],
    )

    assert label == "All raw MEVs"


def test_build_model_chart_cards_returns_empty_mev_card_without_figure_builder():
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("figure builder should not be called")

    cards = views.build_model_chart_cards(
        "Model A",
        [{"MEV Name": "MEV A", "Scenario": "baseline"}],
        [],
        "family",
        ["baseline"],
        "history",
        None,
        None,
        None,
        [],
        [],
        figure_builder=fail_if_called,
    )

    assert cards[0].children[0].children[0].children[0].children == "No MEVs selected"


def test_build_model_chart_cards_uses_injected_figure_builder():
    calls = []

    def build_figure(*args):
        calls.append(args)
        return {"data": [], "layout": {"title": "Test"}}

    cards = views.build_model_chart_cards(
        "Model A",
        [{"MEV Name": "MEV A", "Scenario": "baseline"}],
        [{"MEV Name": "MEV A", "Scenario": "baseline"}],
        "family",
        ["baseline"],
        "history",
        None,
        None,
        None,
        ["MEV A"],
        [],
        figure_builder=build_figure,
    )

    assert len(calls) == 1
    assert cards[0].children[-1].figure == {"data": [], "layout": {"title": "Test"}}


def test_format_monitoring_date_returns_quarter_label():
    assert views.format_monitoring_date(datetime(2024, 6, 30)) == "2024Q2"
    assert views.format_monitoring_date("2024-12-31") == "2024Q4"


def test_build_monitoring_threshold_chips_returns_four_bands():
    chips = views.build_monitoring_threshold_chips(
        {
            "green_low": 1.0,
            "green_high": 2.0,
            "amber_low_low": 0.5,
            "amber_low_high": 1.0,
            "amber_high_low": 2.0,
            "amber_high_high": 2.5,
            "red_low_cutoff": 0.5,
            "red_high_cutoff": 2.5,
        }
    )

    assert len(chips) == 4
    assert chips[0].className == "pd-mev-threshold-chip pd-mev-threshold-chip-green"
    assert chips[-1].className == "pd-mev-threshold-chip pd-mev-threshold-chip-red"


def test_build_historical_dispersion_summary_empty_state():
    summary = views.build_historical_dispersion_summary(
        [{"Date": datetime(2024, 3, 31), "Scenario": "baseline", "Run For": "Cycle A", "MEV Value": 1.0}],
        ["baseline"],
    )

    assert summary.className == "saas-historical-dispersion saas-historical-dispersion-empty"
