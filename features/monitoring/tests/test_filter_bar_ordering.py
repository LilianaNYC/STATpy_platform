"""Every filter in the bar follows the one ordering rule.

Text values A-Z; dates, quarters and numbers newest-first. Checked against the
**rendered** options of all five tabs rather than against each option builder,
because the builders are spread across the repositories, domain and callback
layers and only the rendered list is what a user actually reads.

Aggregate sentinels ("All", "Select model", "Select segment") are not values --
they are the absence of a choice -- so they are expected at the head of a list
and are stripped before the ordering is checked.
"""

from __future__ import annotations

import pytest
from dash.development.base_component import Component

from STATpy_platform.features.monitoring.ui.views import (
    ead_performance as ead_layout,
    lgd_performance as lgd_layout,
    loss_performance as loss_layout,
    overview as overview_layout,
)
from STATpy_platform.shared.domain.filter_order import alphabetical, newest_first
from STATpy_platform.shared.ui import controls as pd_layout

# Sentinels that head a list rather than sorting into it. Matched on **value**,
# not label: Loss labels its aggregate "All models" while its one real model is
# named "All Models", so a label match cannot tell the two apart.
SENTINEL_VALUES = {"", "all", "All"}

# Which filters hold periods (newest-first) rather than text (A-Z). Reporting
# Cycle is here because its *label* is the bare cycle -- its value stays the
# composite join key, which is why the check below reads labels, not values.
PERIOD_FILTERS = {"Reporting Cycle", "Monitoring Point"}


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    for child in (children if isinstance(children, (list, tuple)) else [children]):
        if isinstance(child, Component):
            yield from _walk(child)


def _bar(module):
    from STATpy_platform.features.monitoring.data_access import PD_PERFORMANCE_DATA

    if module is pd_layout:
        return [module.build_global_filters(PD_PERFORMANCE_DATA)]
    if module is overview_layout:
        return module.page_layout(PD_PERFORMANCE_DATA)
    if hasattr(module, "build_layout"):
        return module.build_layout()
    return module.page_layout()


def _labelled_filters(module):
    """``{label: [option labels]}`` for every filter cell in the bar.

    Both the label and the options are searched for across the cell's whole
    subtree, not just its direct children: ``build_single_select_dropdown``
    wraps the options-carrying component in a toggle/menu Div, so a
    direct-children-only scan silently finds nothing and every check below
    passes vacuously.
    """
    found: dict[str, list[str]] = {}
    for root in _bar(module):
        if not isinstance(root, Component):
            continue
        for node in _walk(root):
            classes = (getattr(node, "className", None) or "").split()
            if "monitoring-filter" not in classes:
                continue
            cell = list(_walk(node))
            label = next((n.children for n in cell
                          if type(n).__name__ == "Label" and isinstance(n.children, str)), None)
            if label is None or label in found:
                continue
            options = next((getattr(n, "options", None) for n in cell
                            if getattr(n, "options", None)), None)
            if options:
                found[label] = [
                    (o["label"], o["value"]) if isinstance(o, dict) else (str(o), str(o))
                    for o in options
                ]
    return found


def _values(pairs):
    """Option labels with the aggregate sentinels stripped."""
    return [label for label, value in pairs if value not in SENTINEL_VALUES]


def test_the_guard_actually_finds_the_filters():
    """A scan that finds nothing makes every ordering check below pass
    vacuously -- which is exactly what the first version of this file did."""
    for name, module in TABS:
        found = _labelled_filters(module)
        assert "Reporting Cycle" in found, f"{name}: {sorted(found)}"
        assert len(found) >= 5, f"{name} only found {sorted(found)}"


TABS = [
    ("Overview", overview_layout),
    ("PD", pd_layout),
    ("LGD", lgd_layout),
    ("EAD", ead_layout),
    ("Loss", loss_layout),
]


@pytest.mark.parametrize("name,module", TABS)
def test_every_filter_in_the_bar_follows_the_ordering_rule(name, module):
    wrong = []
    for label, pairs in _labelled_filters(module).items():
        values = _values(pairs)
        if len(values) < 2:
            continue  # a single-value filter (PD's own Model Group) orders trivially
        expected = newest_first(values) if label in PERIOD_FILTERS else alphabetical(values)
        if values != expected:
            wrong.append(f"{label}: {values} != {expected}")
    assert not wrong, f"{name}: " + "; ".join(wrong)


@pytest.mark.parametrize("name,module", TABS)
def test_sentinels_stay_at_the_head_of_their_list(name, module):
    """"All"/"Select …" must not sort into the middle of the values."""
    for label, pairs in _labelled_filters(module).items():
        positions = [i for i, (_l, value) in enumerate(pairs) if value in SENTINEL_VALUES]
        assert positions == list(range(len(positions))), f"{name} {label}: {pairs}"


@pytest.mark.parametrize("name,module", TABS)
def test_reporting_cycle_and_monitoring_point_read_the_same_direction(name, module):
    """Both are periods, so both descend -- the pair sits side by side in the
    bar and opposite directions read as a bug."""
    found = _labelled_filters(module)
    for label in ("Reporting Cycle", "Monitoring Point"):
        values = _values(found.get(label, []))
        assert values == newest_first(values), f"{name} {label}: {values}"


def test_the_model_group_filter_is_alphabetical_but_the_figure_order_is_not():
    """The two must not be conflated. ``MODEL_GROUPS`` is the loss-decomposition
    sequence every chart and table sorts on; only the *filter* is alphabetized."""
    from STATpy_platform.features.monitoring.domain.overview import MODEL_GROUPS

    assert overview_layout.SEGMENT_MODEL_GROUP_OPTIONS == ["All", "EAD", "LGD", "Loss", "PD"]
    assert MODEL_GROUPS == ["PD", "LGD", "EAD", "Loss"]
