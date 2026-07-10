"""Unit tests for small SAAS workspace view helpers."""

from __future__ import annotations

from datetime import datetime

from dash.development.base_component import Component

from STATpy_platform.features.saas.ui.views import workspace as page, components as views


def _children_of(node) -> list:
    children = getattr(node, "children", None)
    if children is None:
        return []
    if isinstance(children, (list, tuple)):
        return list(children)
    return [children]


def _find_component_by_id(node, component_id):
    if not isinstance(node, Component):
        return None
    if getattr(node, "id", None) == component_id:
        return node
    for child in _children_of(node):
        found = _find_component_by_id(child, component_id)
        if found is not None:
            return found
    return None


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
    monkeypatch.setattr(views.selectors, "effective_model_names", lambda _segment, _selected, **_kwargs: ["Model A"])
    monkeypatch.setattr(views.selectors, "model_descriptive_label", lambda model_name: f"Label {model_name}")

    label, subnav_children = views.build_subnav_models(None, None)
    button = subnav_children[0].children[0]

    assert label == "Models in Scope"
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

    assert label == "All"


def test_mev_toggle_label_handles_all_family_mevs():
    label = views.mev_toggle_label(
        "family",
        views.records.FAMILY_ALL_VALUE,
        [],
        [
            {"label": "All", "value": views.records.FAMILY_ALL_VALUE},
            {"label": "Transformed A", "value": "transformed_a"},
        ],
        [],
    )

    assert label == "All"


def test_build_model_panel_defaults_family_picker_to_all(monkeypatch):
    monkeypatch.setitem(
        views.records.SAAS_PAGE_DATA,
        "model_mev_map",
        {"Model A": {"transformed": ["Transformed A", "Transformed B"], "raw": ["Raw A", "Raw B"]}},
    )
    monkeypatch.setitem(
        views.records.SAAS_PAGE_DATA,
        "model_mev_family_map",
        {"Model A": {"Transformed A": ["Raw A"], "Transformed B": ["Raw B"]}},
    )
    monkeypatch.setitem(
        views.SAAS_PAGE_DATA,
        "model_segments_map",
        {"Model A": ["Segment A"]},
    )
    monkeypatch.setattr(views.selectors, "model_descriptive_label", lambda model_name: model_name)

    panel = views.build_model_panel(
        1,
        "Model A",
        [
            {
                "Model Name": "Model A",
                "MEV Name": "Transformed A",
                "Scenario": "baseline",
                "Quarter": 0,
                "Date": datetime(2024, 3, 31),
                "Run For": "Cycle A",
            },
            {
                "Model Name": "Model A",
                "MEV Name": "Raw A",
                "Scenario": "baseline",
                "Quarter": 0,
                "Date": datetime(2024, 3, 31),
                "Run For": "Cycle A",
            },
            {
                "Model Name": "Model A",
                "MEV Name": "Transformed B",
                "Scenario": "baseline",
                "Quarter": 0,
                "Date": datetime(2024, 3, 31),
                "Run For": "Cycle A",
            },
            {
                "Model Name": "Model A",
                "MEV Name": "Raw B",
                "Scenario": "baseline",
                "Quarter": 0,
                "Date": datetime(2024, 3, 31),
                "Run For": "Cycle A",
            },
        ],
        ["Cycle A"],
        [],
        "history",
        None,
        None,
        figure_builder=lambda *_args, **_kwargs: {"data": [], "layout": {}},
    )

    family_picker = _find_component_by_id(
        panel,
        {"type": page.MODEL_MEV_SINGLE_VALUE_TYPE, "model": "Model A"},
    )

    assert family_picker is not None
    assert family_picker.value == views.records.FAMILY_ALL_VALUE


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
        figure_builder=build_figure,
    )

    assert len(calls) == 1
    assert cards[0].children[0].children[-1].figure == {"data": [], "layout": {"title": "Test"}}


def test_build_model_chart_cards_groups_each_family_onto_its_own_row(monkeypatch):
    monkeypatch.setattr(
        views.records,
        "family_map_for_model",
        lambda _model_name: {"T1": ["R1", "R2"], "T2": ["R3"]},
    )
    mev_names = ["T1", "R1", "R2", "T2", "R3"]
    records_ = [{"MEV Name": name, "Scenario": "baseline"} for name in mev_names]

    cards = views.build_model_chart_cards(
        "Model A",
        records_,
        records_,
        "family",
        ["baseline"],
        "history",
        None,
        None,
        None,
        mev_names,
        figure_builder=lambda *_args: {"data": [], "layout": {}},
    )

    assert [row.className for row in cards] == ["pd-mev-chart-family-row"] * 3
    assert [len(row.children) for row in cards] == [2, 1, 2]
    titles_by_row = [
        [card.children[0].children[0].children[0].children for card in row.children]
        for row in cards
    ]
    assert titles_by_row == [["T1", "R1"], ["R2"], ["T2", "R3"]]


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


def _text_nodes(node) -> list[str]:
    texts: list[str] = []
    if isinstance(node, str):
        return [node]
    for child in _children_of(node):
        texts.extend(_text_nodes(child))
    return texts


def test_model_attribute_lines_carry_full_per_model_attributes(monkeypatch):
    monkeypatch.setitem(views.SAAS_PAGE_DATA, "model_segments_map", {"PD_model_d": ["Cyclical"]})
    monkeypatch.setitem(views.SAAS_PAGE_DATA, "model_region_map", {"PD_model_d": ["US", "EU"]})
    monkeypatch.setitem(views.SAAS_PAGE_DATA, "model_group_map", {"PD_model_d": ["PD"]})
    monkeypatch.setitem(views.SAAS_PAGE_DATA, "model_portfolio_map", {"PD_model_d": ["C&I"]})
    monkeypatch.setattr(views.selectors, "model_development_date", lambda *_args: datetime(2024, 3, 31))

    texts = [line.children for line in views.model_attribute_lines("PD_model_d", ["Cycle A"])]

    # Single value -> singular label; several distinct values -> pluralized.
    assert "Regions: US, EU" in texts
    assert "Model Group: PD" in texts
    assert "Portfolio: C&I" in texts
    assert any(text.startswith("Segment: ") for text in texts)
    assert any(text.startswith("Development Date: ") for text in texts)


def test_build_model_group_card_nests_children_under_one_parent_header():
    members = [views.html.Div("child-a"), views.html.Div("child-b")]
    card = views.build_model_group_card(1, "PD Model D", members)

    texts = _text_nodes(card)
    assert "PD Model D" in texts          # parent label rendered once
    assert "1. Parent Model" in texts     # numbered parent kicker
    assert "2 models" in texts            # member count shown for multi-child parents

    member_container = card.children[-1]
    assert member_container.className == "pd-mev-model-group-members"
    assert member_container.children == members
