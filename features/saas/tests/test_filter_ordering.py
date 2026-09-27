"""SAAS's filter bar follows the same ordering rule as the monitoring tabs.

Text A-Z, cycles most-recent-first. The **mode selectors** are deliberately
exempt: Snapshot Period, Reference Lines, MEV Label and Historical Statistics
list modes, not data values, and their order carries meaning ("History ->
Projection -> History & Projection", "Off -> On") that alphabetizing destroys.
"""

from __future__ import annotations

from dash.development.base_component import Component

from STATpy_platform.features.saas.ui.views import workspace as layout
from STATpy_platform.shared.domain.filter_order import alphabetical, composite_cycles_newest_first

# Sentinels that head a list rather than sorting into it.
SENTINEL_LABELS = {"All", "None"}

# Filters whose values are modes, not data -- their order is their meaning.
MODE_FILTERS = {"Snapshot Period", "Reference Lines", "MEV Label", "Historical Statistics"}

CYCLE_FILTERS = {"Model Use Case / Cycle", "Compare To"}


def _walk(node):
    yield node
    children = getattr(node, "children", None)
    if children is None:
        return
    for child in (children if isinstance(children, (list, tuple)) else [children]):
        if isinstance(child, Component):
            yield from _walk(child)


def _labelled_filters():
    found: dict[str, list[str]] = {}
    for root in layout.page_layout():
        if not isinstance(root, Component):
            continue
        for node in _walk(root):
            if "monitoring-filter" not in (getattr(node, "className", None) or "").split():
                continue
            cell = list(_walk(node))
            label = next((n.children for n in cell
                          if type(n).__name__ == "Label" and isinstance(n.children, str)), None)
            if label is None or label in found:
                continue
            options = next((getattr(n, "options", None) for n in cell
                            if getattr(n, "options", None)), None)
            if options:
                found[label] = [o["label"] if isinstance(o, dict) else str(o) for o in options]
    return found


def test_the_scan_actually_finds_the_bar():
    """Without this the checks below would pass on an empty dict."""
    found = _labelled_filters()
    assert "Region" in found and "Model Use Case / Cycle" in found, sorted(found)


def test_value_filters_are_alphabetical():
    wrong = []
    for label, options in _labelled_filters().items():
        if label in MODE_FILTERS or label in CYCLE_FILTERS:
            continue
        values = [v for v in options if v not in SENTINEL_LABELS]
        if len(values) < 2:
            continue
        if values != alphabetical(values):
            wrong.append(f"{label}: {values}")
    assert not wrong, "; ".join(wrong)


def test_cycle_filters_read_most_recent_first():
    for label in CYCLE_FILTERS:
        values = [v for v in _labelled_filters().get(label, []) if v not in SENTINEL_LABELS]
        assert values == composite_cycles_newest_first(values), f"{label}: {values}"


def test_the_page_opens_on_the_most_recent_cycle():
    """The default is taken from position, so ordering decides it. Before the
    cycles were sorted this landed on the *oldest* cycle in the workbook."""
    options = [o["value"] for o in layout.RUN_FOR_OPTIONS]
    assert layout.DEFAULT_RUN_FOR_VALUE == options[0]
    assert layout.DEFAULT_RUN_FOR_VALUE == composite_cycles_newest_first(options)[0]


def test_mode_selectors_keep_their_meaningful_order():
    """Guards the exemption: these must not be swept into the alphabetizing."""
    found = _labelled_filters()
    assert found["Snapshot Period"] == ["History", "Projection", "History & Projection"]
    assert found["Historical Statistics"] == ["Off", "On"]


def test_the_dynamically_rebuilt_model_options_are_also_alphabetical():
    """The Model checklist is repopulated by a callback through
    ``selectors.model_options_for_filters``, not by the static layout above --
    so the layout-only checks miss it. Left in workbook order it interleaved the
    groups: "PD Model A, EAD Model A, LGD Model A, PD Model B, ...".
    """
    from STATpy_platform.features.saas.domain import selectors

    labels = [o["label"] for o in selectors.model_options_for_filters(None)]
    assert len(labels) > 2, labels
    assert labels == alphabetical(labels), labels
