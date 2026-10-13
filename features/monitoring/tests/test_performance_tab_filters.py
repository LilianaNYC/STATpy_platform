"""The split Model Use Case / Reporting Cycle filters on PD, LGD, EAD and Loss.

Each tab carries its own near-identical copy of the bar (PD's comes from the
shared ``controls.build_global_filters``), so these tests run the same
expectations across all four rather than trusting the copies stayed in step.
"""

from __future__ import annotations

import pytest
from dash.development.base_component import Component

from STATpy_platform.features.monitoring.ui.views import (
    ead_performance as ead_layout,
    lgd_performance as lgd_layout,
    loss_performance as loss_layout,
)
from STATpy_platform.shared.ui import controls as pd_layout
from STATpy_platform.shared.ui.controls import SELECT_PROMPTS, UNSELECTED

# (label, module, element-id prefix). PD's controls live in the shared module.
TABS = [
    ("PD", pd_layout, "pd"),
    ("LGD", lgd_layout, "lgd"),
    ("EAD", ead_layout, "ead"),
    ("Loss", loss_layout, "loss"),
]


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


def _nodes(module):
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA

    if module is pd_layout:
        roots = [module.build_global_filters(PD_PERFORMANCE_DATA)]
    elif hasattr(module, "build_layout"):
        roots = module.build_layout()
    else:
        # EAD exposes page_layout instead of build_layout.
        roots = module.page_layout()
    out = []
    for root in roots:
        if isinstance(root, Component):
            out.extend(_walk(root))
    return out


def _texts(nodes):
    return " ".join(n for n in nodes if isinstance(n, str))


def _by_id(nodes, element_id):
    return next((n for n in nodes if getattr(n, "id", None) == element_id), None)


def _real(options):
    """Options with the leading "Select …" placeholder (value "") dropped."""
    return [o for o in options if o["value"] != UNSELECTED]


def _monitoring_point(module, prefix):
    """PD names the control ``pd-monitoring-point``; the other tabs append
    ``-dropdown``."""
    nodes = _nodes(module)
    # NB: `a or b` is wrong here -- a Dash component with no children is falsy
    # (__len__ counts children), so a found Dropdown would be discarded.
    control = _by_id(nodes, f"{prefix}-monitoring-point")
    if control is None:
        control = _by_id(nodes, f"{prefix}-monitoring-point-dropdown")
    assert control is not None, f"{prefix}: monitoring point control not found"
    return control


@pytest.mark.parametrize("name,module,prefix", TABS)
def test_bar_has_both_filters_and_not_the_combined_one(name, module, prefix):
    nodes = _nodes(module)
    text = _texts(nodes)
    assert "Model Use Case / Cycle" not in text, name
    assert "Model Use Case" in text, name
    assert "Reporting Cycle" in text, name
    assert _by_id(nodes, f"{prefix}-model-use-case") is not None, name
    assert _by_id(nodes, f"{prefix}-reporting-cycle") is not None, name


@pytest.mark.parametrize("name,module,prefix", TABS)
def test_cycle_values_stay_composite_while_labels_are_bare(name, module, prefix):
    """The value is the join key behind every store, figure and export; only the
    label comes from the workbook's Reporting Cycle column."""
    cycle = _by_id(_nodes(module), f"{prefix}-reporting-cycle")
    for option in _real(cycle.options):
        assert " " in option["value"], f"{name}: {option['value']!r} is not a composite"
        assert option["label"] == option["value"].split(" ", 1)[1], name


@pytest.mark.parametrize("name,module,prefix", TABS)
def test_use_case_offers_only_real_programmes(name, module, prefix):
    use_case = _by_id(_nodes(module), f"{prefix}-model-use-case")
    values = {o["value"] for o in _real(use_case.options)}
    assert values <= {"CCAR", "CECL"}, name
    assert "All" not in values, name
    # The page opens unanswered -- the value is the placeholder, not a programme.
    assert use_case.value == UNSELECTED, name


@pytest.mark.parametrize("name,module,prefix", TABS)
def test_monitoring_point_is_listed_most_recent_first(name, module, prefix):
    """Same direction as Reporting Cycle above it."""
    point = _monitoring_point(module, prefix)
    labels = [o["label"] for o in _real(point.options)]
    assert labels == sorted(labels, reverse=True), name


@pytest.mark.parametrize("name,module,prefix", TABS)
def test_monitoring_point_opens_unanswered(name, module, prefix):
    """It used to default to the latest quarter. The page now opens with nothing
    selected, so it must not answer itself -- not even with the newest value."""
    point = _monitoring_point(module, prefix)
    assert point.value == UNSELECTED, name
    assert point.options[0]["label"] == SELECT_PROMPTS["monitoring-point"], name


@pytest.mark.parametrize("name,module,prefix", [t for t in TABS if t[0] != "Loss"])
def test_region_and_portfolio_have_no_all_option(name, module, prefix):
    """Loss is excluded on purpose: its only entity is the portfolio-wide
    "All Models", which carries no region/portfolio, so those two stay fixed
    placeholders rather than becoming empty dropdowns."""
    nodes = _nodes(module)
    for field in ("region", "portfolio"):
        control = _by_id(nodes, f"{prefix}-{field}")
        values = {o["value"] for o in _real(control.options)}
        assert "All" not in values, f"{name} {field}"
        # Opens unanswered -- see test_every_filter_opens_unanswered below.
        assert control.value == UNSELECTED, f"{name} {field} default"


def test_loss_keeps_its_region_portfolio_placeholders():
    """Documents the deliberate exception above."""
    nodes = _nodes(loss_layout)
    for field in ("region", "portfolio"):
        control = _by_id(nodes, f"loss-{field}")
        assert [o["value"] for o in control.options] == ["All"]


# --- cascade direction ----------------------------------------------------

# Filter order in the bar. Each tab spells some ids differently (PD's controls
# live in the shared module), so both spellings map to the same position.
_FILTER_RANK = {
    "REGION_ID": 0, "PORTFOLIO_ID": 1, "MODEL_USE_CASE_ID": 2, "REPORTING_CYCLE_ID": 3,
    "MODELS_ID": 4, "MODEL_DROPDOWN_ID": 4,
    "PORTFOLIO_SEGMENT_ID": 5, "SEGMENT_DROPDOWN_ID": 5,
    "MONITORING_POINT_ID": 6, "MONITORING_POINT_DROPDOWN_ID": 6,
    "SCENARIO_ID": 7,
}

# (module holding register_callbacks, the namespace its decorators use)
_CALLBACK_MODULES = [
    ("pd", "controls"), ("lgd", "layout"), ("ead", "layout"), ("loss", "layout"),
]


@pytest.mark.parametrize("tab,namespace", _CALLBACK_MODULES)
def test_cascade_only_flows_left_to_right(tab, namespace):
    """No callback may write a filter that sits left of one of its own inputs.

    That is the property keeping the cascade acyclic. Reordering the bar put
    Reporting Cycle ahead of Model/Segment, which required inverting the old
    population-to-cycle narrowing -- keeping both directions would have closed
    exactly the loop callback rule 2 forbids.
    """
    import importlib
    import inspect
    import re

    module = importlib.import_module(
        f"STATpy_platform.features.monitoring.callbacks.{tab}_performance"
    )
    source = inspect.getsource(module.register_callbacks)

    violations = []
    for block in source.split("@app.callback")[1:]:
        decorator, _, rest = block.partition("def ")
        name = rest.split("(", 1)[0] if rest else "?"
        outs = [_FILTER_RANK[m] for m in re.findall(rf"Output\({namespace}\.(\w+)", decorator)
                if m in _FILTER_RANK]
        ins = [_FILTER_RANK[m] for m in re.findall(rf"Input\({namespace}\.(\w+)", decorator)
               if m in _FILTER_RANK]
        if outs and ins and min(outs) <= max(ins):
            violations.append(f"{name}: writes position {min(outs)} while reading up to {max(ins)}")

    assert not violations, f"{tab} cascade flows backwards: " + "; ".join(violations)


@pytest.mark.parametrize("name,module,prefix", TABS)
def test_bar_reads_in_the_agreed_order(name, module, prefix):
    """Region | Portfolio | Model Use Case | Reporting Cycle || Model | Segment
    | Monitoring Point | Scenario.

    No Model Group: each of these tabs shows exactly one group, so the control
    could only ever return its own name. Overview keeps its Model Group, where
    it is a real choice -- see test_overview_use_case_filter.py.
    """
    expected = ["Region", "Portfolio", "Model Use Case", "Reporting Cycle",
                "Model", "Segment", "Monitoring Point", "Scenario"]
    if prefix == "loss":
        # Loss has no Scenario: it only ever drove the MEV Range section, which
        # Loss does not have. Its value was never even written into the applied
        # store, so the filter was a required click that changed nothing.
        expected = [label for label in expected if label != "Scenario"]
    labels = []
    for node in _nodes(module):
        if type(node).__name__ == "Label":
            text = node.children
            if isinstance(text, str) and text in expected and text not in labels:
                labels.append(text)
    assert labels == expected, f"{name}: {labels}"


# --- row captions ---------------------------------------------------------

# (row class, expected caption). The bar reads as two labelled rows: row 1 is
# the Scope -- what population the page covers -- and row 2 the Focus: which
# model/segment/point within it is on screen.
_ROW_CAPTIONS = [
    ("monitoring-primary-filter-row", "Scope"),
    ("saas-secondary-filter-row", "Focus"),
]


def _row(nodes, row_class):
    return next(
        (n for n in nodes
         if row_class in (getattr(n, "className", None) or "").split()),
        None,
    )


@pytest.mark.parametrize("row_class,caption", _ROW_CAPTIONS)
@pytest.mark.parametrize("name,module,prefix", TABS)
def test_each_filter_row_leads_with_its_caption(name, module, prefix, row_class, caption):
    row = _row(_nodes(module), row_class)
    assert row is not None, f"{name}: no .{row_class}"
    first = row.children[0]
    assert getattr(first, "className", None) == "monitoring-filter-row-caption", (
        f"{name}: {row_class} does not lead with a caption cell"
    )
    assert first.children == caption, f"{name}: {row_class} caption is {first.children!r}"


@pytest.mark.parametrize("name,module,prefix", TABS)
def test_the_caption_is_not_a_filter_cell(name, module, prefix):
    """``styles.css`` draws the cascade chevron before every ``.monitoring-filter``
    that follows another one. If the caption carried that class it would sit an
    arrow between itself and the first filter, and claim a filter-width track."""
    for row_class, _caption in _ROW_CAPTIONS:
        row = _row(_nodes(module), row_class)
        classes = (getattr(row.children[0], "className", None) or "").split()
        assert "monitoring-filter" not in classes, f"{name}: {row_class}"


@pytest.mark.parametrize("name,module,prefix", TABS)
def test_these_tabs_have_no_model_group_filter(name, module, prefix):
    """Each shows exactly one group, so the control could only ever return its
    own name. Its value drove nothing -- the group is hardcoded at every
    ``models_matching`` call site -- and once the bar started empty it became a
    required click with a foregone answer."""
    nodes = _nodes(module)
    assert _by_id(nodes, f"{prefix}-model-group") is None, name
    labels = [n.children for n in nodes
              if type(n).__name__ == "Label" and isinstance(n.children, str)]
    assert "Model Group" not in labels, name


def test_overview_keeps_its_model_group():
    """The removal above is specific to the single-group tabs. Overview's Model
    Group picks between PD/LGD/EAD/Loss, so it stays."""
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA
    from STATpy_platform.features.monitoring.ui.views import overview as overview_layout

    nodes = []
    for root in overview_layout.page_layout(PD_PERFORMANCE_DATA):
        if isinstance(root, Component):
            nodes.extend(_walk(root))
    control = _by_id(nodes, overview_layout.SEGMENT_MODEL_GROUP_ID)
    assert control is not None
    assert len([o for o in control.options if o["value"] != UNSELECTED]) > 1


def test_loss_has_no_scenario_filter():
    """Scenario only ever drove the MEV Range section, and Loss has none.

    Its value was never written into Loss's applied store, so answering it
    changed nothing on screen -- while still being one of the filters that had
    to be answered before Apply would enable. The other three tabs keep theirs
    until the control moves into the MEV Range section itself.
    """
    nodes = _nodes(loss_layout)
    assert _by_id(nodes, "loss-scenario") is None
    labels = [n.children for n in nodes
              if type(n).__name__ == "Label" and isinstance(n.children, str)]
    assert "Scenario" not in labels

    for name, module, prefix in TABS:
        if prefix == "loss":
            continue
        assert _by_id(_nodes(module), f"{prefix}-scenario") is not None, name


def test_no_loss_deep_link_carries_a_scenario():
    """Why removing it is free rather than a trade-off.

    Overview's escalation cards are the only producer of ``?scenario=``, and
    only for rows that carry a "MEV Range Scenario" -- which
    augment_rows_with_post_subjective writes for PD, LGD and EAD only. A Loss
    card therefore never emitted one, so no existing link breaks.
    """
    import inspect
    from STATpy_platform.features.monitoring.ui.views import overview as overview_layout

    source = inspect.getsource(overview_layout.augment_rows_with_post_subjective)
    for group in ("PD", "LGD", "EAD"):
        assert f'"{group}"' in source, group
    assert '"Loss"' not in source, "Loss gained a post-subjective sidecar -- revisit this"
