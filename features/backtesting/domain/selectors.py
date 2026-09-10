"""Filter-scope resolution for the backtesting dashboard.

Pure data logic over :data:`BACKTESTING_PAGE_DATA` -- no Dash imports. Mirrors
``features/saas/domain/selectors.py``: the UI asks "which models does this
segment have?" and gets a plain list back, so no view module inspects a frame.

**The model catalogue is authoritative for scope.** Region, Portfolio, Model
Group, the segments a model serves, and the label it is shown under all come
from the ``model_names`` sheet of ``dummy_mev_data.xlsx`` -- the same catalogue
Monitoring and SAAS read -- rather than from the backtesting workbook. The
backtesting workbook is generated to match it, so a catalogue-driven cascade
never offers a combination with no rows. See ``features/backtesting/README.md``.

A model whose catalogue attribute is blank is shown as ``Unassigned`` rather
than dropped: selecting a real Region or Portfolio then excludes it, which is
the honest reading of a missing value, and the gap stays visible.
"""

from __future__ import annotations

from functools import lru_cache

from ....shared.domain import constants as config
from ..data_access import BACKTESTING_PAGE_DATA

ALL_VALUE = "all"
UNASSIGNED = config.BACKTESTING_UNASSIGNED_LABEL


def is_all(value) -> bool:
    """Whether a filter selection means "no narrowing"."""
    return value in (None, "", ALL_VALUE)


def catalog() -> dict[str, dict]:
    """``{model_name: attributes}`` for the models this workbook contains."""
    return BACKTESTING_PAGE_DATA.get("model_catalog") or {}


@lru_cache(maxsize=1)
def _pd_model_names() -> tuple[str, ...]:
    """PD-side models, across both disjoint PD populations.

    The Model filter is PD-side: the two PD sheets each carry one model, so the
    union is what a user picks from. Reading one sheet would offer half.
    """
    model_values = BACKTESTING_PAGE_DATA.get("model_values") or {}
    names: list[str] = []
    for metric in config.BACKTESTING_PD_METRICS:
        for value in model_values.get(metric) or []:
            if value not in names:
                names.append(value)
    return tuple(names)


def all_models() -> list[str]:
    return list(_pd_model_names())


def model_label(model: str) -> str:
    """The model's descriptive name from the catalogue, falling back to its key."""
    return (catalog().get(model) or {}).get("label") or model


def _attribute(model: str, key: str) -> str:
    return (catalog().get(model) or {}).get(key) or UNASSIGNED


def _model_segments(model: str) -> list[str]:
    return list((catalog().get(model) or {}).get("segments") or [])


def _distinct(values) -> list[str]:
    """Distinct values in first-seen order, with ``Unassigned`` sorted last.

    Keeping the gap at the end of the list stops a missing attribute from
    heading the dropdown, without hiding it.
    """
    ordered = [value for value in dict.fromkeys(values) if value]
    real = [value for value in ordered if value != UNASSIGNED]
    return sorted(real) + ([UNASSIGNED] if UNASSIGNED in ordered else [])


# ---------------------------------------------------------------------------
# Attribute catalogs -- each narrowed by the filters to its left
# ---------------------------------------------------------------------------


def models_matching(
    *,
    region=None,
    portfolio=None,
    model_group=None,
    segment=None,
) -> list[str]:
    """PD models satisfying every supplied attribute filter.

    The single place scope is resolved: every option list and the cascade are
    derived from it, so they cannot disagree about what a selection means.
    """
    matched = []
    for model in _pd_model_names():
        if not is_all(region) and _attribute(model, "region") != region:
            continue
        if not is_all(portfolio) and _attribute(model, "portfolio") != portfolio:
            continue
        if not is_all(model_group) and _attribute(model, "model_group") != model_group:
            continue
        if not is_all(segment) and segment not in _model_segments(model):
            continue
        matched.append(model)
    return matched


def region_values() -> list[str]:
    return _distinct(_attribute(model, "region") for model in _pd_model_names())


def portfolio_values(*, region=None) -> list[str]:
    return _distinct(
        _attribute(model, "portfolio") for model in models_matching(region=region)
    )


def model_group_values(*, region=None, portfolio=None) -> list[str]:
    return _distinct(
        _attribute(model, "model_group")
        for model in models_matching(region=region, portfolio=portfolio)
    )


def all_segments() -> list[str]:
    """Segments the PD models serve, per the catalogue.

    Deliberately *not* read from the backtesting workbook: the catalogue drives
    scope, and the workbook is generated to agree with it.
    """
    return _distinct(
        segment for model in _pd_model_names() for segment in _model_segments(model)
    )


def segments_for_model(model) -> list[str]:
    """Segments ``model`` serves (all of them when unnarrowed)."""
    if is_all(model):
        return all_segments()
    return _distinct(_model_segments(model)) or all_segments()


def models_for_segment(segment, *, region=None, portfolio=None, model_group=None) -> list[str]:
    """Models serving ``segment``, also honouring the attribute filters."""
    matched = models_matching(
        region=region, portfolio=portfolio, model_group=model_group, segment=segment
    )
    # Fall back to the unnarrowed list rather than an empty one: an empty
    # dropdown reads as breakage.
    return matched or models_matching(region=region, portfolio=portfolio, model_group=model_group)


def segments_for_filters(*, region=None, portfolio=None, model_group=None, model=None) -> list[str]:
    """Segments reachable under the current attribute selection."""
    if not is_all(model):
        return segments_for_model(model)
    models = models_matching(region=region, portfolio=portfolio, model_group=model_group)
    return _distinct(
        segment for model_name in models for segment in _model_segments(model_name)
    ) or all_segments()


# ---------------------------------------------------------------------------
# Scope summary
# ---------------------------------------------------------------------------


def describe_scope(applied: dict | None) -> str:
    """One-line human summary of an applied filter set.

    Used for the top bar's help line, so a user can see what the sections below
    are actually reporting on without re-reading nine dropdowns.
    """
    if not applied:
        return ""

    def _label(value, all_text: str) -> str:
        return all_text if is_all(value) else str(value)

    model = applied.get("model")
    parts = [
        f"Region: {_label(applied.get('region'), 'All regions')}",
        f"Portfolio: {_label(applied.get('portfolio'), 'All portfolios')}",
        f"Model Group: {_label(applied.get('model_group'), 'All groups')}",
        f"Model: {'All models' if is_all(model) else model_label(model)}",
        f"Segment: {_label(applied.get('segment'), 'All segments')}",
        f"Model Use Case / Cycle: {_label(applied.get('run_for'), 'All cycles')}",
        f"Scenario: {_label(applied.get('scenario'), 'All scenarios')}",
        f"J/N: {_label(applied.get('jn_flag'), 'Both')}",
        f"Snapshot: {_label(applied.get('snapshot'), 'All vintages')}",
    ]
    return " · ".join(parts)
