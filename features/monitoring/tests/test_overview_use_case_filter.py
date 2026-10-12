"""Overview's split Model Use Case / Reporting Cycle filters.

The single "Model Use Case / Cycle" control is now two: Model Use Case (fed by
the workbook's ``Model Use Case`` column) and Reporting Cycle (labelled from the
``Reporting Cycle`` column). The cycle option *values* stay the composite
("CCAR 2026") because that is the join key behind every store, figure and
export -- these tests pin that split so a future change cannot quietly turn the
value into the bare cycle and strand the downstream lookups.
"""

from __future__ import annotations

from dash.development.base_component import Component

from STATpy_platform.features.monitoring.ui.views import overview as layout
from STATpy_platform.shared.ui.controls import SELECT_PROMPTS, UNSELECTED
from STATpy_platform.shared.repositories.filters_config import (
    default_use_case,
    model_use_case_options,
    reporting_cycle_options,
    use_case_of,
)


# --- option derivation ----------------------------------------------------

def test_use_case_options_are_listed_alphabetically():
    options = model_use_case_options()
    assert [o["value"] for o in options] == ["CECL", "ST - CCAR"]


def test_the_default_use_case_still_owns_the_most_recent_cycle():
    """Order and default are separate concerns. Listing A-Z puts CECL first, so
    taking the default from position would silently move every tab's landing
    page off the current CCAR cycle -- ``default_use_case`` is what stops that."""
    options = model_use_case_options()
    chosen = default_use_case(options)
    assert chosen == "ST - CCAR"
    assert chosen != options[0]["value"], "the guard is vacuous if A-Z already picks it"
    assert reporting_cycle_options(chosen)[0]["value"] == "CCAR 2026"


def test_default_use_case_falls_back_when_its_cycle_is_out_of_scope():
    """A population with only CECL data must not be handed a CCAR default."""
    assert default_use_case([{"label": "CECL", "value": "CECL"}]) == "CECL"
    assert default_use_case([]) == ""


def test_cycle_options_label_bare_but_value_composite():
    options = reporting_cycle_options("ST - CCAR")
    assert [o["label"] for o in options] == ["2026", "2025", "2024"]
    assert [o["value"] for o in options] == ["CCAR 2026", "CCAR 2025", "CCAR 2024"]


def test_cycle_options_are_scoped_to_the_use_case():
    """A use case only ever offers cycles it has data for -- the two filters can
    never show a combination with no rows behind it."""
    assert [o["label"] for o in reporting_cycle_options("CECL")] == ["2025Q1"]
    assert [o["value"] for o in reporting_cycle_options("CECL")] == ["CECL 2025Q1"]


def test_unscoped_cycle_options_cover_every_use_case():
    values = {o["value"] for o in reporting_cycle_options()}
    assert values == {"CCAR 2026", "CCAR 2025", "CCAR 2024", "CECL 2025Q1"}


def test_use_case_of_maps_composite_back_to_its_programme():
    assert use_case_of("CCAR 2026") == "ST - CCAR"
    assert use_case_of("CECL 2025Q1") == "CECL"
    assert use_case_of("nonsense") == ""


# --- the filter bar -------------------------------------------------------

def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    for child in (children if isinstance(children, (list, tuple)) else [children]):
        if isinstance(child, Component):
            yield from _walk(child)
        else:
            yield child


def _layout_nodes():
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA
    nodes = []
    for root in layout.page_layout(PD_PERFORMANCE_DATA):
        if isinstance(root, Component):
            nodes.extend(_walk(root))
    return nodes


def _ids(nodes):
    return {getattr(n, "id", None) for n in nodes if isinstance(getattr(n, "id", None), str)}


def _real(options):
    """Option values with the "Select …" placeholder (value "") dropped."""
    return [o["value"] for o in options if o["value"] != UNSELECTED]


def test_layout_builds_with_both_filters_present():
    nodes = _layout_nodes()
    ids = _ids(nodes)
    assert layout.MODEL_USE_CASE_ID in ids
    assert layout.REPORTING_CYCLE_ID in ids


def test_bar_labels_are_split_and_the_combined_label_is_gone():
    texts = [n for n in _layout_nodes() if isinstance(n, str)]
    joined = " ".join(texts)
    assert "Model Use Case / Cycle" not in joined
    assert "Model Use Case" in joined
    assert "Reporting Cycle" in joined


def test_cycle_dropdown_opens_unnarrowed_because_nothing_is_selected_yet():
    """The page opens with Region/Portfolio/Use Case unanswered, so there is
    nothing to narrow by and the cycle control offers every cycle with data.
    The cascade re-narrows it as soon as a predecessor is answered -- that
    direction is covered by ``test_use_case_narrows_the_cycle_options``."""
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA
    from STATpy_platform.features.monitoring.domain.overview import overview_cycle_options

    nodes = _layout_nodes()
    def _control(element_id):
        return next(n for n in nodes if getattr(n, "id", None) == element_id)

    for element_id in (layout.REGION_ID, layout.PORTFOLIO_ID, layout.MODEL_USE_CASE_ID):
        assert _control(element_id).value == UNSELECTED, element_id

    cycle = _control(layout.REPORTING_CYCLE_ID)
    expected = overview_cycle_options(PD_PERFORMANCE_DATA)
    assert set(_real(cycle.options)) == {o["value"] for o in expected}
    assert cycle.value == UNSELECTED


# --- the narrowing callback ----------------------------------------------

class _StubApp:
    """Captures decorated callbacks instead of registering them with Dash."""

    def __init__(self):
        self.callbacks = {}

    def callback(self, *_args, **_kwargs):
        def decorator(func):
            self.callbacks[func.__name__] = func
            return func
        return decorator


def _captured_callbacks(monkeypatch):
    from STATpy_platform.features.monitoring.callbacks import overview as callbacks
    monkeypatch.setattr(callbacks, "already_registered", lambda *_a, **_k: False)
    app = _StubApp()
    callbacks.register_callbacks(app)
    return app.callbacks


def test_use_case_narrows_the_cycle_options(monkeypatch):
    sync = _captured_callbacks(monkeypatch)["sync_overview_cycle_options"]

    options, value = sync("HBUS", "C&I", "CECL", "CCAR 2026")
    assert _real(options) == ["CECL 2025Q1"]
    # A stale CCAR selection cannot survive a use case that lacks it -- and the
    # filter is left unanswered rather than silently moved to the first cycle.
    assert value == UNSELECTED

    options, value = sync("HBUS", "C&I", "ST - CCAR", "CCAR 2025")
    assert [o["label"] for o in options if o["value"] != UNSELECTED] == ["2026", "2025"]
    # a still-valid selection is preserved rather than reset to the first option
    assert value == "CCAR 2025"


def test_cycles_offered_depend_on_the_region_portfolio_scope(monkeypatch):
    """2024 exists only for LGD Model A (US / non-C&I), so it must not be
    offered under a scope that excludes that model."""
    sync = _captured_callbacks(monkeypatch)["sync_overview_cycle_options"]

    non_ci, _v = sync("HBUS", "non-C&I", "ST - CCAR", UNSELECTED)
    ci, _v = sync("HBUS", "C&I", "ST - CCAR", UNSELECTED)
    assert "2024" in [o["label"] for o in non_ci]
    assert "2024" not in [o["label"] for o in ci]


def test_portfolio_and_use_case_offer_only_available_values(monkeypatch):
    cbs = _captured_callbacks(monkeypatch)
    portfolios, value = cbs["sync_overview_portfolio_options"]("HBUS", None)
    assert set(_real(portfolios)) == {"C&I", "non-C&I"}
    # Nothing valid selected -> stays unanswered. It must NOT take the first
    # available value: this callback runs on the first render, so doing so
    # would fill the bar in before the user has touched it.
    assert value == UNSELECTED

    use_cases, _v = cbs["sync_overview_use_case_options"]("HBUS", "C&I", "ST - CCAR")
    assert set(_real(use_cases)) <= {"ST - CCAR", "CECL"}


def test_none_of_the_scope_filters_offer_an_all_option(monkeypatch):
    """These four are always a concrete slice -- an "All" would reintroduce the
    combination-with-no-data problem the narrowing exists to prevent."""
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA
    from STATpy_platform.features.monitoring.domain import overview as domain

    assert "All" not in {o["value"] for o in domain.overview_region_options(PD_PERFORMANCE_DATA)}
    assert "All" not in {o["value"] for o in domain.overview_portfolio_options(PD_PERFORMANCE_DATA, "HBUS")}
    assert "All" not in {o["value"] for o in domain.overview_use_case_options(PD_PERFORMANCE_DATA, "HBUS", "C&I")}
    assert "All" not in {o["value"] for o in domain.overview_cycle_options(PD_PERFORMANCE_DATA, "HBUS", "C&I", "ST - CCAR")}


def test_model_options_narrow_by_region_portfolio_and_cycle(monkeypatch):
    """Region, Portfolio and Reporting Cycle all scope the Model list -- that is
    how those filters reach the charts, since the content is scoped by model."""
    sync = _captured_callbacks(monkeypatch)["sync_overview_model_options"]

    unfiltered, _value = sync("All", "All", "", "All", "", [])
    eu_only, _value = sync("EU", "All", "", "All", "", [])
    assert {o["value"] for o in eu_only} < {o["value"] for o in unfiltered}
    # Named models drift as the dummy data is trimmed, so assert the property:
    # EU must keep at least one model, and drop at least one HBUS-only model.
    assert eu_only, "EU narrowed the list to nothing"
    assert {o["value"] for o in unfiltered} - {o["value"] for o in eu_only}

    by_cycle, _value = sync("All", "All", "CCAR 2024", "All", "", [])
    assert [o["value"] for o in by_cycle] == ["LGD Model A"]


def test_narrowing_models_also_rewrites_the_selection(monkeypatch):
    """Narrowing the options is not enough -- the *value* has to follow, or the
    charts would still be scoped to models no longer offered."""
    sync = _captured_callbacks(monkeypatch)["sync_overview_model_options"]

    eu_models = [o["value"] for o in sync("EU", "All", "", "All", "", [])[0]]
    all_models = [o["value"] for o in sync("All", "All", "", "All", "", [])[0]]
    dropped = next(m for m in all_models if m not in eu_models)  # not an EU model
    kept = eu_models[0]

    _options, value = sync("EU", "All", "", "All", "", [dropped, kept])
    assert dropped not in value, f"{dropped} is not in EU and must leave the selection"
    assert kept in value


def test_loss_survives_a_region_filter(monkeypatch):
    """Loss's "All Models" carries no region/portfolio; excluding blanks would
    silently drop the whole Loss workstream whenever a region is picked."""
    sync = _captured_callbacks(monkeypatch)["sync_overview_model_options"]
    options, _value = sync("EU", "C&I", "", "All", "", [])
    assert "All Models" in {o["value"] for o in options}


def test_the_cascade_only_ever_flows_left_to_right():
    """The bar narrows left to right, and nothing may write a filter that sits
    left of one of its own inputs.

    That is the property which keeps the cascade acyclic: a callback reading a
    downstream filter and writing an upstream one closes the loop that callback
    rule 2 exists to prevent. Checked over the real decorators so a future edit
    cannot reintroduce one quietly.
    """
    import inspect
    import re
    from STATpy_platform.features.monitoring.callbacks import overview as callbacks

    order = [
        "REGION_ID", "PORTFOLIO_ID", "MODEL_USE_CASE_ID", "REPORTING_CYCLE_ID",
        "SEGMENT_MODEL_GROUP_ID", "OVERVIEW_MODEL_ID", "MONITORING_POINT_ID",
    ]
    rank = {name: index for index, name in enumerate(order)}
    source = inspect.getsource(callbacks.register_callbacks)

    violations = set()
    for block in source.split("@app.callback")[1:]:
        body = block.split("def ", 1)
        decorator, name = body[0], (body[1].split("(", 1)[0] if len(body) > 1 else "?")
        outputs = [rank[m] for m in re.findall(r"Output\(layout\.(\w+)", decorator) if m in rank]
        inputs = [rank[m] for m in re.findall(r"Input\(layout\.(\w+)", decorator) if m in rank]
        if outputs and inputs and min(outputs) <= max(inputs):
            violations.add(name)

    # sync_overview_model_select_all takes the Model value as an Input while also
    # writing it -- the mutually-syncing select-all that CLAUDE.md records as
    # known-unfixed (callback rule 4). It predates this bar and needs a
    # store-based redesign, so it is pinned here rather than hidden: any *other*
    # name appearing is a new backwards edge and a real regression.
    assert violations == {"sync_overview_model_select_all"}, (
        "cascade flows backwards -> dependency cycle risk: " + ", ".join(sorted(violations))
    )


# --- the in-content scope chip -------------------------------------------

def test_scope_chip_splits_the_cycle_like_the_filter_bar():
    """The chip mirrors the bar, so it must not keep showing the composite under
    the retired combined label."""
    note = layout._scope_cycle_note("CCAR 2026")
    assert note == "Model use case ST - CCAR · Reporting cycle 2026"
    assert layout._scope_cycle_note("CECL 2025Q1") == "Model use case CECL · Reporting cycle 2025Q1"


def test_scope_chip_degrades_visibly_for_unknown_or_missing_cycles():
    """An unrecognised composite still shows something rather than blanking."""
    assert layout._scope_cycle_note("MYSTERY 9999") == "Model use case / cycle MYSTERY 9999"
    assert layout._scope_cycle_note("") == "Model use case — · Reporting cycle —"


# --- region / portfolio in the applied scope ------------------------------

def test_scope_prefix_omits_unnarrowed_axes():
    """"All" adds nothing: spelling out every default would bury the axes the
    user actually narrowed."""
    assert layout._scope_prefix("All", "All") == ""
    assert layout._scope_prefix("EU", "All") == "Region EU"
    assert layout._scope_prefix("All", "C&I") == "Portfolio C&I"
    assert layout._scope_prefix("EU", "C&I") == "Region EU · Portfolio C&I"


def test_applied_snapshot_records_region_and_portfolio():
    from STATpy_platform.features.monitoring.callbacks.overview import _overview_filter_snapshot

    snapshot = _overview_filter_snapshot(
        "CCAR 2026", "2026Q3", "All", ["PD Model A"], region="EU", portfolio="C&I",
    )
    assert snapshot["region"] == "EU"
    assert snapshot["portfolio"] == "C&I"
    # unchanged keys still present, so existing readers keep working
    assert snapshot["reporting_cycle"] == "CCAR 2026"
    assert snapshot["models"] == ["PD Model A"]


def test_applied_snapshot_defaults_the_new_keys():
    """Callers that predate the two filters must still produce a usable snapshot."""
    from STATpy_platform.features.monitoring.callbacks.overview import _overview_filter_snapshot

    snapshot = _overview_filter_snapshot("CCAR 2026", "2026Q3", "All", [])
    assert snapshot["region"] == "All"
    assert snapshot["portfolio"] == "All"


# --- Apply button dirty state --------------------------------------------

_APPLIED = {
    "region": "All", "portfolio": "All", "reporting_cycle": "CCAR 2026",
    "monitoring_point": "2026Q3", "segment_model_group": "All", "models": ["A", "B"],
}


def test_apply_reads_dirty_before_anything_is_applied():
    """Nothing is rendered until the first Apply, so the button must invite it."""
    assert layout.apply_button_class(_APPLIED, None).endswith("is-dirty")


def test_apply_reads_clean_when_the_bar_matches_what_is_rendered():
    assert layout.apply_button_class(dict(_APPLIED), _APPLIED).endswith("is-clean")


def test_reordering_the_model_checkboxes_is_not_a_change():
    """Models compare as a set -- checkbox order is not a filter change, and
    flagging it would leave the button permanently dirty."""
    reordered = {**_APPLIED, "models": ["B", "A"]}
    assert layout.apply_button_class(reordered, _APPLIED).endswith("is-clean")


def test_every_scope_axis_marks_the_bar_dirty():
    for field, value in (
        ("region", "EU"), ("portfolio", "C&I"), ("reporting_cycle", "CCAR 2025"),
        ("monitoring_point", "2025Q4"), ("segment_model_group", "PD"), ("models", ["A"]),
    ):
        pending = {**_APPLIED, field: value}
        assert layout.apply_button_class(pending, _APPLIED).endswith("is-dirty"), field


def test_apply_state_callback_writes_only_the_buttons_own_props(monkeypatch):
    """It owns both the dirty-state class and the Apply gate, but writes nothing
    except the button's own props -- nothing reads those back, so it adds no
    edge to the filter cascade."""
    import inspect
    import re
    from STATpy_platform.features.monitoring.callbacks import overview as callbacks

    source = inspect.getsource(callbacks.register_callbacks)
    decorator = source[:source.index("def sync_overview_apply_state")].rsplit("@app.callback", 1)[-1]
    outputs = re.findall(r"Output\((\S+?), \"(\w+)\"\)", decorator)
    assert outputs == [("layout.APPLY_FILTERS_ID", "className"),
                       ("layout.APPLY_FILTERS_ID", "disabled")], outputs


# --- monitoring point ordering -------------------------------------------

def test_monitoring_point_is_listed_most_recent_first():
    """Reads in the same direction as Reporting Cycle above it."""
    nodes = _layout_nodes()
    point = next(n for n in nodes if getattr(n, "id", None) == layout.MONITORING_POINT_ID)
    labels = [o["label"] for o in point.options]
    assert labels == sorted(labels, reverse=True)


def test_monitoring_point_opens_unanswered():
    """It used to default to the latest quarter. The page now opens with nothing
    selected, so it must not answer itself -- not even with the newest value."""
    nodes = _layout_nodes()
    point = next(n for n in nodes if getattr(n, "id", None) == layout.MONITORING_POINT_ID)
    assert point.value == UNSELECTED
    assert point.options[0]["label"] == SELECT_PROMPTS["monitoring-point"]


def test_monitoring_point_callback_orders_but_never_answers_itself(monkeypatch):
    sync = _captured_callbacks(monkeypatch)["sync_overview_monitoring_point_dropdown"]
    options, value = sync("CCAR 2026", [], None)
    labels = [o["label"] for o in options if o["value"] != UNSELECTED]
    assert labels == sorted(labels, reverse=True)
    assert value == UNSELECTED
    # ... but a still-valid pick survives a re-narrowing.
    _options, kept = sync("CCAR 2026", [], labels[1])
    assert kept == labels[1]


# --- two-tier bar ---------------------------------------------------------

def test_bar_is_split_into_a_scope_row_and_a_focus_row():
    """Overview matches the performance tabs: scope filters on row 1, the
    population/point filters and Apply on row 2."""
    from dash.development.base_component import Component

    rows = {}
    for node in _layout_nodes():
        class_name = getattr(node, "className", "") or ""
        if "overview-primary-filter-row" in class_name:
            rows["scope"] = node
        elif "overview-secondary-filter-row" in class_name:
            rows.setdefault("focus", node)

    assert set(rows) == {"scope", "focus"}

    def labels_of(node):
        out = []
        stack = [node]
        while stack:
            current = stack.pop(0)
            children = getattr(current, "children", None)
            if children is None:
                continue
            for child in (children if isinstance(children, (list, tuple)) else [children]):
                if isinstance(child, Component):
                    if type(child).__name__ == "Label":
                        out.append(child.children)
                    stack.append(child)
        return [t for t in out if isinstance(t, str)]

    assert labels_of(rows["scope"]) == ["Region", "Portfolio", "Model Use Case", "Reporting Cycle"]
    focus = [t for t in labels_of(rows["focus"]) if t in ("Model Group", "Model", "Monitoring Point")]
    assert focus == ["Model Group", "Model", "Monitoring Point"]


def test_exactly_one_of_each_filter_row_is_rendered():
    """Guards against a stray empty container -- an earlier edit left a second,
    empty secondary row that rendered as a blank strip."""
    classes = [
        getattr(n, "className", "") or "" for n in _layout_nodes()
    ]
    assert sum("overview-primary-filter-row" in c for c in classes) == 1
    assert sum("overview-secondary-filter-row" in c for c in classes) == 1


def test_apply_button_lives_on_the_focus_row():
    from dash.development.base_component import Component

    focus = next(
        n for n in _layout_nodes()
        if "overview-secondary-filter-row" in (getattr(n, "className", "") or "")
    )
    ids = []
    stack = [focus]
    while stack:
        current = stack.pop(0)
        children = getattr(current, "children", None)
        if children is None:
            continue
        for child in (children if isinstance(children, (list, tuple)) else [children]):
            if isinstance(child, Component):
                ids.append(getattr(child, "id", None))
                stack.append(child)
    assert layout.APPLY_FILTERS_ID in ids


# Overview's rows carry their own classes but must read the same way as the
# performance tabs: a Scope row over a Focus row. See the matching test in
# ``test_performance_tab_filters.py``.
def test_overview_rows_lead_with_the_same_captions_as_the_other_tabs():
    nodes = _layout_nodes()
    for row_class, caption in (("overview-primary-filter-row", "Scope"),
                               ("overview-secondary-filter-row", "Focus")):
        row = next(
            (n for n in nodes
             if row_class in (getattr(n, "className", None) or "").split()),
            None,
        )
        assert row is not None, f"no .{row_class}"
        first = row.children[0]
        assert getattr(first, "className", None) == "monitoring-filter-row-caption", row_class
        assert first.children == caption, f"{row_class}: {first.children!r}"
        # Not a filter cell -- it would otherwise take a chevron and a full track.
        assert "monitoring-filter" not in (first.className or "").split()
