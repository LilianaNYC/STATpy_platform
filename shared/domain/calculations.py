"""Calculation engine for the PD Performance tab.

This module is a line-by-line port of the calculation helpers defined in the
``JS`` string of ``pages/monitoring_pd_models_page.py`` (the original
monolithic dashboard). Function names are the ``snake_case`` equivalents of
the original ``camelCase`` JS functions (e.g. ``calculatePdAuc`` ->
``calculate_pd_auc``).

A few JS globals had no direct Python equivalent and are replaced here:

- ``MONITORING_MODELS`` / ``MONITORING_PORTFOLIO_SEGMENT`` / ``CQ`` (monitoring
  point) / ``MONITORING_PD_INPUT`` / ``MONITORING_TIME_HORIZON`` /
  ``DASH_DATA.quarters`` are bundled into a :class:`PdFilterContext` that is
  threaded through every function that needs them.
- ``PD_TIME_RANGES`` (a mutable global holding the from/to range per chart)
  becomes a plain ``{"from": ..., "to": ...}`` dict passed in explicitly -
  in the Dash app this dict lives in a ``dcc.Store``.
- ``fmtN`` (defined in ``components/monitoring_helpers_js.py``) is ported as
  :func:`fmt_n`.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from . import constants as config

# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _to_number(value):
    """Port of JS ``Number(value)`` followed by ``Number.isFinite`` filtering."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def is_finite_number(value):
    """Port of ``Number.isFinite(value)``."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _first_present(row, *keys):
    """Port of ``a ?? b ?? c`` (nullish coalescing) over dict keys."""
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _ge(value, bound):
    """``value >= bound``, but ``False`` if ``bound`` is ``None`` (mirrors JS NaN comparisons)."""
    return bound is not None and value >= bound


def _le(value, bound):
    """``value <= bound``, but ``False`` if ``bound`` is ``None`` (mirrors JS NaN comparisons)."""
    return bound is not None and value <= bound


def fmt_n(value):
    """Port of ``const fmtN = (v) => v == null ? '—' : (+v).toLocaleString('en-US')``."""
    if value is None:
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    if number == int(number):
        return f"{int(number):,}"
    return f"{number:,.3f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------
# Filter context (replaces JS globals MONITORING_*, CQ, DASH_DATA.quarters)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PdFilterContext:
    """Bundles the filter state that the JS code read from page-level globals."""

    quarters: list[str]
    models: set[str]
    segment: str
    monitoring_point: str


# ---------------------------------------------------------------------------
# Precomputed-metrics store
# ---------------------------------------------------------------------------
# The PD Performance tab reads metrics straight from the ``PD_Performance_Metrics``
# workbook tab rather than recomputing them from facility-level data. The loader
# builds a lookup keyed by ``(model_key, segment_key, quarter, horizon_key)`` and
# installs it here; the metric functions below consult it and return the
# pre-calculated values verbatim. ``model_key`` is the model name, or ``"ALL"``
# when every model is selected; ``segment_key`` is the segment name or ``"All"``.

_PRECOMPUTED_METRICS: dict | None = None

# Fallback model for a segment selection when more than one (or zero) models
# are in scope -- e.g. the Overview page's Segments chapter, which pools every
# PD model per segment and has no single model to resolve against. When
# exactly one model is in scope (the PD Performance tab's own Segment filter,
# which now requires a model to be picked first), that model is used directly
# instead -- see ctx_store_keys.
PD_SEGMENT_HOME_MODEL = "PD Model A"


def set_precomputed_metrics(store: dict | None) -> None:
    """Install (or clear) the precomputed-metrics lookup the engine reads from."""
    global _PRECOMPUTED_METRICS
    _PRECOMPUTED_METRICS = store


def ctx_store_keys(ctx: "PdFilterContext") -> tuple[str, str]:
    """Resolve the (model, segment) the precomputed store is keyed by.

    A segment selection now refines whichever model is selected (the PD
    Performance tab's Segment filter requires a model to be chosen first, and
    narrows its options to that model's own segments), so when exactly one
    model is in scope and a real segment is chosen, both are used together.
    When zero or more-than-one models are in scope with a real segment (e.g.
    the Overview page's Segments chapter, which pools every PD model per
    segment), fall back to :data:`PD_SEGMENT_HOME_MODEL` as before.

    Public (not just used by :func:`precomputed_row`): callers that need to
    write back to the same row a read resolved -- e.g. saving an edited
    review-flow RAG to the portfolio file -- reuse this so the write always
    targets the exact row the read came from.
    """
    models = sorted(m for m in ctx.models if m)
    if ctx.segment and ctx.segment != "all":
        if len(models) == 1:
            return models[0], ctx.segment
        return PD_SEGMENT_HOME_MODEL, ctx.segment
    if models:
        return models[0], "All"
    return "", "All"


def precomputed_row(ctx: "PdFilterContext", quarter, horizon_key):
    """Return the precomputed sheet row for ``(ctx, quarter, horizon)`` or ``None``."""
    if _PRECOMPUTED_METRICS is None:
        return None
    model, segment = ctx_store_keys(ctx)
    return _PRECOMPUTED_METRICS.get((model, segment, quarter, horizon_key))


def _row_to_rag_metrics(row: dict) -> dict:
    """Map a precomputed sheet row to the engine's RAG-metrics dict."""
    return {
        "Observed Default Rate": row.get("observed_default_rate"),
        "Predicted Default Rate": row.get("predicted_default_rate"),
        "Actual / Expected Ratio": row.get("actual_expected_ratio"),
        "Confidence Interval Test": row.get("confidence_interval_test"),
        "Accuracy Ratio": row.get("accuracy_ratio"),
        "Go Live Accuracy Ratio": row.get("go_live_accuracy_ratio"),
        "Go Live Quarter": row.get("go_live_quarter") or "",
        "Delta Accuracy Ratio": row.get("delta_accuracy_ratio"),
        "Gini Coefficient": row.get("gini_coefficient"),
        "KS Statistic": row.get("ks_statistic"),
        "Brier Score": row.get("brier_score"),
        "Population Stability Index": row.get("population_stability_index"),
        "Rating Migration Index": row.get("rating_migration_index"),
        "Notching Test": row.get("notching_test_abs"),
        "Kendall's Tau": row.get("kendall_tau"),
    }


# ---------------------------------------------------------------------------
# Quarter helpers (getPreviousPdQuarter / shiftMonitoringQuarterYear)
# ---------------------------------------------------------------------------

_QUARTER_RE = re.compile(r"^(\d{4})Q([1-4])$")


def get_previous_pd_quarter(quarter):
    match = _QUARTER_RE.match(quarter or "")
    if not match:
        return ""
    year = int(match.group(1))
    quarter_number = int(match.group(2))
    return f"{year - 1}Q4" if quarter_number == 1 else f"{year}Q{quarter_number - 1}"


def get_pd_quarter_years_back(quarter, years):
    """The same calendar quarter ``years`` years earlier ("2025Q2", 1 ->
    "2024Q2"). Returns "" for anything that is not a ``YYYYQn`` quarter (e.g.
    the "No monitoring point" placeholder), so callers can fall back."""
    match = _QUARTER_RE.match(quarter or "")
    if not match:
        return ""
    return f"{int(match.group(1)) - int(years)}Q{match.group(2)}"


# ---------------------------------------------------------------------------
# Performance context (getPdPerformanceHorizonKey / getPdPerformanceContext*)
# ---------------------------------------------------------------------------


def get_pd_performance_horizon_key(ctx: PdFilterContext) -> str:
    # The original page's MONITORING_PD_INPUT / MONITORING_TIME_HORIZON globals
    # default to 'time_horizon' / '1y' and have no UI control on the PD
    # Performance tab, so the ECL PIT PD (Chapter 1) horizon is always '1y'.
    return "1y"


def get_pd_performance_context_for_horizon(performance_horizons, horizon_key, ctx: PdFilterContext):
    horizon_years = 2 if horizon_key == "2y" else 1
    horizon = (performance_horizons or {}).get(horizon_key) or {}
    snapshot_quarter = ctx.monitoring_point
    return {
        "monitoring_point": ctx.monitoring_point,
        "horizon_key": horizon_key,
        # Length of the observation window the horizon's tests measure over --
        # drives the cards' "Snapshot range" line (see cards._snapshot_meta).
        "horizon_years": horizon_years,
        "input_label": "NCO PD 1 year" if horizon_key == "nco_1y" else "Time horizon PD",
        "horizon_label": horizon.get("label") or f"{horizon_years} year{'' if horizon_years == 1 else 's'}",
        "uses_nco_input": horizon_key == "nco_1y",
        "snapshot_quarter": snapshot_quarter,
        "previous_quarter": get_previous_pd_quarter(snapshot_quarter),
        "predicted_column": horizon.get("predicted_column")
        or ("CPD_NCO_1y" if horizon_key == "nco_1y" else f"CPD_{horizon_key}_base"),
    }


def get_pd_performance_context(performance_horizons, ctx: PdFilterContext):
    return get_pd_performance_context_for_horizon(performance_horizons, get_pd_performance_horizon_key(ctx), ctx)


# ---------------------------------------------------------------------------
# Population filters (matchesPdSelectedPopulation / filterPd*Observations*)
# ---------------------------------------------------------------------------


def matches_pd_selected_population(row, quarter, ctx: PdFilterContext):
    if row["quarter"] != quarter:
        return False
    if row["model"] not in ctx.models:
        return False
    return ctx.segment == "all" or row["segment"] == ctx.segment


def filter_pd_performance_observations_for_horizon(observations, quarter, horizon_key, ctx: PdFilterContext):
    rows = []
    for row in observations:
        if not matches_pd_selected_population(row, quarter, ctx):
            continue
        horizon = (row.get("horizons") or {}).get(horizon_key)
        if not horizon:
            continue
        new_row = dict(row)
        new_row["observed"] = horizon["observed"]
        new_row["predicted"] = horizon["predicted"]
        rows.append(new_row)
    return rows


def filter_pd_performance_observations(observations, quarter, ctx: PdFilterContext):
    return filter_pd_performance_observations_for_horizon(
        observations, quarter, get_pd_performance_horizon_key(ctx), ctx,
    )


def pd_quarters_with_data(quarters, observations, horizon_keys, ctx: PdFilterContext):
    """Restrict ``quarters`` to those where the selected model/segment actually
    has a row for at least one of ``horizon_keys`` -- otherwise a model with a
    shorter history than the reporting cycle's full quarter range pads trend
    charts with a long empty stretch before its first real data point."""
    return [
        quarter for quarter in quarters
        if any(precomputed_row(ctx, quarter, key) is not None for key in horizon_keys)
        or any(filter_pd_performance_observations_for_horizon(observations, quarter, key, ctx) for key in horizon_keys)
    ]


def filter_pd_rating_observations(observations, quarter, ctx: PdFilterContext):
    return [row for row in observations if matches_pd_selected_population(row, quarter, ctx)]


# ---------------------------------------------------------------------------
# Range / period helpers (getPdRangePeriods / filterPdPeriodsByRange / ...)
# ---------------------------------------------------------------------------


def get_pd_range_periods(quarters, max_quarter):
    return sorted({q for q in quarters if q and q <= max_quarter})


def get_pd_range_selection(range_value, periods):
    range_value = range_value or {}
    range_from = range_value.get("from", "")
    range_to = range_value.get("to", "")
    return {
        "from": range_from if range_from in periods else "",
        "to": range_to if range_to in periods else "",
    }


def filter_pd_periods_by_range(range_value, periods):
    selection = get_pd_range_selection(range_value, periods)
    return [
        period for period in periods
        if (not selection["from"] or period >= selection["from"])
        and (not selection["to"] or period <= selection["to"])
    ]


def get_pd_range_preset(range_value, periods):
    selection = get_pd_range_selection(range_value, periods)
    if not selection["from"] and not selection["to"]:
        return "all"
    last_period = periods[-1] if periods else ""
    for count in (4, 8, 12):
        first_period = periods[max(0, len(periods) - count)] if periods else ""
        if selection["from"] == first_period and selection["to"] == last_period:
            return f"last-{count}"
    return "custom"


# ---------------------------------------------------------------------------
# Core statistical metrics (calculatePdAuc / calculatePdKs / ...)
# ---------------------------------------------------------------------------


def calculate_pd_auc(rows):
    positives = sum(1 for row in rows if row["observed"] == 1)
    negatives = sum(1 for row in rows if row["observed"] == 0)
    if not positives or not negatives:
        return None

    sorted_rows = sorted(rows, key=lambda row: row["predicted"])
    positive_rank_total = 0.0
    n = len(sorted_rows)
    index = 0
    while index < n:
        end = index + 1
        while end < n and sorted_rows[end]["predicted"] == sorted_rows[index]["predicted"]:
            end += 1
        average_rank = ((index + 1) + end) / 2
        for i in range(index, end):
            if sorted_rows[i]["observed"] == 1:
                positive_rank_total += average_rank
        index = end

    return (positive_rank_total - positives * (positives + 1) / 2) / (positives * negatives)


def calculate_pd_ks(rows):
    positives = sum(1 for row in rows if row["observed"] == 1)
    negatives = sum(1 for row in rows if row["observed"] == 0)
    if not positives or not negatives:
        return None

    sorted_rows = sorted(rows, key=lambda row: row["predicted"])
    cumulative_positives = 0
    cumulative_negatives = 0
    maximum_distance = 0.0
    n = len(sorted_rows)
    index = 0
    while index < n:
        end = index + 1
        while end < n and sorted_rows[end]["predicted"] == sorted_rows[index]["predicted"]:
            end += 1
        for i in range(index, end):
            if sorted_rows[i]["observed"] == 1:
                cumulative_positives += 1
            else:
                cumulative_negatives += 1
        maximum_distance = max(
            maximum_distance,
            abs(cumulative_positives / positives - cumulative_negatives / negatives),
        )
        index = end

    return maximum_distance


def calculate_pd_performance_metrics(rows):
    if not rows:
        return {
            "observed_default_rate": None,
            "predicted_default_rate": None,
            "actual_expected_ratio": None,
            "accuracy_ratio": None,
            "gini_coefficient": None,
            "ks_statistic": None,
        }
    observed_default_rate = sum(row["observed"] for row in rows) / len(rows)
    predicted_default_rate = sum(row["predicted"] for row in rows) / len(rows)
    auc = calculate_pd_auc(rows)
    accuracy_ratio = None if auc is None else 2 * auc - 1
    return {
        "observed_default_rate": observed_default_rate,
        "predicted_default_rate": predicted_default_rate,
        "actual_expected_ratio": (observed_default_rate / predicted_default_rate) if predicted_default_rate else None,
        "accuracy_ratio": accuracy_ratio,
        "gini_coefficient": accuracy_ratio,
        "ks_statistic": calculate_pd_ks(rows),
    }


def calculate_pd_brier_score(rows):
    if not rows:
        return None
    return sum((row["observed"] - row["predicted"]) ** 2 for row in rows) / len(rows)


def calculate_pd_quantile(sorted_values, probability):
    position = (len(sorted_values) - 1) * probability
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    return lower + (upper - lower) * (position - lower_index)


def calculate_pd_psi(current_rows, previous_rows, buckets=10):
    current = [row["predicted"] for row in current_rows if is_finite_number(row["predicted"])]
    previous = [row["predicted"] for row in previous_rows if is_finite_number(row["predicted"])]
    if not current or not previous:
        return None
    if len(set(previous)) < 3:
        return 0

    sorted_previous = sorted(previous)
    breaks: list[float] = []
    for index in range(buckets + 1):
        value = calculate_pd_quantile(sorted_previous, index / buckets)
        if not breaks or value != breaks[-1]:
            breaks.append(value)
    if len(breaks) < 3:
        return 0

    def distribution(values):
        counts = [0] * (len(breaks) - 1)
        included = 0
        for value in values:
            if value < breaks[0] or value > breaks[-1]:
                continue
            bucket_index = len(breaks) - 2
            for index in range(1, len(breaks)):
                if value <= breaks[index]:
                    bucket_index = index - 1
                    break
            counts[bucket_index] += 1
            included += 1
        return [count / included for count in counts] if included else []

    current_distribution = distribution(current)
    previous_distribution = distribution(previous)
    if not current_distribution or not previous_distribution:
        return None

    total = 0.0
    for index, value in enumerate(current_distribution):
        current_share = value or 0.0001
        previous_share = previous_distribution[index] or 0.0001
        total += (current_share - previous_share) * math.log(current_share / previous_share)
    return total


def calculate_pd_rating_migration_index(observations, current_quarter, previous_quarter, ctx: PdFilterContext):
    if not previous_quarter:
        return None
    current_rows = filter_pd_rating_observations(observations, current_quarter, ctx)
    previous_rows = filter_pd_rating_observations(observations, previous_quarter, ctx)
    current_by_account = {row["account"]: _to_number(row["rating"]) for row in current_rows}
    migrations = []
    for row in previous_rows:
        current_rating = current_by_account.get(row["account"])
        previous_rating = _to_number(row["rating"])
        if current_rating is not None and previous_rating is not None:
            migrations.append(abs(current_rating - previous_rating))
    return sum(migrations) / len(migrations) if migrations else None


def calculate_pd_kendall_tau(rows):
    if len(rows) < 2:
        return None
    concordant = 0
    discordant = 0
    predicted_ties = 0
    observed_ties = 0
    n = len(rows)
    for left in range(n):
        for right in range(left + 1, n):
            predicted_delta = rows[left]["predicted"] - rows[right]["predicted"]
            observed_delta = rows[left]["observed"] - rows[right]["observed"]
            if predicted_delta == 0 and observed_delta == 0:
                continue
            if predicted_delta == 0:
                predicted_ties += 1
            elif observed_delta == 0:
                observed_ties += 1
            elif predicted_delta * observed_delta > 0:
                concordant += 1
            else:
                discordant += 1
    denominator = math.sqrt((concordant + discordant + predicted_ties) * (concordant + discordant + observed_ties))
    return (concordant - discordant) / denominator if denominator else None


# ---------------------------------------------------------------------------
# CRR master scale / notching (getPdCrrMasterScale / mapPdProbabilityToCrr / ...)
# ---------------------------------------------------------------------------


def get_pd_crr_master_scale(monitoring_thresholds):
    rows = (monitoring_thresholds or {}).get("crr_master_scale") or config.DEFAULT_PD_CRR_MASTER_SCALE
    scale = []
    for row in rows:
        crr = _to_number(_first_present(row, "crr", "CRR"))
        min_pd = _to_number(_first_present(row, "min_pd", "Min PD"))
        max_pd = _to_number(_first_present(row, "max_pd", "Max PD"))
        if crr is None or min_pd is None or max_pd is None:
            continue
        scale.append({"crr": crr, "min_pd": min_pd, "max_pd": max_pd})
    return sorted(scale, key=lambda row: (row["min_pd"], row["crr"]))


def map_pd_probability_to_crr(probability, crr_scale):
    if probability is None or not math.isfinite(probability):
        return None
    if not crr_scale:
        return None
    if probability <= crr_scale[0]["min_pd"]:
        return crr_scale[0]["crr"]

    for index, row in enumerate(crr_scale):
        is_last = index == len(crr_scale) - 1
        next_min = crr_scale[index + 1]["min_pd"] if not is_last else row["max_pd"]
        if probability >= row["min_pd"] and (probability < next_min or (is_last and probability <= row["max_pd"])):
            return row["crr"]
    return crr_scale[-1]["crr"]


def calculate_pd_notching_components(rows, crr_scale):
    empty = {"actual_notch": None, "predicted_notch": None, "signed_difference": None, "difference": None}
    if not rows:
        return dict(empty)

    predicted = [row["predicted"] for row in rows if is_finite_number(row["predicted"])]
    observed = [row["observed"] for row in rows if is_finite_number(row["observed"])]
    if not predicted or not observed:
        return dict(empty)

    average_predicted = sum(predicted) / len(predicted)
    average_observed = sum(observed) / len(observed)
    predicted_notch = map_pd_probability_to_crr(average_predicted, crr_scale)
    actual_notch = map_pd_probability_to_crr(average_observed, crr_scale)
    if not is_finite_number(predicted_notch) or not is_finite_number(actual_notch):
        return dict(empty)

    return {
        "actual_notch": actual_notch,
        "predicted_notch": predicted_notch,
        "signed_difference": predicted_notch - actual_notch,
        "difference": abs(predicted_notch - actual_notch),
    }


def calculate_pd_notching_test(rows, crr_scale):
    return calculate_pd_notching_components(rows, crr_scale)["difference"]


def precomputed_notching_components(ctx: "PdFilterContext", quarter, horizon_key, crr_scale):
    """Notching components built from the precomputed sheet row (or ``None``).

    The signed and absolute notch differences come straight from the sheet;
    the individual actual/predicted notch grades are a deterministic CRR lookup
    of the observed/predicted default rates for display.
    """
    row = precomputed_row(ctx, quarter, horizon_key)
    if row is None:
        return None
    predicted_dr = row.get("predicted_default_rate")
    observed_dr = row.get("observed_default_rate")
    return {
        "actual_notch": map_pd_probability_to_crr(observed_dr, crr_scale) if observed_dr is not None else None,
        "predicted_notch": map_pd_probability_to_crr(predicted_dr, crr_scale) if predicted_dr is not None else None,
        "signed_difference": row.get("notching_test_signed"),
        "difference": row.get("notching_test_abs"),
    }


def get_pd_confidence_interval_bucket(value):
    if value is None or not math.isfinite(value):
        return ""
    if value < 0.05:
        return "p_low"
    if value <= 0.90:
        return "p_mid"
    if value <= 0.975:
        return "p_high"
    return "p_very_high"


def get_pd_notching_bucket(value):
    if value is None or not math.isfinite(value):
        return ""
    if value > 2:
        return ">2"
    if abs(value - 2) < 1e-9:
        return "+2"
    if value < -2:
        return "<-2"
    if abs(value + 2) < 1e-9:
        return "-2"
    return "0 to +/-1"


def get_pd_rag_assignment(monitoring_thresholds):
    rows = (monitoring_thresholds or {}).get("rag_assignment_pd") or config.DEFAULT_PD_RAG_ASSIGNMENT
    mapped = []
    for row in rows:
        bucket = str(_first_present(row, "notching_bucket", "Notching Test") or "").strip()
        if not bucket:
            continue
        mapped.append({
            "notching_bucket": bucket,
            "p_low": _first_present(row, "p<5%", "p_lt_5", "p_low"),
            "p_mid": _first_present(row, "5%<=p<=90%", "p_5_to_90", "p_mid"),
            "p_high": _first_present(row, "90%<p<=97.5%", "p_90_to_975", "p_high"),
            "p_very_high": _first_present(row, "p>97.5%", "p_gt_975", "p_very_high"),
        })
    return mapped


def calculate_pd_calibration_assignment_rag(confidence_interval, signed_notching_difference, monitoring_thresholds):
    confidence_bucket = get_pd_confidence_interval_bucket(confidence_interval)
    notching_bucket = get_pd_notching_bucket(signed_notching_difference)
    if not confidence_bucket or not notching_bucket:
        return "N/A"
    row = next(
        (entry for entry in get_pd_rag_assignment(monitoring_thresholds) if entry["notching_bucket"] == notching_bucket),
        None,
    )
    rag = row.get(confidence_bucket) if row else ""
    return str(rag).strip() if rag else "N/A"


# ---------------------------------------------------------------------------
# Confidence interval (hashPdSeed / calculatePdConfidenceInterval*)
# ---------------------------------------------------------------------------


def hash_pd_seed(value):
    """FNV-1a hash, port of ``hashPdSeed``."""
    hash_value = 2166136261
    for char in str(value):
        hash_value ^= ord(char)
        hash_value = (hash_value * 16777619) & 0xFFFFFFFF
    return hash_value


def calculate_pd_confidence_interval_components(rows):
    empty = {
        "actual_confidence_interval": None,
        "predicted_confidence_interval": None,
        "confidence_interval": None,
        "difference": None,
    }
    if not rows:
        return dict(empty)

    predicted = [row["predicted"] for row in rows if is_finite_number(row["predicted"])]
    observed = [row["observed"] for row in rows if is_finite_number(row["observed"])]
    if not predicted or not observed:
        return dict(empty)

    average_predicted = sum(predicted) / len(predicted)
    average_observed = sum(observed) / len(observed)
    predicted_std = (
        math.sqrt(sum((value - average_predicted) ** 2 for value in predicted) / len(predicted))
        if len(predicted) > 1 else 0
    )
    observed_std = (
        math.sqrt(sum((value - average_observed) ** 2 for value in observed) / len(observed))
        if len(observed) > 1 else 0
    )
    seed = "|".join([
        str(len(rows)),
        f"{average_predicted:.6f}",
        f"{average_observed:.6f}",
        f"{predicted_std:.6f}",
        f"{observed_std:.6f}",
    ])
    normalized = hash_pd_seed(seed) / 4294967295
    spread = min(0.22, 0.04 + abs(average_predicted - average_observed) * 2 + (predicted_std + observed_std) * 0.5)
    actual_confidence_interval = min(1, normalized + spread / 2)
    predicted_confidence_interval = max(0, normalized - spread / 2)

    return {
        "actual_confidence_interval": actual_confidence_interval,
        "predicted_confidence_interval": predicted_confidence_interval,
        "confidence_interval": normalized,
        "difference": abs(actual_confidence_interval - predicted_confidence_interval),
    }


def calculate_pd_confidence_interval(rows):
    return calculate_pd_confidence_interval_components(rows)["confidence_interval"]


# ---------------------------------------------------------------------------
# Thresholds & rules (getPdThresholds / matchesPdThresholdRule / ...)
# ---------------------------------------------------------------------------


def get_pd_thresholds(monitoring_thresholds):
    thresholds = list((monitoring_thresholds or {}).get("pd_thresholds") or [])
    if not any(row.get("metric") == "Confidence Interval" for row in thresholds):
        thresholds.append(config.DEFAULT_PD_CONFIDENCE_INTERVAL_THRESHOLD)
    return thresholds


def get_pd_threshold_metric_name(metric):
    return config.PD_THRESHOLD_METRIC_ALIASES.get(metric, metric)


_RANGE_RULE = re.compile(r"^(-?\d*\.?\d+)\s*(<=|<)\s*value\s*(<=|<)\s*(-?\d*\.?\d+)$", re.IGNORECASE)
_VALUE_OP_RULE = re.compile(r"^value\s*(>=|>|<=|<)\s*(-?\d*\.?\d+)$", re.IGNORECASE)
_THRESHOLD_OP_VALUE_RULE = re.compile(r"^(-?\d*\.?\d+)\s*(>=|>)\s*value$", re.IGNORECASE)


def matches_pd_threshold_rule(rule, value):
    if not rule or value is None or not math.isfinite(value):
        return False
    for part in re.split(r"\s+OR\s+", str(rule), flags=re.IGNORECASE):
        clause = part.strip()
        if not clause:
            continue

        match = _RANGE_RULE.match(clause)
        if match:
            lower = float(match.group(1))
            lower_op = match.group(2)
            upper_op = match.group(3)
            upper = float(match.group(4))
            lower_pass = value >= lower if lower_op == "<=" else value > lower
            upper_pass = value <= upper if upper_op == "<=" else value < upper
            if lower_pass and upper_pass:
                return True
            continue

        match = _VALUE_OP_RULE.match(clause)
        if match:
            op = match.group(1)
            threshold = float(match.group(2))
            if op == ">=" and value >= threshold:
                return True
            if op == ">" and value > threshold:
                return True
            if op == "<=" and value <= threshold:
                return True
            if op == "<" and value < threshold:
                return True
            continue

        match = _THRESHOLD_OP_VALUE_RULE.match(clause)
        if match:
            threshold = float(match.group(1))
            op = match.group(2)
            if op == ">=" and value <= threshold:
                return True
            if op == ">" and value < threshold:
                return True
    return False


_VALUE_UPPER_RULE = re.compile(r"value\s*(?:<=|<)\s*(-?\d*\.?\d+)", re.IGNORECASE)
_VALUE_LOWER_RULE = re.compile(r"value\s*(?:>=|>)\s*(-?\d*\.?\d+)", re.IGNORECASE)
_RANGE_RULE_LOOSE = re.compile(r"(-?\d*\.?\d+)\s*(?:<=|<)\s*value\s*(?:<=|<)\s*(-?\d*\.?\d+)", re.IGNORECASE)


def extract_pd_rule_upper_bound(rule):
    if not rule:
        return None
    text = str(rule).strip()
    match = _VALUE_UPPER_RULE.search(text)
    if match:
        return float(match.group(1))
    match = _RANGE_RULE_LOOSE.search(text)
    if match:
        return float(match.group(2))
    return None


def extract_pd_rule_lower_bound(rule):
    if not rule:
        return None
    text = str(rule).strip()
    match = _VALUE_LOWER_RULE.search(text)
    if match:
        return float(match.group(1))
    match = _RANGE_RULE_LOOSE.search(text)
    if match:
        return float(match.group(1))
    return None


def calculate_pd_metric_rag(thresholds, metric, value):
    if value is None or not math.isfinite(value):
        return "N/A"

    metric_name = get_pd_threshold_metric_name(metric)
    threshold = next((row for row in thresholds if row.get("metric") == metric_name), None)
    if threshold is None:
        return "N/A"

    red_condition = threshold.get("red_condition")

    if red_condition == "no_rag":
        return "Green"

    if red_condition == "outside amber range":
        if _ge(value, threshold.get("green_min")) and _le(value, threshold.get("green_max")):
            return "Green"
        if _ge(value, threshold.get("amber_min")) and _le(value, threshold.get("amber_max")):
            return "Amber"
        return "Red"

    if red_condition == "below amber_min":
        if _ge(value, threshold.get("green_min")):
            return "Green"
        if _ge(value, threshold.get("amber_min")):
            return "Amber"
        return "Red"

    if red_condition == "above amber_max":
        if _le(value, threshold.get("green_max")):
            return "Green"
        if _le(value, threshold.get("amber_max")):
            return "Amber"
        return "Red"

    if red_condition == "abs above amber_max":
        green_max = threshold.get("green_max")
        amber_max = threshold.get("amber_max")
        abs_value = abs(value)
        if _le(abs_value, abs(green_max) if green_max is not None else None):
            return "Green"
        if _le(abs_value, abs(amber_max) if amber_max is not None else None):
            return "Amber"
        return "Red"

    if matches_pd_threshold_rule(threshold.get("green_rule"), value):
        return "Green"
    if matches_pd_threshold_rule(threshold.get("amber_rule"), value):
        return "Amber"
    if matches_pd_threshold_rule(threshold.get("red_rule"), value):
        return "Red"
    return "N/A"


# ---------------------------------------------------------------------------
# RAG metric aggregation (getPdGoLiveQuarter / calculatePdRagMetrics* / ...)
# ---------------------------------------------------------------------------


def get_pd_go_live_quarter(performance_observations, horizon_key, ctx: PdFilterContext):
    # Try the precomputed store first — go_live_quarter is stored on every row.
    if _PRECOMPUTED_METRICS is not None:
        for quarter in ctx.quarters:
            row = precomputed_row(ctx, quarter, horizon_key)
            if row and row.get("go_live_quarter"):
                return str(row["go_live_quarter"])

    go_live_quarters = sorted(
        {
            quarter for quarter in ctx.quarters
            if quarter and config.PD_GO_LIVE_QUARTER_START <= quarter <= config.PD_GO_LIVE_QUARTER_END
        },
        reverse=True,
    )
    for quarter in go_live_quarters:
        rows = filter_pd_performance_observations_for_horizon(performance_observations, quarter, horizon_key, ctx)
        accuracy_ratio = calculate_pd_performance_metrics(rows)["accuracy_ratio"]
        if is_finite_number(accuracy_ratio):
            return quarter
    return ""


def calculate_pd_rag_metrics_for_horizon(performance_observations, rating_observations, quarter, horizon_key, ctx: PdFilterContext, crr_scale):
    row = precomputed_row(ctx, quarter, horizon_key)
    if row is not None:
        return _row_to_rag_metrics(row)

    previous_quarter = get_previous_pd_quarter(quarter)
    current_rows = filter_pd_performance_observations_for_horizon(performance_observations, quarter, horizon_key, ctx)
    previous_rows = filter_pd_performance_observations_for_horizon(performance_observations, previous_quarter, horizon_key, ctx)
    go_live_quarter = get_pd_go_live_quarter(performance_observations, horizon_key, ctx)
    go_live_rows = (
        filter_pd_performance_observations_for_horizon(performance_observations, go_live_quarter, horizon_key, ctx)
        if go_live_quarter else []
    )

    metrics = calculate_pd_performance_metrics(current_rows)
    go_live_metrics = calculate_pd_performance_metrics(go_live_rows)
    go_live_accuracy_ratio = go_live_metrics["accuracy_ratio"]
    accuracy_ratio = metrics["accuracy_ratio"]

    delta_accuracy_ratio = None
    if (
        is_finite_number(go_live_accuracy_ratio) and is_finite_number(accuracy_ratio)
        and go_live_accuracy_ratio != 0
    ):
        delta_accuracy_ratio = (go_live_accuracy_ratio - accuracy_ratio) / go_live_accuracy_ratio

    return {
        "Observed Default Rate": metrics["observed_default_rate"],
        "Predicted Default Rate": metrics["predicted_default_rate"],
        "Actual / Expected Ratio": metrics["actual_expected_ratio"],
        "Confidence Interval Test": calculate_pd_confidence_interval(current_rows),
        "Accuracy Ratio": accuracy_ratio,
        "Go Live Accuracy Ratio": go_live_accuracy_ratio,
        "Go Live Quarter": go_live_quarter,
        "Delta Accuracy Ratio": delta_accuracy_ratio,
        "Gini Coefficient": metrics["gini_coefficient"],
        "KS Statistic": metrics["ks_statistic"],
        "Brier Score": calculate_pd_brier_score(current_rows),
        "Population Stability Index": calculate_pd_psi(current_rows, previous_rows),
        "Rating Migration Index": calculate_pd_rating_migration_index(rating_observations, quarter, previous_quarter, ctx),
        "Notching Test": calculate_pd_notching_test(current_rows, crr_scale),
        "Kendall's Tau": calculate_pd_kendall_tau(current_rows),
    }


def calculate_pd_rag_metrics(performance_observations, rating_observations, quarter, ctx: PdFilterContext, crr_scale):
    horizon_key = get_pd_performance_horizon_key(ctx)
    return calculate_pd_rag_metrics_for_horizon(performance_observations, rating_observations, quarter, horizon_key, ctx, crr_scale)


def calculate_pd_default_count_for_horizon(performance_observations, quarter, horizon_key, ctx: PdFilterContext):
    if not quarter:
        return 0
    precomp = precomputed_row(ctx, quarter, horizon_key)
    if precomp is not None:
        # ``total_defaults`` is the authoritative per-horizon default count from
        # the ``PD_Performance_Metrics`` sheet (the loader only synthesises the
        # legacy ``default_count_1y`` for the 1y row, so non-1y horizons -- e.g.
        # Balance Sheet ``nco_1y`` -- must read ``total_defaults`` directly).
        count = precomp.get("total_defaults")
        if count is None:
            count = precomp.get("default_count_1y")
        return int(count) if count is not None else 0
    rows = filter_pd_performance_observations_for_horizon(performance_observations, quarter, horizon_key, ctx)
    return sum(1 for row in rows if row["observed"] == 1)


# ---------------------------------------------------------------------------
# Section RAGs (getWorstPdRag / calculatePdDiscriminationSectionRag / ...)
# ---------------------------------------------------------------------------


def get_worst_pd_rag(rags):
    scores = {"N/A": 0, "Green": 1, "Amber": 2, "Red": 3}
    worst = "N/A"
    for rag in rags:
        if scores.get(rag, 0) > scores.get(worst, 0):
            worst = rag
    return worst


_FALLBACK_LOW_DEFAULT_THRESHOLD = 15


def _norm_fallback_text(value) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def resolve_fallback_rule(fallback_rules, model_type: str, component: str, test: str, default_count) -> tuple[str, str]:
    """Resolve the RAG-Assignment fallback for a single test.

    Reads the ``fallback_amber_rules`` workbook sheet (passed in as its list of
    row-dicts, loaded dynamically -- see ``load_monitoring_thresholds`` -- so the
    rules can change in the file without a code change) and returns
    ``(status, note)`` where ``status`` is one of:

      * ``"applicable"``     -- the test's normal calculation stands (note "").
      * ``"fallback_amber"`` -- the test is forced to Amber (low default count).
      * ``"non_applicable"`` -- the test is not calculated / excluded from its
        dimension RAG.

    The rule is matched by ``(Model Type, Component, Test)`` and keyed on the
    default count: fewer than 15 -> the ``"< 15 Defaults"`` column, otherwise
    ``">= 15 Defaults"``. Any unmatched test (or missing/non-finite default
    count) is treated as ``"applicable"``. The sheet carries PD, LGD and EAD
    rules; ``model_type`` selects which set applies.
    """
    if default_count is None or not math.isfinite(default_count):
        return "applicable", ""
    threshold = _FALLBACK_LOW_DEFAULT_THRESHOLD
    is_low = default_count < threshold
    bucket = "< 15 Defaults" if is_low else ">= 15 Defaults"
    # e.g. "8 defaults (< 15)" -- surfaces how far the count is from the threshold.
    count = int(default_count)
    count_text = f"{count} default{'' if count == 1 else 's'} ({'<' if is_low else '≥'} {threshold})"
    model_type_n = _norm_fallback_text(model_type)
    component_n, test_n = _norm_fallback_text(component), _norm_fallback_text(test)
    for row in fallback_rules or []:
        if (
            _norm_fallback_text(row.get("Model Type")) == model_type_n
            and _norm_fallback_text(row.get("Component")) == component_n
            and _norm_fallback_text(row.get("Test")) == test_n
        ):
            action = _norm_fallback_text(row.get(bucket))
            # Both low-default outcomes carry the same note: it names the rule
            # that fired, not that rule's effect on this particular test. What
            # separates them is the RAG each one resolves to (Amber vs N/A),
            # which the card and flow node already show alongside the note.
            if action in ("fallback amber", "non-applicable"):
                status = "fallback_amber" if action == "fallback amber" else "non_applicable"
                return status, f"Fallback Amber applied — {count_text}"
            return "applicable", ""
    return "applicable", ""


# LGD/EAD metric key -> the "Test" name its fallback rule is filed under in the
# workbook. Both model types use the same three tests, each filed with Component
# equal to the model type itself ("LGD" / "EAD"). The sheet's two remaining rows
# per model type ("Change of discriminatory power over time", "12 months ... for
# past quarters") are Applicable in both default buckets, so they are no-ops with
# no card to attach to.
_METRIC_FALLBACK_TESTS = {
    "ME": "Mean Error 1 year",
    "RMSE": "RMSE 1 year",
    "Kendall's Tau": "Kendall's Tau 1 year",
}


def resolve_metric_fallback(fallback_rules, model_type: str, metric: str, default_count) -> tuple[str, str]:
    """``(status, note)`` for one LGD/EAD metric card -- the model-type-keyed
    equivalent of the PD call in ``_fallback_options``. Metrics with no rule of
    their own (e.g. Population Stability Index) are always Applicable."""
    test = _METRIC_FALLBACK_TESTS.get(metric)
    if not test:
        return "applicable", ""
    return resolve_fallback_rule(fallback_rules, model_type, model_type, test, default_count)


def apply_metric_fallback_rag(fallback_rules, model_type: str, metric: str, default_count, rag):
    """A metric's RAG with its LGD/EAD fallback applied -- forced to Amber on a
    low default count so the fallback flows into the dimension RAGs the same way
    it does for PD (the workbook's "Monitoring Dimension RAG" column names the
    dimension each test rolls into). Returns ``rag`` unchanged when Applicable."""
    status, _ = resolve_metric_fallback(fallback_rules, model_type, metric, default_count)
    return "Amber" if status in ("fallback_amber", "non_applicable") else rag


def _apply_fallback_to_trend_metric(fallback_rules, test, default_count, rag, value):
    """For a trend row: apply a test's Chapter-1 fallback (component ``ECL PIT
    PD``) to its ``(rag, value)`` pair -- forcing the RAG (Amber / N/A) and
    suppressing the value to ``None`` so no misleading number is plotted. Returns
    the pair unchanged when the test is Applicable."""
    status, _ = resolve_fallback_rule(fallback_rules, "PD", "ECL PIT PD", test, default_count)
    if status == "fallback_amber":
        return "Amber", None
    if status == "non_applicable":
        return "N/A", None
    return rag, value


def calibration_assignment_rag_with_fallback(
    confidence_interval,
    signed_notching_difference,
    monitoring_thresholds,
    fallback_rules=None,
    component=None,
    notching_test=None,
    default_count=None,
):
    """RAG Assignment for one calibration horizon, honoring the Non-Applicable
    Notching fallback. When the notching test resolves to ``"non_applicable"``
    (low default count -- see :func:`resolve_fallback_rule`) the Notching Test
    is excluded and the RAG Assignment reduces to the Confidence Interval Test
    RAG alone; otherwise the standard 2D (Confidence x Notching) lookup applies.
    With no fallback rule supplied this is exactly
    :func:`calculate_pd_calibration_assignment_rag`."""
    if fallback_rules and component and notching_test:
        status, _ = resolve_fallback_rule(fallback_rules, "PD", component, notching_test, default_count)
        if status == "non_applicable":
            thresholds = get_pd_thresholds(monitoring_thresholds)
            return calculate_pd_metric_rag(thresholds, "Confidence Interval Test", confidence_interval)
    return calculate_pd_calibration_assignment_rag(
        confidence_interval, signed_notching_difference, monitoring_thresholds,
    )


def calculate_pd_discrimination_section_rag(thresholds, values, default_count_1y=None):
    accuracy_rag = calculate_pd_metric_rag(thresholds, "Accuracy Ratio", values.get("Accuracy Ratio"))
    if accuracy_rag == "N/A":
        # No Accuracy Ratio at all means no data for this scope -- distinct
        # from a real low-default-count caution, which requires data to exist
        # in the first place (see calculate_pd_default_count_for_horizon,
        # which returns 0 -- "finite and < 15" -- for a missing precomputed
        # row just as readily as for a genuinely low-default population).
        return "N/A"
    if default_count_1y is not None and math.isfinite(default_count_1y) and default_count_1y < 15:
        return "Amber"
    delta_accuracy_rag = calculate_pd_metric_rag(thresholds, "Delta Accuracy Ratio", values.get("Delta Accuracy Ratio"))
    if delta_accuracy_rag == "Red" and accuracy_rag == "Green":
        return "Amber"
    if delta_accuracy_rag == "Red" and accuracy_rag == "Amber":
        return "Red"
    return accuracy_rag


def calculate_pd_overview_performance_rag(calibration_rag, discrimination_rag, balance_sheet_rag):
    components = [
        (calibration_rag, 0.25),
        (discrimination_rag, 0.25),
        (balance_sheet_rag, 0.50),
    ]
    scores = [pd_rag_score(rag) for rag, _ in components]
    if any(score is None for score in scores):
        return {"rag": "N/A", "weighted_score": None, "rounded_score": None}
    weighted_score = sum(score * weight for score, (_, weight) in zip(scores, components))
    rounded_score = round_pd_half_down(weighted_score)
    return {"rag": pd_score_to_rag(rounded_score), "weighted_score": weighted_score, "rounded_score": rounded_score}


def build_pd_overview_performance_rag_tooltip(calibration_rag, discrimination_rag, balance_sheet_rag, details):
    def score_label(rag):
        score = pd_rag_score(rag)
        return "—" if score is None else f"{score}"

    component_summary = "; ".join([
        f"ECL PIT Calibration: {calibration_rag} ({score_label(calibration_rag)}) x 25%",
        f"ECL PIT Discriminatory Power: {discrimination_rag} ({score_label(discrimination_rag)}) x 25%",
        f"Balance Sheet Calibration: {balance_sheet_rag} ({score_label(balance_sheet_rag)}) x 50%",
    ])
    weighted_score = details.get("weighted_score")
    rounded_score = details.get("rounded_score")
    weighted_label = "—" if not is_finite_number(weighted_score) else f"{weighted_score:.2f}"
    rounded_label = "—" if not is_finite_number(rounded_score) else f"{rounded_score}"

    if not is_finite_number(weighted_score) or not is_finite_number(rounded_score):
        return (
            "Performance RAG combines three inputs with weights of 25%, 25%, and 50%. Higher scores are better: "
            f"Green = 3, Amber = 2, Red = 1. Current inputs: {component_summary}. One or more inputs are unavailable, "
            f"so the displayed Performance RAG is {details['rag']}."
        )
    return (
        "Performance RAG combines three inputs with weights of 25%, 25%, and 50%. Higher scores are better: "
        f"Green = 3, Amber = 2, Red = 1. Current inputs: {component_summary}. Weighted average score: {weighted_label}. "
        f"Rounded score: {rounded_label}. Displayed Performance RAG: {details['rag']}."
    )


# ---------------------------------------------------------------------------
# EAD summaries (calculatePdEadSummaries)
# ---------------------------------------------------------------------------


def calculate_pd_ead_summaries(observations, quarter, ctx: PdFilterContext):
    empty = {
        "1y": {"ead": None, "share": None, "combined_ead": None},
        "2y": {"ead": None, "share": None, "combined_ead": None},
    }

    row_1y = precomputed_row(ctx, quarter, "1y")
    row_2y = precomputed_row(ctx, quarter, "2y")
    if row_1y is not None or row_2y is not None:
        ead_1y = (row_1y or {}).get("ead") or 0.0
        ead_2y = (row_2y or {}).get("ead") or 0.0
        combined_ead = ead_1y + ead_2y

        def summary(ead):
            return {
                "ead": ead if ead else None,
                "share": (ead / combined_ead) if combined_ead > 0 else None,
                "combined_ead": combined_ead if combined_ead > 0 else None,
            }

        return {"1y": summary(ead_1y), "2y": summary(ead_2y)}

    selected_rows = [row for row in observations if matches_pd_selected_population(row, quarter, ctx)]
    if not selected_rows:
        return empty

    def sum_ead_for_horizon(key):
        total = 0.0
        for row in selected_rows:
            value = (row.get("horizons") or {}).get(key, {}).get("ead")
            if is_finite_number(value):
                total += value
        return total

    ead_1y = sum_ead_for_horizon("1y")
    ead_2y = sum_ead_for_horizon("2y")
    combined_ead = ead_1y + ead_2y

    def summary(ead):
        return {
            "ead": ead if math.isfinite(ead) else None,
            "share": (ead / combined_ead) if combined_ead > 0 and math.isfinite(ead) else None,
            "combined_ead": combined_ead if combined_ead > 0 else None,
        }

    return {"1y": summary(ead_1y), "2y": summary(ead_2y)}


# ---------------------------------------------------------------------------
# Calibration conservatism (calculatePdCalibrationConservatism* / tooltips)
# ---------------------------------------------------------------------------


def calculate_pd_calibration_conservatism_details(observations, rating_observations, monitoring_quarter, ctx: PdFilterContext, crr_scale, monitoring_thresholds, fallback_rules=None):
    if not monitoring_quarter:
        return {"rag": "N/A", "weighted_average": None, "rounded_score": None, "horizons": [], "total_weight": 0}

    ead_summaries = calculate_pd_ead_summaries(observations, monitoring_quarter, ctx)
    weighted_scores = []
    for horizon_key in ("1y", "2y"):
        snapshot_quarter = monitoring_quarter

        precomp = precomputed_row(ctx, snapshot_quarter, horizon_key)
        if precomp is not None:
            confidence_interval = precomp.get("confidence_interval_test")
            signed_notch = precomp.get("notching_test_signed")
            weight = precomp.get("ead_share")
        else:
            horizon_values = calculate_pd_rag_metrics_for_horizon(
                observations, rating_observations, snapshot_quarter, horizon_key, ctx, crr_scale,
            )
            horizon_notching = calculate_pd_notching_components(
                filter_pd_performance_observations_for_horizon(observations, snapshot_quarter, horizon_key, ctx),
                crr_scale,
            )
            confidence_interval = horizon_values["Confidence Interval Test"]
            signed_notch = horizon_notching["signed_difference"]
            weight = (ead_summaries.get(horizon_key) or {}).get("share")

        default_count = calculate_pd_default_count_for_horizon(observations, snapshot_quarter, horizon_key, ctx)
        notching_test = "Notching Test 1 year" if horizon_key == "1y" else "Notching Test 2 year"
        rag = calibration_assignment_rag_with_fallback(
            confidence_interval, signed_notch, monitoring_thresholds,
            fallback_rules=fallback_rules, component="ECL PIT PD",
            notching_test=notching_test, default_count=default_count,
        )
        score = pd_rag_score(rag)
        if score is not None and is_finite_number(weight):
            weighted_scores.append({"key": horizon_key, "score": score, "weight": weight, "rag": rag})

    if not weighted_scores:
        return {"rag": "N/A", "weighted_average": None, "rounded_score": None, "horizons": [], "total_weight": 0}

    total_weight = sum(entry["weight"] for entry in weighted_scores)
    if total_weight > 0:
        weighted_average = sum(entry["score"] * entry["weight"] for entry in weighted_scores) / total_weight
    else:
        weighted_average = sum(entry["score"] for entry in weighted_scores) / len(weighted_scores)
    rounded_score = round_pd_half_down(weighted_average)

    return {
        "rag": pd_score_to_rag(rounded_score),
        "weighted_average": weighted_average,
        "rounded_score": rounded_score,
        "horizons": weighted_scores,
        "total_weight": total_weight,
    }


def build_pd_calibration_tooltip(details):
    if not details or not details.get("horizons"):
        return (
            "Calibration Conservatism RAG (ECL PIT) combines the 1-year and 2-year RAG Assignment results "
            "using EAD share weights. Higher scores are better: Green = 3, Amber = 2, Red = 1. The required "
            "inputs are unavailable for the current filtered population."
        )

    pieces = "; ".join(
        f"{'1-year RAG Assignment' if entry['key'] == '1y' else '2-year RAG Assignment'}: "
        f"{entry['rag']} ({entry['score']}) x {entry['weight'] * 100:.1f}%"
        for entry in details["horizons"]
    )
    weighted_average = details.get("weighted_average")
    rounded_score = details.get("rounded_score")
    weighted_label = "—" if not is_finite_number(weighted_average) else f"{weighted_average:.2f}"
    rounded_label = "—" if not is_finite_number(rounded_score) else f"{rounded_score}"

    if not is_finite_number(weighted_average) or not is_finite_number(rounded_score):
        return (
            "Calibration Conservatism RAG (ECL PIT) combines the 1-year and 2-year RAG Assignment results "
            f"using EAD share weights. Higher scores are better: Green = 3, Amber = 2, Red = 1. Current inputs: {pieces}. "
            f"One or more inputs are unavailable, so the displayed Calibration Conservatism RAG is {details['rag']}."
        )
    return (
        "Calibration Conservatism RAG (ECL PIT) combines the 1-year and 2-year RAG Assignment results "
        f"using EAD share weights. Higher scores are better: Green = 3, Amber = 2, Red = 1. Current inputs: {pieces}. "
        f"Weighted average score: {weighted_label}. Rounded score: {rounded_label}. Displayed Calibration "
        f"Conservatism RAG: {details['rag']}."
    )


def format_pd_confidence_bucket_label(bucket):
    return {
        "p_low": "p < 5%",
        "p_mid": "5% <= p <= 90%",
        "p_high": "90% < p <= 97.5%",
        "p_very_high": "p > 97.5%",
    }.get(bucket, "—")


def format_pd_signed_notching_label(value):
    if value is None or not math.isfinite(value):
        return "—"
    rounded = round(value)
    return f"+{rounded}" if rounded > 0 else f"{rounded}"


def build_pd_calibration_assignment_tooltip(label, confidence_interval, signed_notching_difference, lookup_rag, displayed_rag, confidence_rag, notching_rag):
    confidence_bucket = get_pd_confidence_interval_bucket(confidence_interval)
    notching_bucket = get_pd_notching_bucket(signed_notching_difference)
    lookup_label = lookup_rag or "N/A"
    fallback_active = lookup_label == "N/A" and displayed_rag and displayed_rag != "N/A"
    if fallback_active:
        fallback_text = (
            f" The lookup result is unavailable, so the card falls back to the worse of Confidence Interval Test "
            f"({confidence_rag or 'N/A'}) and Notching Test ({notching_rag or 'N/A'}): {displayed_rag}."
        )
    else:
        fallback_text = f" Displayed RAG: {displayed_rag or 'N/A'}."

    if not confidence_bucket or not notching_bucket:
        return (
            f"RAG Assignment {label} is determined from a lookup table using the Confidence Interval Test bucket "
            "and the signed notch difference bucket (predicted notch minus actual notch). The signed notch "
            "difference is not the same as the absolute Notching Test shown in the KPI card. One or more current "
            f"inputs are unavailable, so the direct lookup result is {lookup_label}.{fallback_text}"
        )

    return (
        f"RAG Assignment {label} is determined from a lookup table using the Confidence Interval Test bucket "
        "and the signed notch difference bucket (predicted notch minus actual notch). The signed notch "
        "difference is not the same as the absolute Notching Test shown in the KPI card. Current inputs: "
        f"Confidence Interval: {format_pd_metric(confidence_interval, 'percent')} "
        f"({format_pd_confidence_bucket_label(confidence_bucket)}); signed notch difference = "
        f"{format_pd_signed_notching_label(signed_notching_difference)} ({notching_bucket}). "
        f"Direct lookup result: {lookup_label}.{fallback_text}"
    )


# ---------------------------------------------------------------------------
# Trend builders (buildPdCalibrationRagTrend / buildPdDiscriminationRagTrend / ...)
# ---------------------------------------------------------------------------


def build_pd_calibration_rag_trend(observations, rating_observations, monitoring_quarter, ctx: PdFilterContext, crr_scale, monitoring_thresholds, fallback_rules=None):
    quarters = sorted({q for q in ctx.quarters if q and q <= monitoring_quarter})
    quarters = pd_quarters_with_data(quarters, observations, ("1y", "2y"), ctx)
    trend = []
    for quarter in quarters:
        details = calculate_pd_calibration_conservatism_details(
            observations, rating_observations, quarter, ctx, crr_scale, monitoring_thresholds, fallback_rules,
        )
        trend.append({
            "quarter": quarter,
            "rag": details["rag"],
            "rag_score": pd_rag_score(details["rag"]),
            "weighted_average": details["weighted_average"],
            "rounded_score": details["rounded_score"],
        })
    return trend


def build_pd_discrimination_rag_trend(observations, rating_observations, monitoring_quarter, ctx: PdFilterContext, crr_scale, monitoring_thresholds, fallback_rules=None):
    thresholds = get_pd_thresholds(monitoring_thresholds)
    quarters = sorted({q for q in ctx.quarters if q and q <= monitoring_quarter})
    quarters = pd_quarters_with_data(quarters, observations, ("1y",), ctx)
    trend = []
    for quarter in quarters:
        values = calculate_pd_rag_metrics_for_horizon(observations, rating_observations, quarter, "1y", ctx, crr_scale)
        default_count_1y = calculate_pd_default_count_for_horizon(observations, quarter, "1y", ctx)
        accuracy_ratio = values["Accuracy Ratio"]
        delta_accuracy_ratio = values["Delta Accuracy Ratio"]
        accuracy_rag = calculate_pd_metric_rag(thresholds, "Accuracy Ratio", accuracy_ratio)
        delta_accuracy_rag = calculate_pd_metric_rag(thresholds, "Delta Accuracy Ratio", delta_accuracy_ratio)
        rag = calculate_pd_discrimination_section_rag(thresholds, values, default_count_1y)
        # Fallback Amber (low defaults): the metric is not a valid measurement, so
        # suppress its value in the hover and show only the forced RAG.
        accuracy_rag, accuracy_ratio = _apply_fallback_to_trend_metric(
            fallback_rules, "Accuracy Ratio 1 year", default_count_1y, accuracy_rag, accuracy_ratio,
        )
        delta_accuracy_rag, delta_accuracy_ratio = _apply_fallback_to_trend_metric(
            fallback_rules, "Delta Accuracy Ratio 1 year", default_count_1y, delta_accuracy_rag, delta_accuracy_ratio,
        )
        trend.append({
            "quarter": quarter,
            "rag": rag,
            "rag_score": pd_rag_score(rag),
            "accuracy_ratio": accuracy_ratio,
            "accuracy_rag": accuracy_rag,
            "delta_accuracy_ratio": delta_accuracy_ratio,
            "delta_accuracy_rag": delta_accuracy_rag,
            "default_count_1y": default_count_1y,
            "low_default_override": default_count_1y < 15,
        })
    return trend


def build_pd_balance_sheet_calibration_rag_trend(observations, rating_observations, monitoring_quarter, ctx: PdFilterContext, crr_scale, monitoring_thresholds, fallback_rules=None):
    thresholds = get_pd_thresholds(monitoring_thresholds)
    quarters = sorted({q for q in ctx.quarters if q and q <= monitoring_quarter})
    quarters = pd_quarters_with_data(quarters, observations, ("nco_1y",), ctx)
    trend = []
    for quarter in quarters:
        values = calculate_pd_rag_metrics_for_horizon(observations, rating_observations, quarter, "nco_1y", ctx, crr_scale)
        precomp = precomputed_row(ctx, quarter, "nco_1y")
        if precomp is not None:
            signed_difference = precomp.get("notching_test_signed")
        else:
            signed_difference = calculate_pd_notching_components(
                filter_pd_performance_observations_for_horizon(observations, quarter, "nco_1y", ctx), crr_scale,
            )["signed_difference"]
        default_count = calculate_pd_default_count_for_horizon(observations, quarter, "nco_1y", ctx)
        notching_na = resolve_fallback_rule(
            fallback_rules, "PD", "Balance Sheet PD", "Notching Test 1 year", default_count,
        )[0] == "non_applicable"
        assignment_rag = calibration_assignment_rag_with_fallback(
            values["Confidence Interval Test"], signed_difference, monitoring_thresholds,
            fallback_rules=fallback_rules, component="Balance Sheet PD",
            notching_test="Notching Test 1 year", default_count=default_count,
        )
        if assignment_rag == "N/A":
            rag = get_worst_pd_rag([
                calculate_pd_metric_rag(thresholds, metric, values[metric])
                for metric in config.PD_RAG_GROUPS["calibration"]
            ])
        else:
            rag = assignment_rag
        trend.append({
            "quarter": quarter,
            "rag": rag,
            "rag_score": pd_rag_score(rag),
            "confidence_interval": values["Confidence Interval Test"],
            "confidence_rag": calculate_pd_metric_rag(thresholds, "Confidence Interval Test", values["Confidence Interval Test"]),
            # Not calculated -> suppress the notching value/RAG in the hover.
            "notching_difference": None if notching_na else signed_difference,
            "notching_rag": "N/A" if notching_na else calculate_pd_metric_rag(thresholds, "Notching Test", signed_difference),
            "assignment_rag": assignment_rag,
        })
    return trend


def _precomputed_trend_row(precomp: dict, quarter: str, crr_scale) -> dict:
    """Build one trend row entirely from precomputed sheet values."""
    predicted_dr = precomp.get("predicted_default_rate")
    observed_dr = precomp.get("observed_default_rate")
    signed = precomp.get("notching_test_signed")
    abs_notch = precomp.get("notching_test_abs")
    # The individual actual/predicted notch grades are a deterministic CRR lookup.
    predicted_notch = map_pd_probability_to_crr(predicted_dr, crr_scale) if predicted_dr is not None else None
    actual_notch = map_pd_probability_to_crr(observed_dr, crr_scale) if observed_dr is not None else None
    accuracy_ratio = precomp.get("accuracy_ratio")
    return {
        "quarter": quarter,
        "observed_default_rate": observed_dr,
        "predicted_default_rate": predicted_dr,
        "actual_expected_ratio": precomp.get("actual_expected_ratio"),
        "accuracy_ratio": accuracy_ratio,
        "gini_coefficient": precomp.get("gini_coefficient"),
        "ks_statistic": precomp.get("ks_statistic"),
        "brier_score": precomp.get("brier_score"),
        "population_stability_index": precomp.get("population_stability_index"),
        "rating_migration_index": precomp.get("rating_migration_index"),
        "notching_test": abs_notch,
        "actual_notch": actual_notch,
        "predicted_notch": predicted_notch,
        "notching_difference": abs_notch if abs_notch is not None else (abs(signed) if signed is not None else None),
        "confidence_interval": precomp.get("confidence_interval_test"),
        "go_live_accuracy_ratio": precomp.get("go_live_accuracy_ratio"),
        "go_live_quarter": precomp.get("go_live_quarter") or "",
        "delta_accuracy_ratio": precomp.get("delta_accuracy_ratio"),
        "kendall_tau": precomp.get("kendall_tau"),
    }


def build_pd_performance_trend_for_horizon(observations, rating_observations, snapshot_quarter, horizon_key, ctx: PdFilterContext, crr_scale):
    quarters = sorted({q for q in ctx.quarters if q and q <= snapshot_quarter})
    quarters = pd_quarters_with_data(quarters, observations, (horizon_key,), ctx)
    trend = []
    for quarter in quarters:
        precomp = precomputed_row(ctx, quarter, horizon_key)
        if precomp is not None:
            trend.append(_precomputed_trend_row(precomp, quarter, crr_scale))
            continue

        current_rows = filter_pd_performance_observations_for_horizon(observations, quarter, horizon_key, ctx)
        rag_metrics = calculate_pd_rag_metrics_for_horizon(observations, rating_observations, quarter, horizon_key, ctx, crr_scale)
        notching = calculate_pd_notching_components(current_rows, crr_scale)
        row = dict(calculate_pd_performance_metrics(current_rows))
        row.update({
            "quarter": quarter,
            "brier_score": rag_metrics["Brier Score"],
            "population_stability_index": rag_metrics["Population Stability Index"],
            "rating_migration_index": rag_metrics["Rating Migration Index"],
            "notching_test": rag_metrics["Notching Test"],
            "actual_notch": notching["actual_notch"],
            "predicted_notch": notching["predicted_notch"],
            "notching_difference": notching["difference"],
            "confidence_interval": rag_metrics["Confidence Interval Test"],
            "go_live_accuracy_ratio": rag_metrics["Go Live Accuracy Ratio"],
            "go_live_quarter": rag_metrics["Go Live Quarter"],
            "delta_accuracy_ratio": rag_metrics["Delta Accuracy Ratio"],
            "kendall_tau": rag_metrics["Kendall's Tau"],
        })
        trend.append(row)
    return trend
# ---------------------------------------------------------------------------
# Formatting helpers (formatPdMetric / pdRagScore / formatPdTestChange / ...)
# ---------------------------------------------------------------------------


def format_pd_metric(value, fmt):
    if value is None or not math.isfinite(value):
        return "—"
    if fmt == "percent":
        return f"{value * 100:.2f}%"
    if fmt == "count":
        return f"{round(value)}"
    return f"{value:.3f}"


def format_pd_compact_amount(value):
    if value is None or not math.isfinite(value):
        return "—"
    absolute = abs(value)
    if absolute >= 1e9:
        return f"{value / 1e9:.2f}B"
    if absolute >= 1e6:
        return f"{value / 1e6:.1f}M"
    if absolute >= 1e3:
        return f"{value / 1e3:.1f}K"
    return fmt_n(round(value))


def pd_tone_class(rag):
    return {"Green": "green", "Amber": "amber", "Red": "red"}.get(rag, "na")


def pd_rag_score(rag):
    return {"Red": 1, "Amber": 2, "Green": 3}.get(rag)


def pd_score_to_rag(score):
    return {1: "Red", 2: "Amber", 3: "Green"}.get(score, "N/A")


def round_pd_half_down(value):
    if value is None or not math.isfinite(value):
        return None
    lower = math.floor(value)
    return lower + 1 if value - lower > 0.5 else lower


def format_pd_test_change(current, previous, fmt, threshold=None):
    threshold = threshold or {}
    if current is None or previous is None or not math.isfinite(current) or not math.isfinite(previous):
        return {"text": "No prior comparison", "css": "pd-change-neutral"}

    difference = current - previous
    display_difference = difference * 100 if fmt == "percent" else difference
    decimals = 0 if fmt == "count" else 2 if fmt == "percent" else 3
    suffix = " pp" if fmt == "percent" else ""

    if abs(display_difference) < (10 ** -decimals) / 2:
        return {"text": f"{0:.{decimals}f}{suffix}", "css": "pd-change-neutral"}

    improved = None
    if threshold.get("higher_is_better") is True:
        improved = difference > 0
    elif threshold.get("lower_is_better") is True:
        improved = difference < 0
    elif is_finite_number(threshold.get("target_value")):
        target_value = threshold["target_value"]
        improved = abs(current - target_value) < abs(previous - target_value)

    sign = "+" if display_difference > 0 else ""
    return {
        "text": f"{sign}{display_difference:.{decimals}f}{suffix}",
        "css": "pd-change-neutral" if improved is None else ("pd-change-negative" if improved else "pd-change-positive"),
    }


def format_pd_rag_change(current, previous):
    scores = {"N/A": 0, "Green": 1, "Amber": 2, "Red": 3}
    if not previous or previous == "N/A":
        return {"text": "No prior comparison", "css": "pd-change-neutral"}
    if current == previous:
        return {"text": "No change", "css": "pd-change-neutral"}
    if scores.get(current, 0) < scores.get(previous, 0):
        return {"text": "Improved", "css": "pd-change-negative"}
    return {"text": "Deteriorated", "css": "pd-change-positive"}


# ---------------------------------------------------------------------------
# Threshold bands for chart backgrounds (buildPdThresholdBands / buildPdAeRatioBands)
# ---------------------------------------------------------------------------


def build_pd_ae_ratio_bands(threshold, ratios):
    threshold = threshold or {}
    green_min = threshold.get("green_min") if is_finite_number(threshold.get("green_min")) else 0.75
    green_max = threshold.get("green_max") if is_finite_number(threshold.get("green_max")) else 1.25
    amber_min = threshold.get("amber_min") if is_finite_number(threshold.get("amber_min")) else green_min
    amber_max = threshold.get("amber_max") if is_finite_number(threshold.get("amber_max")) else green_max

    finite_ratios = [ratio for ratio in ratios if is_finite_number(ratio)]
    max_ratio = max(finite_ratios) if finite_ratios else amber_max
    axis_max = max(amber_max * 1.12, max_ratio * 1.12, 1.6)

    def band(y0, y1, fillcolor):
        return {
            "type": "rect", "xref": "paper", "x0": 0, "x1": 1, "yref": "y2",
            "y0": y0, "y1": y1, "fillcolor": fillcolor, "line": {"width": 0}, "layer": "below",
        }

    return {
        "axis_range": [0, axis_max],
        "shapes": [
            band(0, amber_min, "rgba(220,38,38,.08)"),
            band(amber_min, green_min, "rgba(217,119,6,.18)"),
            band(green_min, green_max, "rgba(22,163,74,.10)"),
            band(green_max, amber_max, "rgba(217,119,6,.18)"),
            band(amber_max, axis_max, "rgba(220,38,38,.08)"),
        ],
    }


def build_pd_threshold_bands(threshold, values, options=None):
    options = options or {}
    finite_values = [value for value in values if is_finite_number(value)]
    min_value = min(finite_values) if finite_values else 0
    max_value = max(finite_values) if finite_values else 1
    min_axis_max = options.get("min_axis_max") if is_finite_number(options.get("min_axis_max")) else 1

    red = "rgba(220,38,38,.08)"
    amber = "rgba(217,119,6,.18)"
    green = "rgba(22,163,74,.10)"

    def band(y0, y1, fillcolor):
        return {
            "type": "rect", "xref": "paper", "x0": 0, "x1": 1, "yref": "y",
            "y0": y0, "y1": y1, "fillcolor": fillcolor, "line": {"width": 0}, "layer": "below",
        }

    def positive_axis(upper_bound):
        return [
            min(0, min_value * 1.12 if min_value < 0 else 0),
            max(upper_bound, max_value * 1.12, min_axis_max),
        ]

    threshold = threshold or {}
    red_condition = threshold.get("red_condition")
    inferred_green_max = extract_pd_rule_upper_bound(threshold.get("green_rule"))
    inferred_amber_max = extract_pd_rule_upper_bound(threshold.get("amber_rule"))
    inferred_green_min = extract_pd_rule_lower_bound(threshold.get("green_rule"))
    inferred_amber_min = extract_pd_rule_lower_bound(threshold.get("amber_rule"))

    if not threshold or red_condition == "no_rag":
        return {"axis_range": positive_axis(max_value), "shapes": []}

    if red_condition == "below amber_min":
        green_min = threshold.get("green_min") if is_finite_number(threshold.get("green_min")) else max_value
        amber_min = threshold.get("amber_min") if is_finite_number(threshold.get("amber_min")) else green_min
        axis_range = positive_axis(green_min * 1.2)
        return {
            "axis_range": axis_range,
            "shapes": [
                band(axis_range[0], amber_min, red),
                band(amber_min, green_min, amber),
                band(green_min, axis_range[1], green),
            ],
        }

    if red_condition == "above amber_max":
        green_max = threshold.get("green_max") if is_finite_number(threshold.get("green_max")) else max_value
        amber_max = threshold.get("amber_max") if is_finite_number(threshold.get("amber_max")) else green_max
        axis_range = positive_axis(amber_max * 1.12)
        return {
            "axis_range": axis_range,
            "shapes": [
                band(axis_range[0], green_max, green),
                band(green_max, amber_max, amber),
                band(amber_max, axis_range[1], red),
            ],
        }

    if red_condition == "outside amber range":
        green_min = threshold.get("green_min") if is_finite_number(threshold.get("green_min")) else min_value
        green_max = threshold.get("green_max") if is_finite_number(threshold.get("green_max")) else max_value
        amber_min = threshold.get("amber_min") if is_finite_number(threshold.get("amber_min")) else green_min
        amber_max = threshold.get("amber_max") if is_finite_number(threshold.get("amber_max")) else green_max
        axis_range = positive_axis(amber_max * 1.12)
        return {
            "axis_range": axis_range,
            "shapes": [
                band(axis_range[0], amber_min, red),
                band(amber_min, green_min, amber),
                band(green_min, green_max, green),
                band(green_max, amber_max, amber),
                band(amber_max, axis_range[1], red),
            ],
        }

    if red_condition == "abs above amber_max":
        green_max = abs(threshold.get("green_max") if is_finite_number(threshold.get("green_max")) else max_value)
        amber_max = abs(threshold.get("amber_max") if is_finite_number(threshold.get("amber_max")) else green_max)
        axis_max = max(amber_max * 1.12, abs(min_value) * 1.12, abs(max_value) * 1.12, min_axis_max)
        axis_range = [-axis_max, axis_max]
        return {
            "axis_range": axis_range,
            "shapes": [
                band(axis_range[0], -amber_max, red),
                band(-amber_max, -green_max, amber),
                band(-green_max, green_max, green),
                band(green_max, amber_max, amber),
                band(amber_max, axis_range[1], red),
            ],
        }

    if threshold.get("lower_is_better") is True and is_finite_number(inferred_green_max) and is_finite_number(inferred_amber_max):
        axis_range = positive_axis(inferred_amber_max * 1.12)
        return {
            "axis_range": axis_range,
            "shapes": [
                band(axis_range[0], inferred_green_max, green),
                band(inferred_green_max, inferred_amber_max, amber),
                band(inferred_amber_max, axis_range[1], red),
            ],
        }

    if threshold.get("higher_is_better") is True and is_finite_number(inferred_green_min) and is_finite_number(inferred_amber_min):
        axis_range = positive_axis(max(max_value, inferred_green_min * 1.2))
        return {
            "axis_range": axis_range,
            "shapes": [
                band(axis_range[0], inferred_amber_min, red),
                band(inferred_amber_min, inferred_green_min, amber),
                band(inferred_green_min, axis_range[1], green),
            ],
        }

    return {"axis_range": positive_axis(max_value), "shapes": []}
