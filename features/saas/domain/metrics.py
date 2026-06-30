"""Pure SAAS workspace metric and comparison calculations."""

from __future__ import annotations

from collections import defaultdict
import statistics

from ....shared.domain.calculations import is_finite_number
from ..data_access import SAAS_PAGE_DATA
from . import records as record_filters
from . import selectors

BASELINE_SCENARIO_VALUE = "baseline"


def compute_historical_dispersion_stats(records: list[dict], selected_scenarios) -> dict | None:
    scoped_records = record_filters.filter_records_by_scenarios(records, selected_scenarios)
    values_by_date: dict[object, dict[tuple[str, str], float]] = {}
    visible_lines: set[tuple[str, str]] = set()

    for row in scoped_records:
        date_value = row.get("Date")
        scenario_value = str(row.get("Scenario") or "").strip().lower()
        run_for_value = str(row.get("Run For") or "").strip()
        numeric_value = row.get("MEV Value")
        if date_value is None or not run_for_value or not is_finite_number(numeric_value):
            continue
        line_key = (run_for_value, scenario_value)
        visible_lines.add(line_key)
        values_by_date.setdefault(date_value, {})[line_key] = float(numeric_value)

    if len(visible_lines) < 2:
        return {
            "visible_lines": len(visible_lines),
            "matched_quarters": 0,
            "has_dispersion": False,
        }

    per_date_ranges: list[float] = []
    per_date_stddevs: list[float] = []
    max_range_date = None
    max_range_value = None

    for date_value in sorted(values_by_date):
        line_values = list(values_by_date[date_value].values())
        if len(line_values) < 2:
            continue
        range_value = max(line_values) - min(line_values)
        stddev_value = statistics.pstdev(line_values) if len(line_values) > 1 else 0.0
        per_date_ranges.append(range_value)
        per_date_stddevs.append(stddev_value)
        if max_range_value is None or range_value > max_range_value:
            max_range_value = range_value
            max_range_date = date_value

    if not per_date_ranges:
        return {
            "visible_lines": len(visible_lines),
            "matched_quarters": 0,
            "has_dispersion": False,
        }

    return {
        "visible_lines": len(visible_lines),
        "matched_quarters": len(per_date_ranges),
        "avg_range": sum(per_date_ranges) / len(per_date_ranges),
        "max_range": max(per_date_ranges),
        "avg_stddev": sum(per_date_stddevs) / len(per_date_stddevs),
        "max_stddev": max(per_date_stddevs),
        "max_range_date": max_range_date,
        "has_dispersion": True,
    }


def excel_to_py_date(value):
    if value is None:
        return None
    if hasattr(value, "to_pydatetime"):
        try:
            return value.to_pydatetime()
        except (TypeError, ValueError):
            return None
    return value


def excel_quarter_label(value) -> str:
    parsed = excel_to_py_date(value)
    if parsed is None:
        return ""
    quarter = ((parsed.month - 1) // 3) + 1
    return f"{parsed.year}Q{quarter}"


def compute_saas_metric_record(
    model_name: str,
    mev_label: str,
    subset_rows: list[dict],
    *,
    baseline_min: float | None = None,
    baseline_max: float | None = None,
) -> dict | None:
    history = [
        (row.get("Date"), float(row.get("MEV Value")))
        for row in subset_rows
        if is_finite_number(row.get("MEV Value")) and is_finite_number(row.get("Quarter")) and float(row.get("Quarter")) <= 0
    ]
    projection = [
        float(row.get("MEV Value"))
        for row in subset_rows
        if is_finite_number(row.get("MEV Value")) and is_finite_number(row.get("Quarter")) and float(row.get("Quarter")) > 0
    ]
    if not history:
        return None

    history_values = [value for _, value in history]
    history_min = min(history_values)
    history_max = max(history_values)
    history_mean = statistics.fmean(history_values)
    history_std = statistics.pstdev(history_values) if len(history_values) > 1 else 0.0

    def _extreme_date(target: float):
        candidates = sorted(
            (date_value for date_value, value in history if value == target and date_value is not None),
            key=lambda value: (getattr(value, "year", 0), getattr(value, "month", 0), getattr(value, "day", 0)),
        )
        return excel_to_py_date(candidates[0]) if candidates else None

    sevadv_min = min(projection) if projection else None
    sevadv_max = max(projection) if projection else None
    history_min_2std = history_min - 2 * history_std
    history_max_2std = history_max + 2 * history_std

    is_min_lt_2std = sevadv_min is not None and sevadv_min < history_min_2std
    is_max_gt_2std = sevadv_max is not None and sevadv_max > history_max_2std
    is_baseline_min_lt_2std = (baseline_min < history_min_2std) if baseline_min is not None else None
    is_baseline_max_gt_2std = (baseline_max > history_max_2std) if baseline_max is not None else None

    time_of_min = _extreme_date(history_min)
    time_of_max = _extreme_date(history_max)

    # Full date span of the historical (Quarter <= 0) data: earliest to latest date.
    history_dates = sorted(
        excel_to_py_date(date_value) for date_value, _ in history if date_value is not None
    )
    if len(history_dates) >= 2:
        minmax_daterange = f"{history_dates[0]:%Y-%m-%d} to {history_dates[-1]:%Y-%m-%d}"
    elif len(history_dates) == 1:
        minmax_daterange = f"{history_dates[0]:%Y-%m-%d}"
    else:
        minmax_daterange = ""

    return {
        "model": model_name,
        "model_descriptive": selectors.model_descriptive_label(model_name),
        "mev": mev_label,
        "history_min": history_min,
        "history_max": history_max,
        "history_mean": history_mean,
        "history_std": history_std,
        "sevadv_min": sevadv_min,
        "sevadv_max": sevadv_max,
        "is_min_beyond": sevadv_min is not None and sevadv_min < history_min,
        "is_max_beyond": sevadv_max is not None and sevadv_max > history_max,
        "minmax_daterange": minmax_daterange,
        "time_of_min": time_of_min,
        "time_of_max": time_of_max,
        "history_min_2std": history_min_2std,
        "history_max_2std": history_max_2std,
        "is_min_lt_2std": is_min_lt_2std,
        "is_max_gt_2std": is_max_gt_2std,
        "is_baseline_min_lt_2std": is_baseline_min_lt_2std,
        "is_baseline_max_gt_2std": is_baseline_max_gt_2std,
        "conclusion": any(
            flag is True
            for flag in (is_min_lt_2std, is_max_gt_2std, is_baseline_min_lt_2std, is_baseline_max_gt_2std)
        ),
    }


def build_saas_chart_spec(model_name: str, mev_name: str, mev_label: str, subset_rows: list[dict], *, mev_type: str | None = None) -> dict:
    points = sorted(
        (
            (float(row.get("Quarter")), row.get("Date"), float(row.get("MEV Value")))
            for row in subset_rows
            if is_finite_number(row.get("MEV Value")) and is_finite_number(row.get("Quarter"))
        ),
        key=lambda item: item[0],
    )
    labels = [excel_quarter_label(date_value) for _, date_value, _ in points]
    history = [value if quarter <= 0 else None for quarter, _, value in points]
    projection = [value if quarter > 0 else None for quarter, _, value in points]
    history_values = [value for quarter, _, value in points if quarter <= 0]
    type_suffix = f" [{mev_type}]" if mev_type and mev_type != "—" else ""
    return {
        "model": model_name,
        "mev_name": mev_name,
        "mev_type": mev_type or "",
        "title": f"{mev_label}{type_suffix}",
        "y_title": mev_label,
        "labels": labels,
        "history": history,
        "projection": projection,
        "hist_min": min(history_values) if history_values else None,
        "hist_max": max(history_values) if history_values else None,
    }


def saas_baseline_projection_bounds(time_series_df, primary_run_for, effective_models) -> dict[tuple[str, str], tuple[float, float]]:
    """Per (model, MEV) min/max of the Baseline scenario's projection (Quarter > 0)."""
    baseline_df = time_series_df[
        (time_series_df["Run For"] == primary_run_for)
        & (time_series_df["Scenario"].astype(str).str.strip().str.lower() == BASELINE_SCENARIO_VALUE)
        & (time_series_df["Model Name"].isin(effective_models))
    ]
    bounds: dict[tuple[str, str], list[float]] = {}
    for row in baseline_df.to_dict(orient="records"):
        if not (is_finite_number(row.get("MEV Value")) and is_finite_number(row.get("Quarter")) and float(row.get("Quarter")) > 0):
            continue
        key = (row.get("Model Name"), str(row.get("MEV Name") or "").strip())
        value = float(row.get("MEV Value"))
        if key in bounds:
            bounds[key][0] = min(bounds[key][0], value)
            bounds[key][1] = max(bounds[key][1], value)
        else:
            bounds[key] = [value, value]
    return {key: (lo, hi) for key, (lo, hi) in bounds.items()}


def compute_saas_metrics(run_for, segment, selected_models, mev_label_mode, scenario):
    """Return (metric_rows, chart_specs, primary_run_for, baseline_available)."""
    time_series_df = SAAS_PAGE_DATA.get("mev_time_series")
    selected_run_fors = selectors.normalize_selected_run_fors(run_for)
    primary_run_for = selected_run_fors[0] if selected_run_fors else None
    effective_models = selectors.effective_model_names(segment, selected_models)
    scenario_value = str(scenario or "").strip().lower()

    if (
        time_series_df is None
        or time_series_df.empty
        or not primary_run_for
        or not effective_models
        or not scenario_value
    ):
        return [], [], primary_run_for, False

    scenario_series = time_series_df["Scenario"].astype(str).str.strip().str.lower()
    baseline_available = bool((scenario_series == BASELINE_SCENARIO_VALUE).any())
    baseline_bounds = (
        saas_baseline_projection_bounds(time_series_df, primary_run_for, effective_models)
        if baseline_available
        else {}
    )

    scoped_df = time_series_df[
        (time_series_df["Run For"] == primary_run_for)
        & (scenario_series == scenario_value)
        & (time_series_df["Model Name"].isin(effective_models))
    ]
    records = scoped_df.to_dict(orient="records")

    records_by_model: dict[str, list[dict]] = {}
    for row in records:
        records_by_model.setdefault(row.get("Model Name"), []).append(row)

    metric_rows: list[dict] = []
    chart_specs: list[dict] = []
    for model_name in effective_models:
        model_records = records_by_model.get(model_name, [])
        if not model_records:
            continue
        present_names = {str(row.get("MEV Name") or "").strip() for row in model_records if str(row.get("MEV Name") or "").strip()}
        # Include every MEV available for the model (both Raw and Transformed),
        # grouped by type then ordered by label.
        mev_names = sorted(
            present_names,
            key=lambda name: (selectors.excel_mev_type_label(name), selectors.resolve_mev_label(name, mev_label_mode).lower()),
        )
        for mev_name in mev_names:
            subset = [row for row in model_records if str(row.get("MEV Name") or "").strip() == mev_name]
            mev_label = selectors.resolve_mev_label(mev_name, mev_label_mode)
            mev_type = selectors.excel_mev_type_label(mev_name)
            baseline_min, baseline_max = baseline_bounds.get((model_name, mev_name), (None, None))
            record = compute_saas_metric_record(
                model_name, mev_label, subset,
                baseline_min=baseline_min, baseline_max=baseline_max,
            )
            if record is None:
                continue
            record["mev_type"] = mev_type
            record["model_contribution"] = SAAS_PAGE_DATA.get("model_mev_contribution_map", {}).get(model_name, {}).get(mev_name)
            metric_rows.append(record)
            chart_specs.append(build_saas_chart_spec(model_name, mev_name, mev_label, subset, mev_type=mev_type))

    return metric_rows, chart_specs, primary_run_for, baseline_available


def compute_saas_reconciliation(run_for, compare_against, segment, selected_models, mev_label_mode, scenario):
    """Reconcile historical values across the primary cycle and comparison cycles."""
    time_series_df = SAAS_PAGE_DATA.get("mev_time_series")
    primary = selectors.primary_run_for_value(run_for)
    compare_cycles = [
        value for value in selectors.normalize_compare_against_values(compare_against, primary)
        if value and value != selectors.COMPARE_AGAINST_NONE_VALUE
    ]
    effective_models = selectors.effective_model_names(segment, selected_models)
    scenario_value = str(scenario or "").strip().lower()

    base = {"primary": primary, "compare_cycles": compare_cycles, "cycles": [primary, *compare_cycles], "models": []}
    if (
        time_series_df is None
        or time_series_df.empty
        or not primary
        or not scenario_value
        or not compare_cycles
        or not effective_models
    ):
        return base

    cycles = [primary, *compare_cycles]
    scen_series = time_series_df["Scenario"].astype(str).str.strip().str.lower()
    scoped = time_series_df[
        (scen_series == scenario_value)
        & (time_series_df["Run For"].isin(cycles))
        & (time_series_df["Model Name"].isin(effective_models))
        & (time_series_df["Quarter"] <= 0)
    ]

    index: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    present_by_model: dict = defaultdict(set)
    for row in scoped.to_dict(orient="records"):
        if not (is_finite_number(row.get("MEV Value")) and is_finite_number(row.get("Quarter"))):
            continue
        model = row.get("Model Name")
        mev = str(row.get("MEV Name") or "").strip()
        cycle = str(row.get("Run For") or "").strip()
        date_value = row.get("Date")
        if not model or not mev or not cycle or date_value is None:
            continue
        index[model][mev][cycle][date_value] = float(row.get("MEV Value"))
        present_by_model[model].add(mev)

    models_out: list[dict] = []
    for model_name in effective_models:
        mev_names = selectors.saas_family_ordered_names(model_name, present_by_model.get(model_name, set()), mev_label_mode)
        mev_blocks: list[dict] = []
        for mev_name in mev_names:
            per_cycle = index[model_name].get(mev_name, {})
            date_sets = [set(per_cycle.get(cycle, {}).keys()) for cycle in cycles]
            if any(not date_set for date_set in date_sets):
                continue
            overlap = set.intersection(*date_sets)
            if not overlap:
                continue
            ordered_dates = sorted(overlap)
            values = {cycle: [per_cycle[cycle][date] for date in ordered_dates] for cycle in cycles}
            diffs: dict = {}
            for cycle in compare_cycles:
                abs_list, pct_list = [], []
                for date in ordered_dates:
                    primary_value = per_cycle[primary][date]
                    compare_value = per_cycle[cycle][date]
                    abs_list.append(compare_value - primary_value)
                    pct_list.append((compare_value - primary_value) / primary_value if primary_value else None)
                diffs[cycle] = {"abs": abs_list, "pct": pct_list}
            mev_blocks.append({
                "mev_name": mev_name,
                "mev_label": selectors.resolve_mev_label(mev_name, mev_label_mode),
                "mev_type": selectors.excel_mev_type_label(mev_name),
                "periods": [excel_quarter_label(date) for date in ordered_dates],
                "values": values,
                "diffs": diffs,
            })
        if mev_blocks:
            models_out.append({"model": model_name, "mevs": mev_blocks})

    base["models"] = models_out
    return base


def compute_saas_projection_comparison(run_for, compare_against, segment, selected_models, mev_label_mode, scenario, max_quarter=20):
    """Compare projection paths across the primary cycle and comparison cycles."""
    time_series_df = SAAS_PAGE_DATA.get("mev_time_series")
    primary = selectors.primary_run_for_value(run_for)
    compare_cycles = [
        value for value in selectors.normalize_compare_against_values(compare_against, primary)
        if value and value != selectors.COMPARE_AGAINST_NONE_VALUE
    ]
    effective_models = selectors.effective_model_names(segment, selected_models)
    scenario_value = str(scenario or "").strip().lower()

    base = {"primary": primary, "compare_cycles": compare_cycles, "cycles": [primary, *compare_cycles], "models": []}
    if (
        time_series_df is None
        or time_series_df.empty
        or not primary
        or not scenario_value
        or not compare_cycles
        or not effective_models
    ):
        return base

    cycles = [primary, *compare_cycles]
    scen_series = time_series_df["Scenario"].astype(str).str.strip().str.lower()
    scoped = time_series_df[
        (scen_series == scenario_value)
        & (time_series_df["Run For"].isin(cycles))
        & (time_series_df["Model Name"].isin(effective_models))
        & (time_series_df["Quarter"] >= 0)
    ]

    index: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    present_by_model: dict = defaultdict(set)
    for row in scoped.to_dict(orient="records"):
        if not (is_finite_number(row.get("MEV Value")) and is_finite_number(row.get("Quarter"))):
            continue
        model = row.get("Model Name")
        mev = str(row.get("MEV Name") or "").strip()
        cycle = str(row.get("Run For") or "").strip()
        quarter = int(round(float(row.get("Quarter"))))
        if not model or not mev or not cycle:
            continue
        index[model][mev][cycle][quarter] = float(row.get("MEV Value"))
        present_by_model[model].add(mev)

    models_out: list[dict] = []
    for model_name in effective_models:
        mev_names = selectors.saas_family_ordered_names(model_name, present_by_model.get(model_name, set()), mev_label_mode)
        mev_blocks: list[dict] = []
        for mev_name in mev_names:
            per_cycle = index[model_name].get(mev_name, {})
            quarter_sets = [set(per_cycle.get(cycle, {}).keys()) for cycle in cycles]
            if any(not quarter_set for quarter_set in quarter_sets):
                continue
            overlap = set.intersection(*quarter_sets)
            if max_quarter is not None:
                overlap = {quarter for quarter in overlap if quarter <= max_quarter}
            if not overlap:
                continue
            ordered_quarters = sorted(overlap)
            values = {cycle: [per_cycle[cycle][quarter] for quarter in ordered_quarters] for cycle in cycles}
            diffs: dict = {}
            for cycle in compare_cycles:
                abs_list, pct_list = [], []
                for quarter in ordered_quarters:
                    primary_value = per_cycle[primary][quarter]
                    compare_value = per_cycle[cycle][quarter]
                    abs_list.append(compare_value - primary_value)
                    pct_list.append((compare_value - primary_value) / primary_value if primary_value else None)
                diffs[cycle] = {"abs": abs_list, "pct": pct_list}
            mev_blocks.append({
                "mev_name": mev_name,
                "mev_label": selectors.resolve_mev_label(mev_name, mev_label_mode),
                "mev_type": selectors.excel_mev_type_label(mev_name),
                "periods": [f"Q{quarter}" for quarter in ordered_quarters],
                "values": values,
                "diffs": diffs,
            })
        if mev_blocks:
            models_out.append({"model": model_name, "mevs": mev_blocks})

    base["models"] = models_out
    return base
