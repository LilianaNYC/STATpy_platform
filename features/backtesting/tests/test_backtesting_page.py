"""Page-shell tests: layout builds, chrome reuse, and callback wiring."""

from __future__ import annotations

import pytest
from dash import ALL, Input, Output, State

from STATpy_platform.features.backtesting import dashboard, page_registry
from STATpy_platform.features.backtesting.callbacks import backtesting as callbacks
from STATpy_platform.features.backtesting.ui.views import backtesting as layout
from STATpy_platform.shared import theme
from STATpy_platform.shared.domain import constants as config


# ---------------------------------------------------------------------------
# Helpers for walking a Dash component tree
# ---------------------------------------------------------------------------


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        if child is None or isinstance(child, str):
            continue
        yield from _walk(child)


def _class_tokens(nodes) -> set[str]:
    """Class tokens across the tree.

    ``parent_className`` is included because ``dcc.Loading`` carries the
    ``dashboard-loading-shell`` wrapper class there rather than on ``className``.
    """
    tokens: set[str] = set()
    for node in nodes:
        for attribute in ("className", "parent_className"):
            value = getattr(node, attribute, None)
            if isinstance(value, str):
                tokens |= set(value.split())
    return tokens


def _ids(nodes) -> set:
    found = set()
    for node in nodes:
        node_id = getattr(node, "id", None)
        if isinstance(node_id, str):
            found.add(node_id)
    return found


def _text(nodes) -> str:
    parts = []
    for node in nodes:
        children = getattr(node, "children", None)
        if isinstance(children, str):
            parts.append(children)
        elif isinstance(children, (list, tuple)):
            parts.extend(child for child in children if isinstance(child, str))
    return " ".join(parts)


@pytest.fixture(scope="module")
def nodes():
    return list(_walk_all(layout.page_layout()))


def _walk_all(items):
    for item in items:
        yield from _walk(item)


# ---------------------------------------------------------------------------
# Layout builds
# ---------------------------------------------------------------------------


def test_page_layout_builds():
    assert layout.page_layout()


def test_page_content_builds_with_and_without_applied_filters():
    assert layout.build_page_content()
    assert layout.build_page_content(
        applied_filters={"segment": "Cyclical", "model": "all"},
        theme_value="dark",
    )


def test_every_section_anchor_is_present(nodes):
    present = _ids(nodes)
    for section_id in layout.SECTION_IDS:
        assert section_id in present, section_id


def test_all_nine_filters_are_present(nodes):
    present = _ids(nodes)
    for value_id in (
        layout.REGION_ID,
        layout.PORTFOLIO_ID,
        layout.MODEL_GROUP_ID,
        layout.SEGMENT_ID,
        layout.MODEL_ID,
        layout.RUN_FOR_ID,
        layout.SCENARIO_ID,
        layout.JN_FLAG_ID,
        layout.SNAPSHOT_ID,
    ):
        assert value_id in present, value_id


def test_filter_labels_read_as_specified(nodes):
    text = _text(nodes)
    for label in (
        "Region", "Portfolio", "Model Group", "Segment", "Model",
        "Model Use Case / Cycle", "Scenario", "J/N Flag", "Month End Snapshot",
    ):
        assert label in text, label

    # UI-only rename: the internal spelling must NOT leak into the interface.
    assert "Run For" not in text


# ---------------------------------------------------------------------------
# Chrome reuse -- the page must not invent its own vocabulary
# ---------------------------------------------------------------------------


def test_top_bar_uses_the_platform_filter_chrome(nodes):
    tokens = _class_tokens(nodes)
    for token in (
        "top-bar",
        "monitoring-controls",
        "monitoring-primary-filter-row",
        "monitoring-filter",
        "monitoring-dashboard-title",
    ):
        assert token in tokens, token


def test_dropdowns_use_the_shared_single_select_vocabulary(nodes):
    tokens = _class_tokens(nodes)
    assert "checkbox-dropdown" in tokens
    assert "single-select-dropdown" in tokens
    assert "checkbox-dropdown-toggle" in tokens


def test_subnav_uses_the_shared_subnav_classes(nodes):
    tokens = _class_tokens(nodes)
    for token in (
        "monitoring-section-subnav",
        "monitoring-section-subnav-group",
        "monitoring-section-subnav-label",
        "monitoring-section-subnav-links",
    ):
        assert token in tokens, token
    assert layout.SUBNAV_ID in _ids(nodes)


def test_cards_are_section_cards(nodes):
    assert "section-card" in _class_tokens(nodes)


def test_headings_come_from_the_shared_card_builders(nodes):
    # shared/ui/cards.py emits these; a page rolling its own headings would not.
    tokens = _class_tokens(nodes)
    assert "pd-chapter-heading" in tokens
    assert "pd-domain-heading" in tokens


def test_loading_shell_uses_the_shared_dashboard_loading_classes(nodes):
    tokens = _class_tokens(nodes)
    assert "dashboard-loading-shell" in tokens
    assert any(token.startswith("dashboard-loading-") for token in tokens)


def test_pre_apply_state_uses_the_saas_empty_state_treatment(nodes):
    """Before Apply, every section shows the platform's empty-state card rather
    than an empty chart."""
    tokens = _class_tokens(nodes)
    assert "pd-mev-empty-state" in tokens
    assert "chart-box" not in tokens


def test_summary_strip_labels_row_and_exposure_coverage_separately():
    strip = layout._build_summary_strip({
        "summary": {},
        "coverage": {"row_coverage": 0.5, "exposure_coverage": 0.25},
    })
    text = _text(list(_walk(strip)))

    assert "Row coverage: 50% of forecast rows carried a weight." in text
    assert "Exposure coverage: 25% of available EAD was represented." in text


def test_summary_strip_adds_mae_and_metric_aware_error_units():
    rate = layout._build_summary_strip({
        "metric": config.BACKTESTING_METRIC_PD,
        "summary": {"count": 36, "bias": 0.00085, "mae": 0.0021,
                    "mape": 0.07, "rmse": 0.0033, "hit_rate": 0.78, "rag": "Green"},
    })
    rate_text = " ".join(_text(list(_walk(rate))).split())
    assert "Bias: +0.08%" in rate_text
    assert "MAE: 0.21%" in rate_text
    assert "percentage points" in rate_text

    amount = layout._build_summary_strip({
        "metric": config.BACKTESTING_METRIC_EAD,
        "summary": {"count": 36, "bias": 1_501_304.5, "mae": 2_100_000,
                    "mape": 0.013, "rmse": 6_595_416.2, "hit_rate": 0.94, "rag": "Green"},
    })
    amount_text = " ".join(_text(list(_walk(amount))).split())
    assert "Bias: +$1.5m" in amount_text
    assert "MAE: $2.1m" in amount_text
    assert "RMSE: $6.6m" in amount_text


@pytest.mark.parametrize(
    ("reason", "copy"),
    [
        ("no_rows", "No rows match"),
        ("no_comparable_actual", "no comparable realised actual"),
        ("no_paired_coverage", "none has paired positive EAD coverage"),
    ],
)
def test_applied_empty_metric_collapses_to_one_house_empty_card(reason, copy):
    section = layout._build_metric_section(
        "bt-test", "9.9", "Test metric", "Description",
        view={"empty_reason": reason}, theme_value="light",
    )
    nodes = list(_walk(section))
    tokens = _class_tokens(nodes)
    assert "pd-mev-empty-state" in tokens
    assert "chart-box" not in tokens
    assert copy in _text(nodes)


def test_applied_scope_renders_charts_in_every_metric_section():
    applied = {
        "region": "all", "portfolio": "all", "model_group": "all",
        "segment": "all", "model": "all", "run_for": "all",
        "scenario": "Base", "jn_flag": "all", "snapshot": "all",
    }
    nodes = list(_walk_all(layout.build_page_content(applied, "light")))
    tokens = _class_tokens(nodes)
    assert "chart-box" in tokens
    assert "bt-chart-card" in tokens
    assert "bt-summary-strip" in tokens

    graphs = [node for node in nodes if type(node).__name__ == "Graph"]
    # Two loss-curve charts on the overview + three per metric section.
    assert len(graphs) == 17
    assert all(graph.figure is not None for graph in graphs)


def test_applied_scope_renders_for_the_dark_theme_too():
    applied = {"segment": "all", "model": "all", "scenario": "Base"}
    assert layout.build_page_content(applied, "dark")


def test_new_components_are_bt_prefixed(nodes):
    """Any class that is neither a platform class nor a pd-/saas- reuse must be
    bt- prefixed, so new CSS is confined to assets/backtesting.css."""
    known_prefixes = (
        "bt-", "pd-", "saas-", "monitoring-", "dashboard-loading-",
        "single-select", "checkbox-dropdown", "nav-", "app-",
    )
    generic = {
        "top-bar", "content", "tab-panel", "active", "section-card", "section-title",
        "chart-box", "btn", "btn-primary", "page-shell", "main",
        # Shared state class emitted by the single-select option markup.
        "is-selected",
    }
    for token in _class_tokens(nodes):
        if token in generic or token.startswith(known_prefixes):
            continue
        raise AssertionError(f"unexpected class {token!r}: new components need a bt- prefix")


def test_element_ids_are_bt_prefixed(nodes):
    for node_id in _ids(nodes):
        assert node_id.startswith(("bt-", "tab-backtesting")), node_id


# ---------------------------------------------------------------------------
# Filter options come from the data
# ---------------------------------------------------------------------------


def test_filter_options_are_derived_from_the_workbook():
    # O&M is absent by design: no PD model in the catalogue covers it.
    assert [option["value"] for option in layout.segment_options()][1:] == [
        "Cyclical", "Defensive",
    ]
    assert set(option["value"] for option in layout.run_for_options()) >= {
        "CCAR 2025", "CCAR 2026",
    }
    assert set(option["value"] for option in layout.jn_flag_options()) >= {"J", "N"}


def test_model_options_span_both_disjoint_pd_populations():
    values = [option["value"] for option in layout.model_options()]
    assert "PD_model_a" in values and "PD_model_b" in values


def test_models_are_labelled_by_descriptive_name_from_the_catalogue():
    """The value stays the raw key so it matches the workbook; only the label
    changes."""
    options = {option["value"]: option["label"] for option in layout.model_options()}
    assert options["PD_model_a"] == "PD Model A"
    assert options["PD_model_b"] == "PD Model B"


def test_attribute_options_come_from_the_model_catalogue():
    assert [option["value"] for option in layout.region_options()][1:] == ["US"]
    assert [option["value"] for option in layout.model_group_options()][1:] == ["PD"]


def test_a_model_with_no_portfolio_shows_as_unassigned_and_sorts_last():
    """PD_model_b has no Portfolio in model_names. The gap must stay visible and
    the model must stay reachable."""
    values = [option["value"] for option in layout.portfolio_options()][1:]
    assert config.BACKTESTING_UNASSIGNED_LABEL in values
    assert values[-1] == config.BACKTESTING_UNASSIGNED_LABEL

    from STATpy_platform.features.backtesting.domain import selectors
    assert selectors.models_matching(portfolio="non-C&I") == ["PD_model_a"]
    assert selectors.models_matching(
        portfolio=config.BACKTESTING_UNASSIGNED_LABEL
    ) == ["PD_model_b"]


def test_cascade_follows_the_model_catalogue_not_the_results_workbook():
    """model_names is authoritative for scope: PD_model_a serves Cyclical only,
    PD_model_b serves Cyclical and Defensive."""
    assert [o["value"] for o in layout.segment_options_for_model("PD_model_a")][1:] == ["Cyclical"]
    assert [o["value"] for o in layout.segment_options_for_model("PD_model_b")][1:] == [
        "Cyclical", "Defensive",
    ]
    assert [o["value"] for o in layout.model_options_for_segment("Defensive")][1:] == ["PD_model_b"]


def test_scenario_defaults_to_base():
    # A backtest scores the base scenario; the others are conservative by design.
    assert layout.scenario_options()[0]["value"] == config.BACKTESTING_BASE_SCENARIO
    assert layout.DEFAULT_SCENARIO == config.BACKTESTING_BASE_SCENARIO


def test_snapshot_options_are_quarter_labelled_newest_first():
    options = layout.snapshot_options()
    assert options[0]["value"] == layout.ALL_VALUE
    assert options[1]["label"] == "2025Q1"      # compact YYYYQn, newest first
    assert options[-1]["label"] == "2023Q1"


# ---------------------------------------------------------------------------
# Callback wiring
# ---------------------------------------------------------------------------


class _StubApp:
    """Captures decorated callbacks instead of registering them with Dash."""

    def __init__(self):
        self.callbacks = []

    def callback(self, *args, **kwargs):
        def decorator(func):
            self.callbacks.append({"args": args, "kwargs": kwargs, "func": func})
            return func

        return decorator


@pytest.fixture
def registered(monkeypatch):
    monkeypatch.setattr(callbacks, "already_registered", lambda app, key: False)
    monkeypatch.setattr(
        "STATpy_platform.features.monitoring.ui.common.controls",
        __import__(
            "STATpy_platform.shared.ui.controls", fromlist=["controls"]
        ),
        raising=False,
    )
    app = _StubApp()
    callbacks.register_callbacks(app)
    return app


def _outputs(entry):
    return [arg for arg in entry["args"] if isinstance(arg, Output)]


def _inputs(entry):
    return [arg for arg in entry["args"] if isinstance(arg, Input)]


def _states(entry):
    return [arg for arg in entry["args"] if isinstance(arg, State)]


def test_register_callbacks_is_idempotent():
    app = _StubApp()
    callbacks.register_callbacks(app)
    first = len(app.callbacks)
    callbacks.register_callbacks(app)
    assert len(app.callbacks) == first


def test_all_filter_shells_and_page_callbacks_are_registered(registered):
    names = {entry["func"].__name__ for entry in registered.callbacks}
    # Six shells x three callbacks each, plus the page's own four.
    assert "toggle_single_select_menu" in names
    assert "select_single_select_option" in names
    assert "sync_single_select_shell" in names
    assert "cascade_scope_filters" in names
    assert "apply_backtesting_filters" in names
    assert "render_backtesting_content" in names


def _cascade(registered, name):
    return next(entry for entry in registered.callbacks if entry["func"].__name__ == name)


def test_cascade_triggers_on_option_buttons_not_on_a_filter_value(registered):
    """Callback rule 2: reading a sibling filter's ``value`` as an ``Input``
    would close the Model<->Segment loop and produce a dependency cycle."""
    entry = _cascade(registered, "cascade_scope_filters")
    inputs = _inputs(entry)
    assert len(inputs) == 1
    component_id = inputs[0].component_id
    assert isinstance(component_id, dict)
    assert component_id["filter"] is ALL and component_id["value"] is ALL
    assert inputs[0].component_property == "n_clicks"


def test_cascade_reads_current_selections_as_state(registered):
    entry = _cascade(registered, "cascade_scope_filters")
    assert [state.component_id for state in _states(entry)] == [
        layout.REGION_ID, layout.PORTFOLIO_ID, layout.MODEL_GROUP_ID,
        layout.MODEL_ID, layout.SEGMENT_ID,
    ]
    assert all(state.component_property == "value" for state in _states(entry))


def test_cascade_only_takes_inputs_from_inside_the_menus(registered):
    """Callback rule 3: mixing an Input from a callback-rendered container with
    one from outside means the body silently never runs."""
    inputs = _inputs(_cascade(registered, "cascade_scope_filters"))
    assert all(isinstance(input_.component_id, dict) for input_ in inputs)


def test_cascade_prevents_initial_call_and_allows_duplicate_values(registered):
    entry = _cascade(registered, "cascade_scope_filters")
    assert entry["kwargs"].get("prevent_initial_call") is True
    value_outputs = [o for o in _outputs(entry) if o.component_property == "value"]
    assert value_outputs and all(o.allow_duplicate for o in value_outputs)


def test_cascade_ignores_the_remount_fire_with_zero_clicks(registered):
    """Option buttons are re-created whenever a menu is rebuilt, and the remount
    fires the pattern Input with every n_clicks still 0."""
    from dash import no_update
    entry = _cascade(registered, "cascade_scope_filters")
    assert entry["func"]([0, 0, 0], "all", "all", "all", "all", "all") == (no_update,) * 8
    assert entry["func"]([], "all", "all", "all", "all", "all") == (no_update,) * 8


def _fire(monkeypatch, entry, filter_key, picked, **state):
    class _Ctx:
        triggered_id = {"type": "x", "filter": filter_key, "value": picked}

    monkeypatch.setattr(callbacks, "ctx", _Ctx)
    return entry["func"](
        [1],
        state.get("region", layout.ALL_VALUE),
        state.get("portfolio", layout.ALL_VALUE),
        state.get("model_group", layout.ALL_VALUE),
        state.get("model", layout.ALL_VALUE),
        state.get("segment", layout.ALL_VALUE),
    )


def test_cascade_narrows_models_when_a_segment_is_picked(monkeypatch, registered):
    """Rule 2 trap 1: the picked value must come from ``ctx.triggered_id`` --
    ``State`` still holds the previous value in the same round trip."""
    entry = _cascade(registered, "cascade_scope_filters")
    result = _fire(monkeypatch, entry, layout.SEGMENT_FILTER_KEY, "Defensive")
    model_options = result[4]
    assert [option["value"] for option in model_options][1:] == ["PD_model_b"]


def test_cascade_narrows_segments_when_a_model_is_picked(monkeypatch, registered):
    entry = _cascade(registered, "cascade_scope_filters")
    result = _fire(monkeypatch, entry, layout.MODEL_FILTER_KEY, "PD_model_a")
    segment_options = result[6]
    assert [option["value"] for option in segment_options][1:] == ["Cyclical"]


def test_cascade_clears_a_selection_the_narrowing_invalidates(monkeypatch, registered):
    entry = _cascade(registered, "cascade_scope_filters")
    result = _fire(
        monkeypatch, entry, layout.SEGMENT_FILTER_KEY, "Defensive", model="PD_model_a"
    )
    assert result[5] == layout.ALL_VALUE      # PD_model_a does not serve Defensive


def test_cascade_never_rewrites_the_filter_that_was_clicked(monkeypatch, registered):
    """select_single_select_option owns that value for this round trip."""
    from dash import no_update
    entry = _cascade(registered, "cascade_scope_filters")
    result = _fire(monkeypatch, entry, layout.SEGMENT_FILTER_KEY, "Defensive")
    assert result[6] is no_update and result[7] is no_update


def test_cascade_ignores_filters_that_do_not_reshape_scope(monkeypatch, registered):
    from dash import no_update
    entry = _cascade(registered, "cascade_scope_filters")
    result = _fire(monkeypatch, entry, layout.SCENARIO_FILTER_KEY, "Severe")
    assert result == (no_update,) * 8


def test_apply_snapshots_every_filter_into_the_store(registered):
    entry = _cascade(registered, "apply_backtesting_filters")
    assert _inputs(entry)[0].component_id == layout.APPLY_FILTERS_ID
    assert [state.component_id for state in _states(entry)] == [
        layout.REGION_ID, layout.PORTFOLIO_ID, layout.MODEL_GROUP_ID,
        layout.SEGMENT_ID, layout.MODEL_ID, layout.RUN_FOR_ID,
        layout.SCENARIO_ID, layout.JN_FLAG_ID, layout.SNAPSHOT_ID,
    ]

    applied, help_text = entry["func"](
        1, "US", "non-C&I", "PD", "Cyclical", "PD_model_a", "CCAR 2025", "Base", "N", "all",
    )
    assert applied == {
        "region": "US", "portfolio": "non-C&I", "model_group": "PD",
        "segment": "Cyclical", "model": "PD_model_a", "run_for": "CCAR 2025",
        "scenario": "Base", "jn_flag": "N", "snapshot": "all",
    }
    # The help line reads the model's descriptive name, not its raw key.
    assert "Cyclical" in help_text and "PD Model A" in help_text


def test_render_reacts_to_the_app_theme_toggle(registered):
    """The page must follow the app theme the way the SAAS workspace does."""
    entry = _cascade(registered, "render_backtesting_content")
    input_ids = [input_.component_id for input_ in _inputs(entry)]
    assert layout.APPLIED_FILTERS_STORE_ID in input_ids
    assert theme.APP_THEME_ID in input_ids

    assert entry["func"](None, "dark")
    assert entry["func"]({"segment": "Cyclical"}, "light")


# ---------------------------------------------------------------------------
# Registry wiring
# ---------------------------------------------------------------------------


def test_dashboard_definition_is_wired():
    assert dashboard.DASHBOARD.key == "backtesting"
    assert dashboard.DASHBOARD.base_path == "/backtesting"
    assert dashboard.DASHBOARD.pages == page_registry.PAGES
    assert dashboard.DASHBOARD.build_stores() == []


def test_page_definition_is_callable():
    page = page_registry.PAGES[0]
    assert page.path == "/backtesting"
    assert callable(page.build_layout)
    assert callable(page.register_callbacks)


def test_dashboard_register_callbacks_is_idempotent():
    app = _StubApp()
    dashboard.register_callbacks(app)
    first = len(app.callbacks)
    dashboard.register_callbacks(app)
    assert len(app.callbacks) == first
