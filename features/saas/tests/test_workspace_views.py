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


def _collect_by_type(node, type_name, hits):
    if type(node).__name__ == type_name:
        hits.append(node)
    for child in _children_of(node):
        _collect_by_type(child, type_name, hits)


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


def test_model_group_id_creates_stable_anchor():
    assert views.model_group_id("PD Model D") == "saas-model-group-pd-model-d"


def test_build_subnav_models_emits_one_chip_per_parent(monkeypatch):
    # Two Model Names sharing a Descriptive Name -> a single parent chip that
    # scrolls to the parent card, not two identical-looking child chips.
    monkeypatch.setattr(
        views.selectors,
        "group_effective_models",
        lambda _segment, _selected, **_kwargs: [
            ("PD Model D", ["PD_model_d", "PD_model_e"]),
            ("PD Model A", ["PD_model_a"]),
        ],
    )

    label, subnav_children = views.build_subnav_models(None, None)
    buttons = subnav_children[0].children

    assert label == "Models in Scope"
    assert [button.children for button in buttons] == ["PD Model D", "PD Model A"]
    assert buttons[0].__dict__["data-saas-scroll-target"] == "saas-model-group-pd-model-d"


def test_build_subnav_models_stays_on_models_when_a_segment_is_active(monkeypatch):
    # A Segment selection narrows the in-scope models (applied inside
    # group_effective_models); the section stays "Models in Scope" rather than
    # switching to a segment list.
    monkeypatch.setattr(
        views.selectors,
        "group_effective_models",
        lambda _segment, _selected, **_kwargs: [("PD Model A", ["PD_model_a"])],
    )

    label, subnav_children = views.build_subnav_models(["Cyclical"], None)

    assert label == "Models in Scope"
    assert [button.children for button in subnav_children[0].children] == ["PD Model A"]


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

    # Child panel is a collapsible <details>, collapsed on first render.
    assert type(panel).__name__ == "Details"
    assert panel.open is False
    body = panel.children[-1]
    assert body.className == "pd-mev-model-body"
    grid = _find_component_by_id(panel, {"type": page.MODEL_MEV_GRID_TYPE, "model": "Model A"})
    assert grid is not None

    # Charts are deferred: no dcc.Graph is rendered up front, and a hidden
    # chart-trigger button is present for the client to click on first open.
    graphs = []
    _collect_by_type(panel, "Graph", graphs)
    assert graphs == []
    trigger = _find_component_by_id(panel, {"type": page.MODEL_CHART_TRIGGER_TYPE, "model": "Model A"})
    assert trigger is not None

    # The summary shows the segment, not the raw Model Name (its GMIS name);
    # no tooltip is attached to the kicker.
    kicker = panel.children[0].children[0].children[0]
    heading_text = kicker.children
    assert heading_text.startswith("1. ")
    assert "Model A" not in heading_text


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


def test_build_model_chart_cards_title_shows_mev_type_tag(monkeypatch):
    monkeypatch.setattr(views.selectors, "mev_type_label", lambda name: {"MEV A": "Transformed", "MEV B": "—"}[name])

    cards = views.build_model_chart_cards(
        "Model A",
        [{"MEV Name": "MEV A", "Scenario": "baseline"}, {"MEV Name": "MEV B", "Scenario": "baseline"}],
        [{"MEV Name": "MEV A", "Scenario": "baseline"}, {"MEV Name": "MEV B", "Scenario": "baseline"}],
        "transformed_only",
        ["baseline"],
        "history",
        None,
        None,
        None,
        ["MEV A", "MEV B"],
        figure_builder=lambda *_args, **_kwargs: {"data": [], "layout": {}},
    )

    # A known type (Transformed/Raw) renders as a tag next to the title; an
    # unresolved type ("—") renders no tag rather than a literal "—" badge.
    title_a = cards[0].children[0].children[0].children[0].children
    title_b = cards[1].children[0].children[0].children[0].children
    assert title_a[0] == "MEV A"
    assert title_a[1].children == "Transformed"
    assert title_a[1].className == "pd-mev-chart-type-tag"
    assert title_b[0] == "MEV B"
    assert title_b[1] is None


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
    # The title Div's children are now [mev_label, type_tag_or_None] (the type
    # tag shows Transformed/Raw when known); grab just the label text.
    titles_by_row = [
        [card.children[0].children[0].children[0].children[0] for card in row.children]
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

    texts = [line.children for line in views.model_attribute_lines("PD_model_d")]

    # Single value -> singular label; several distinct values -> pluralized.
    assert "Regions: US, EU" in texts
    assert "Model Group: PD" in texts
    assert "Portfolio: C&I" in texts
    # Segment is shown in the child summary heading, not as an attribute row.
    assert not any(text.startswith("Segment") for text in texts)
    # Development Date is intentionally not shown on the cards.
    assert not any(text.startswith("Development Date") for text in texts)


def test_build_model_group_card_nests_children_under_one_collapsible_parent():
    members = [views.html.Div("child-a"), views.html.Div("child-b")]
    shared = [views.html.P("Region: US", className="pd-mev-model-attr")]
    card = views.build_model_group_card(1, "PD Model D", members, shared_attribute_lines=shared)

    # Collapsible <details>, open on first render so the child waterfall shows,
    # anchored for the subnav.
    assert card.id == "saas-model-group-pd-model-d"
    assert card.open is True

    texts = _text_nodes(card)
    assert "1. PD Model D" in texts       # numbered kicker is the only heading, carries the Model Descriptive Name
    assert "2 models" in texts            # member count shown for multi-child parents
    assert "Region: US" in texts          # shared attribute rolled up into the header

    member_container = card.children[-1]
    assert member_container.className == "pd-mev-model-group-members"
    assert member_container.children == members


def test_partition_group_attributes_rolls_shared_up_and_leaves_differences(monkeypatch):
    # d and e share Region/Model Group: those roll up to the parent (and are
    # suppressed on children). Segment is never rolled up -- it lives in the
    # child summary heading -- even though d and e differ on it.
    monkeypatch.setitem(views.SAAS_PAGE_DATA, "model_segments_map", {"d": ["Cyclical"], "e": ["Defensive"]})
    monkeypatch.setitem(views.SAAS_PAGE_DATA, "model_region_map", {"d": ["US"], "e": ["US"]})
    monkeypatch.setitem(views.SAAS_PAGE_DATA, "model_group_map", {"d": ["PD"], "e": ["PD"]})
    monkeypatch.setitem(views.SAAS_PAGE_DATA, "model_portfolio_map", {})

    shared_lines, shared_keys = views.partition_group_attributes(["d", "e"])

    assert shared_keys == frozenset({"Region", "Model Group"})
    assert "Region: US" in [line.children for line in shared_lines]
    assert "Segment" not in shared_keys

    # A singleton trivially shares its (rollable) attributes, so they roll up
    # into the header -- but Segment is never among them.
    singleton_lines, singleton_keys = views.partition_group_attributes(["d"])
    assert singleton_keys == frozenset({"Region", "Model Group"})
    assert "Segment" not in singleton_keys
    assert "Region: US" in [line.children for line in singleton_lines]
