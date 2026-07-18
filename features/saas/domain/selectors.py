"""Pure SAAS workspace selection, normalization, and label helpers."""

from __future__ import annotations

from datetime import datetime
import re

from ....shared import theme
from ..data_access import SAAS_PAGE_DATA

SEGMENT_ALL_VALUE = "all"
REGION_ALL_VALUE = "all"
MODEL_GROUP_ALL_VALUE = "all"
PORTFOLIO_ALL_VALUE = "all"
COMPARE_AGAINST_NONE_VALUE = "none"
DEFAULT_SCENARIO_FILTER = "all"

SUBNAV_VIEW_OPTIONS = [
    {"label": "History", "value": "history"},
    {"label": "Projection", "value": "projection"},
    {"label": "History & Projection", "value": "history_projection"},
]
DEFAULT_SUBNAV_VIEW = "history_projection"

MEV_LABEL_MODE_OPTIONS = [
    {"label": "Descriptive Name", "value": "long_name"},
    {"label": "US Mnemonic", "value": "us_mnemonic"},
    {"label": "Group Mnemonic", "value": "group_mnemonic"},
]
DEFAULT_MEV_LABEL_MODE = "us_mnemonic"

MEV_TYPE_OPTIONS = [
    {"label": "Transformed + raw", "value": "family"},
    {"label": "Transformed only", "value": "transformed_only"},
    {"label": "Raw only", "value": "raw_only"},
]
DEFAULT_MEV_TYPE = "family"

DATE_RANGE_PRESET_COUNTS = {"last-4": 4, "last-8": 8, "last-12": 12}

RUN_FOR_OPTIONS = [
    {"label": value, "value": value}
    for value in (SAAS_PAGE_DATA.get("run_for_values") or [])
    if value
]

RAW_MEV_NAMES = set(SAAS_PAGE_DATA.get("raw_mev_names") or set())
TRANSFORMED_MEV_NAMES = set(SAAS_PAGE_DATA.get("transformed_mev_names") or set())


def is_region_active(region: str | None) -> bool:
    return bool(region) and region != REGION_ALL_VALUE


def is_model_group_active(model_group: str | None) -> bool:
    return bool(model_group) and model_group != MODEL_GROUP_ALL_VALUE


def is_portfolio_active(portfolio: str | None) -> bool:
    return bool(portfolio) and portfolio != PORTFOLIO_ALL_VALUE


def model_descriptive_label(model_name: str) -> str:
    """Model's descriptive name, falling back to the raw model name."""
    descriptive_map = SAAS_PAGE_DATA.get("model_descriptive_name_map", {})
    return descriptive_map.get(model_name) or model_name


def models_in_group(parent_label: str) -> list[str]:
    """Child Model Names under a parent Descriptive Name, or a singleton for a
    model that is its own parent. Reads the canonical parent->children structure
    built once in :func:`loader.load_saas_mev_workbook_data`."""
    return list(SAAS_PAGE_DATA.get("descriptive_groups", {}).get(parent_label, []))


def normalize_multi_values(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def normalize_selected_segments(value) -> list[str]:
    selected_values = normalize_multi_values(value)
    valid_values = {SEGMENT_ALL_VALUE} | {
        segment for segment in (SAAS_PAGE_DATA.get("segment_values") or []) if segment
    }
    result = [item for item in selected_values if item in valid_values]
    return result or [SEGMENT_ALL_VALUE]


def active_segment_values(value) -> list[str]:
    """The selected segments with the "All" sentinel filtered out."""
    return [item for item in normalize_selected_segments(value) if item != SEGMENT_ALL_VALUE]


def is_segment_active(segment) -> bool:
    return bool(active_segment_values(segment))


def segment_toggle_label(selected_segments) -> str:
    active_segments = active_segment_values(selected_segments)
    if not active_segments:
        return "All"
    if len(active_segments) == 1:
        return active_segments[0]
    return f"{len(active_segments)} segments selected"


def normalize_selected_run_fors(value) -> list[str]:
    selected_values = normalize_multi_values(value)
    valid_values = [option["value"] for option in RUN_FOR_OPTIONS]
    return [value for value in valid_values if value in selected_values]


def normalize_compare_against_values(value, selected_run_for: str | None = None) -> list[str]:
    selected_values = normalize_multi_values(value)
    valid_values = [
        option["value"]
        for option in RUN_FOR_OPTIONS
        if option["value"] and option["value"] != selected_run_for
    ]
    compare_values = [item for item in selected_values if item in valid_values]
    if not compare_values:
        return [COMPARE_AGAINST_NONE_VALUE]
    return compare_values


def scoped_run_for_values(run_for, compare_against) -> list[str]:
    primary_values = normalize_selected_run_fors(run_for)
    primary_value = primary_values[0] if primary_values else None
    compare_values = normalize_compare_against_values(compare_against, primary_value)
    scoped_values = list(primary_values)
    for compare_value in compare_values:
        if compare_value == COMPARE_AGAINST_NONE_VALUE or compare_value in scoped_values:
            continue
        scoped_values.append(compare_value)
    return scoped_values


def run_for_meta_label(selected_run_fors) -> str:
    normalized_values = normalize_selected_run_fors(selected_run_fors)
    if not normalized_values:
        return "No Model Use Case / Cycle selected"
    all_values = [option["value"] for option in RUN_FOR_OPTIONS]
    if all_values and set(normalized_values) == set(all_values):
        return "All Model Use Case / Cycle values"
    if len(normalized_values) == 1:
        return normalized_values[0]
    return ", ".join(normalized_values)


def build_compare_against_options(selected_run_for: str | None) -> list[dict]:
    options = [{"label": "None", "value": COMPARE_AGAINST_NONE_VALUE}]
    for option in RUN_FOR_OPTIONS:
        value = option.get("value")
        if not value or value == selected_run_for:
            continue
        options.append({"label": option.get("label", value), "value": value})
    return options


def compare_against_toggle_label(selected_values, selected_run_for: str | None) -> str:
    normalized_values = normalize_compare_against_values(selected_values, selected_run_for)
    compare_values = [value for value in normalized_values if value != COMPARE_AGAINST_NONE_VALUE]
    if not compare_values:
        return "None"
    if len(compare_values) == 1:
        return compare_values[0]
    return f"{len(compare_values)} Model Use Case / Cycle values selected"


def _options_with_all(values: list[str], all_value: str) -> list[dict]:
    return [{"label": "All", "value": all_value}] + [
        {"label": value, "value": value} for value in values if value
    ]


def portfolio_values_for_filters(*, region: str | None = None) -> list[str]:
    """Portfolio values reachable given the Region filter (cascade step 1)."""
    all_values = list(SAAS_PAGE_DATA.get("portfolio_values") or [])
    if not is_region_active(region):
        return all_values
    model_region_map = SAAS_PAGE_DATA.get("model_region_map", {})
    model_portfolio_map = SAAS_PAGE_DATA.get("model_portfolio_map", {})
    reachable = {
        portfolio
        for model_name, portfolios in model_portfolio_map.items()
        if region in (model_region_map.get(model_name) or [])
        for portfolio in portfolios
    }
    return [value for value in all_values if value in reachable]


def model_group_values_for_filters(*, region: str | None = None, portfolio: str | None = None) -> list[str]:
    """Model Group values reachable given Region + Portfolio (cascade step 2)."""
    all_values = list(SAAS_PAGE_DATA.get("model_group_values") or [])
    if not is_region_active(region) and not is_portfolio_active(portfolio):
        return all_values
    model_region_map = SAAS_PAGE_DATA.get("model_region_map", {})
    model_group_map = SAAS_PAGE_DATA.get("model_group_map", {})
    model_portfolio_map = SAAS_PAGE_DATA.get("model_portfolio_map", {})
    reachable: set[str] = set()
    for model_name, groups in model_group_map.items():
        if is_region_active(region) and region not in (model_region_map.get(model_name) or []):
            continue
        if is_portfolio_active(portfolio) and portfolio not in (model_portfolio_map.get(model_name) or []):
            continue
        reachable.update(groups)
    return [value for value in all_values if value in reachable]


def segment_values_for_filters(
    *,
    region: str | None = None,
    portfolio: str | None = None,
    model_group: str | None = None,
    model_names: list[str] | None = None,
) -> list[str]:
    """Segment values reachable given Region + Portfolio + Model Group, and
    optionally restricted to a specific set of (raw) Model Names.

    Segment narrows off the same three upstream filters as Models
    (see :func:`model_names_for_filters`); it isn't chained after Specific
    Models in the sense of being disabled by it, but when ``model_names`` is
    passed (the current Models selection, expanded via
    :func:`effective_model_names`) the result only covers segments those
    particular models actually have.
    """
    all_values = list(SAAS_PAGE_DATA.get("segment_values") or [])
    if (
        model_names is None
        and not is_region_active(region)
        and not is_model_group_active(model_group)
        and not is_portfolio_active(portfolio)
    ):
        return all_values
    model_region_map = SAAS_PAGE_DATA.get("model_region_map", {})
    model_group_map = SAAS_PAGE_DATA.get("model_group_map", {})
    model_portfolio_map = SAAS_PAGE_DATA.get("model_portfolio_map", {})
    model_segments_map = SAAS_PAGE_DATA.get("model_segments_map", {})
    candidate_models = model_names if model_names is not None else list(model_segments_map.keys())
    reachable: set[str] = set()
    for model_name in candidate_models:
        if is_region_active(region) and region not in (model_region_map.get(model_name) or []):
            continue
        if is_model_group_active(model_group) and model_group not in (model_group_map.get(model_name) or []):
            continue
        if is_portfolio_active(portfolio) and portfolio not in (model_portfolio_map.get(model_name) or []):
            continue
        reachable.update(model_segments_map.get(model_name) or [])
    return [value for value in all_values if value in reachable]


def portfolio_options_for_filters(*, region: str | None = None) -> list[dict]:
    return _options_with_all(portfolio_values_for_filters(region=region), PORTFOLIO_ALL_VALUE)


def model_group_options_for_filters(*, region: str | None = None, portfolio: str | None = None) -> list[dict]:
    return _options_with_all(
        model_group_values_for_filters(region=region, portfolio=portfolio), MODEL_GROUP_ALL_VALUE
    )


def segment_options_for_filters(
    *,
    region: str | None = None,
    portfolio: str | None = None,
    model_group: str | None = None,
    model_names: list[str] | None = None,
) -> list[dict]:
    return _options_with_all(
        segment_values_for_filters(region=region, portfolio=portfolio, model_group=model_group, model_names=model_names),
        SEGMENT_ALL_VALUE,
    )


def model_names_for_filters(
    segment: str | None,
    *,
    region: str | None = None,
    model_group: str | None = None,
    portfolio: str | None = None,
) -> list[str]:
    base_models = list(SAAS_PAGE_DATA.get("model_names", []))
    model_segments_map = SAAS_PAGE_DATA.get("model_segments_map", {})
    model_region_map = SAAS_PAGE_DATA.get("model_region_map", {})
    model_group_map = SAAS_PAGE_DATA.get("model_group_map", {})
    model_portfolio_map = SAAS_PAGE_DATA.get("model_portfolio_map", {})
    # A model can belong to more than one region/group/segment, so membership
    # in the full per-model list is required -- comparing against a single
    # "primary" value would wrongly exclude a model from every filter except
    # whichever one happened to be seen first.
    if is_region_active(region):
        base_models = [model_name for model_name in base_models if region in (model_region_map.get(model_name) or [])]
    if is_model_group_active(model_group):
        base_models = [model_name for model_name in base_models if model_group in (model_group_map.get(model_name) or [])]
    if is_portfolio_active(portfolio):
        base_models = [model_name for model_name in base_models if portfolio in (model_portfolio_map.get(model_name) or [])]
    active_segments = active_segment_values(segment)
    if active_segments:
        segment_set = set(active_segments)
        base_models = [
            model_name for model_name in base_models
            if segment_set & set(model_segments_map.get(model_name) or [])
        ]
    return base_models


def model_options_for_filters(
    segment: str | None,
    *,
    region: str | None = None,
    model_group: str | None = None,
    portfolio: str | None = None,
    disabled: bool = False,
) -> list[dict]:
    """Specific-Models options, deduplicated by Model Descriptive Name.

    A Descriptive Name is the "parent" of one or more Model Names (see
    :func:`effective_model_names`, which expands a selected parent back out
    to its member Model Names) -- so two Model Names sharing a Descriptive
    Name surface as a single selectable option here instead of a
    visually-duplicate pair.
    """
    values = model_names_for_filters(segment, region=region, model_group=model_group, portfolio=portfolio)
    seen: set[str] = set()
    options: list[dict] = []
    for value in values:
        if not value:
            continue
        label = model_descriptive_label(value)
        if label in seen:
            continue
        seen.add(label)
        option = {"label": label, "value": label}
        if disabled:
            option["disabled"] = True
        options.append(option)
    return options


def model_toggle_label(selected_models: list[str], all_options: list[dict], segment_active: bool) -> str:
    selected_model_values = normalize_selected_models(selected_models)
    if segment_active:
        return "Disabled while Segment is selected"
    if not selected_model_values:
        return "Select models"
    all_values = [option["value"] for option in all_options]
    if all_values and set(selected_model_values) == set(all_values):
        return "All"
    if len(selected_model_values) == 1:
        return selected_model_values[0]
    return f"{len(selected_model_values)} models selected"


def normalize_selected_models(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def normalize_selected_mevs(value) -> list[str]:
    return normalize_multi_values(value)


def normalize_selected_mev_mode(value: str | None, options: list[dict] | None = None) -> str:
    raw_value = str(value or "").strip().lower()
    valid_values = {
        str(option.get("value") or "").strip().lower()
        for option in (options or MEV_TYPE_OPTIONS)
        if str(option.get("value") or "").strip()
    }
    if raw_value in valid_values:
        return raw_value
    return DEFAULT_MEV_TYPE


def normalize_selected_scenarios(value, options: list[dict] | None = None) -> list[str]:
    if isinstance(value, str):
        selected_values = [value] if value else []
    elif isinstance(value, list):
        selected_values = [str(item).strip().lower() for item in value if str(item).strip()]
    else:
        selected_values = []
    if options is None:
        return selected_values
    valid_values = {
        str(option.get("value") or "").strip().lower()
        for option in options
        if str(option.get("value") or "").strip()
    }
    return [selected_value for selected_value in selected_values if selected_value in valid_values]


def normalize_snapshot_period(value: str | None) -> str:
    valid_values = {option["value"] for option in SUBNAV_VIEW_OPTIONS}
    if value in valid_values:
        return value
    return DEFAULT_SUBNAV_VIEW


def normalize_mev_label_mode(value: str | None) -> str:
    valid_values = {option["value"] for option in MEV_LABEL_MODE_OPTIONS}
    if value in valid_values:
        return value
    return DEFAULT_MEV_LABEL_MODE


def format_scenario_label(value: str) -> str:
    normalized_value = str(value or "").strip().lower()
    if normalized_value == DEFAULT_SCENARIO_FILTER:
        return "All"
    return str(value or "").replace("_", " ").title()


def show_historical_statistics(selected_value) -> bool:
    return str(selected_value or "").strip().lower() == "on"


def resolve_date_range_selection(
    periods: list[str],
    window_value: str | None,
    from_value: str | None,
    to_value: str | None,
    triggered_id,
    *,
    window_trigger_type: str,
    from_trigger_type: str,
    to_trigger_type: str,
    range_preset_counts: dict[str, int] | None = None,
) -> dict[str, str]:
    valid_periods = set(periods)
    current = {
        "from": from_value if from_value in valid_periods else "",
        "to": to_value if to_value in valid_periods else "",
    }
    triggered_type = triggered_id.get("type") if isinstance(triggered_id, dict) else triggered_id

    if triggered_type == window_trigger_type:
        if window_value == "all":
            return {"from": "", "to": ""}
        preset_counts = range_preset_counts or DATE_RANGE_PRESET_COUNTS
        count = preset_counts.get(window_value or "")
        if not count or not periods:
            return current
        return {"from": periods[max(0, len(periods) - count)], "to": periods[-1]}

    if current["from"] and current["to"] and current["from"] > current["to"]:
        if triggered_type == from_trigger_type:
            current["to"] = current["from"]
        elif triggered_type == to_trigger_type:
            current["from"] = current["to"]
    return current


def normalize_theme_value(value: str | None) -> str:
    valid_values = {option["value"] for option in theme.THEME_OPTIONS}
    if value in valid_values:
        return value
    return theme.DEFAULT_THEME_VALUE


def effective_model_names(
    segment: str | None,
    selected_models,
    *,
    region: str | None = None,
    model_group: str | None = None,
    portfolio: str | None = None,
) -> list[str]:
    """Resolve the Specific-Models selection (Descriptive Names) to the
    underlying Model Names that actually key every SAAS data structure.

    A selected Descriptive Name is a "parent" that can cover more than one
    Model Name (see :func:`model_options_for_filters`); each one expands to
    every reachable Model Name sharing that Descriptive Name.
    """
    selected_descriptive_names = set(normalize_selected_models(selected_models))
    reachable_model_names = model_names_for_filters(None, region=region, model_group=model_group, portfolio=portfolio)
    all_descriptive_names = {model_descriptive_label(name) for name in reachable_model_names}
    all_models_selected = bool(all_descriptive_names) and selected_descriptive_names == all_descriptive_names

    if is_segment_active(segment):
        return model_names_for_filters(segment, region=region, model_group=model_group, portfolio=portfolio)
    if selected_descriptive_names and not all_models_selected:
        return [
            model_name for model_name in reachable_model_names
            if model_descriptive_label(model_name) in selected_descriptive_names
        ]
    if all_models_selected:
        return reachable_model_names
    return []


def model_scope_summary(
    segment: str | None,
    selected_models,
    *,
    region: str | None = None,
    model_group: str | None = None,
    portfolio: str | None = None,
) -> tuple[int, bool]:
    """Count of distinct Model Descriptive Names covered by the current
    Specific-Models scope, and whether that scope reaches every Descriptive
    Name available under the active Region/Portfolio/Model Group filters
    (i.e. the export meta-line should read "All" rather than a count).
    """
    effective = effective_model_names(
        segment, selected_models, region=region, model_group=model_group, portfolio=portfolio
    )
    reachable_model_names = model_names_for_filters(None, region=region, model_group=model_group, portfolio=portfolio)
    all_descriptive_names = {model_descriptive_label(name) for name in reachable_model_names}
    selected_descriptive_names = {model_descriptive_label(name) for name in effective}
    is_all = bool(all_descriptive_names) and selected_descriptive_names == all_descriptive_names
    return len(selected_descriptive_names), is_all


def group_effective_models(
    segment: str | None,
    selected_models,
    *,
    region: str | None = None,
    model_group: str | None = None,
    portfolio: str | None = None,
) -> list[tuple[str, list[str]]]:
    """The in-scope models grouped under their parent Descriptive Name, ordered
    by Model Group (in the workbook's natural group order, i.e.
    ``model_group_values``) and then by first-appearance within that group.
    Each entry is ``(parent_label, [member Model Names])``.

    Members are restricted to the models :func:`effective_model_names` keeps in
    scope, so a parent surfaces only the children the current filters allow --
    the UI renders one card per parent with every in-scope child inside it. A
    parent's Model Group is taken from its first member model; this ordering
    also drives the subnav chips and the exported report's section order, so
    all three stay in the same sequence (card "N." numbering matches chip N).
    """
    effective = effective_model_names(
        segment, selected_models, region=region, model_group=model_group, portfolio=portfolio
    )
    groups: dict[str, list[str]] = {}
    order: list[str] = []
    for model_name in effective:
        parent = model_descriptive_label(model_name)
        if parent not in groups:
            groups[parent] = []
            order.append(parent)
        groups[parent].append(model_name)

    model_group_map = SAAS_PAGE_DATA.get("model_group_map", {})
    group_rank = {value: index for index, value in enumerate(SAAS_PAGE_DATA.get("model_group_values") or [])}
    appearance_rank = {parent: index for index, parent in enumerate(order)}

    def _sort_key(parent: str) -> tuple[int, int]:
        first_member = groups[parent][0]
        primary_group = next(iter(model_group_map.get(first_member) or []), None)
        return (group_rank.get(primary_group, len(group_rank)), appearance_rank[parent])

    ordered_parents = sorted(order, key=_sort_key)
    return [(parent, groups[parent]) for parent in ordered_parents]


def primary_run_for_value(run_for) -> str | None:
    selected_values = normalize_selected_run_fors(run_for)
    return selected_values[0] if selected_values else None


def model_development_date(model_name: str, run_for) -> datetime | None:
    primary_run_for = primary_run_for_value(run_for)
    if not primary_run_for:
        return None
    return SAAS_PAGE_DATA.get("model_development_dates", {}).get(primary_run_for, {}).get(model_name)


def current_date_for_run_for(run_for) -> datetime | None:
    primary_run_for = primary_run_for_value(run_for)
    if not primary_run_for:
        return None
    match = re.search(r"(\d{4})$", primary_run_for)
    if not match:
        return None
    return datetime(int(match.group(1)) - 1, 12, 31)


def projection_start_date_for_run_for(run_for):
    """Return the date where Quarter == 0 for the primary Reporting Cycle."""
    primary_run_for = primary_run_for_value(run_for)
    if not primary_run_for:
        return None
    return SAAS_PAGE_DATA.get("run_for_quarter_zero_dates", {}).get(primary_run_for)


def mev_types_for_name(mev_name: str) -> set[str]:
    normalized_name = str(mev_name or "").strip()
    mev_types: set[str] = set()
    if normalized_name in TRANSFORMED_MEV_NAMES:
        mev_types.add("transformed")
    if normalized_name in RAW_MEV_NAMES:
        mev_types.add("raw")
    return mev_types


def active_mev_label_map(label_mode: str | None) -> dict[str, str]:
    normalized_mode = normalize_mev_label_mode(label_mode)
    if normalized_mode == "long_name":
        return SAAS_PAGE_DATA.get("mev_label_map", {})
    if normalized_mode == "group_mnemonic":
        return SAAS_PAGE_DATA.get("mev_group_label_map", {})
    return {}


def resolve_mev_label(mev_name: str, label_mode: str | None) -> str:
    return active_mev_label_map(label_mode).get(mev_name) or mev_name


def resolve_mev_description(mev_name: str) -> str | None:
    description = SAAS_PAGE_DATA.get("mev_description_map", {}).get(mev_name)
    return description or None


def mev_type_label(mev_name: str) -> str:
    mev_types = mev_types_for_name(mev_name)
    if mev_types == {"raw"}:
        return "Raw"
    if mev_types == {"transformed"}:
        return "Transformed"
    if mev_types:
        return "Raw / Transformed"
    return "—"


def saas_family_ordered_names(model_name: str, present_names, mev_label_mode) -> list[str]:
    """Order MEV names so each transformed MEV is followed by its raw MEVs."""
    family_map = SAAS_PAGE_DATA.get("model_mev_family_map", {}).get(model_name, {})
    present = set(present_names)
    used: set = set()
    ordered: list[str] = []
    transformed = sorted(
        (name for name in family_map if name in present),
        key=lambda name: resolve_mev_label(name, mev_label_mode).lower(),
    )
    for transformed_name in transformed:
        if transformed_name in used:
            continue
        ordered.append(transformed_name)
        used.add(transformed_name)
        for raw_name in family_map[transformed_name]:
            if raw_name in present and raw_name not in used:
                ordered.append(raw_name)
                used.add(raw_name)
    for name in sorted(present, key=lambda name: resolve_mev_label(name, mev_label_mode).lower()):
        if name not in used:
            ordered.append(name)
            used.add(name)
    return ordered
