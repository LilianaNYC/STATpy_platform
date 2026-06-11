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

from .. import monitoring_config as config

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


def _finite(value):
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


def shift_monitoring_quarter_year(quarter, year_delta):
    match = _QUARTER_RE.match(quarter or "")
    if not match:
        return ""
    return f"{int(match.group(1)) + year_delta}Q{match.group(2)}"


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
    snapshot_quarter = shift_monitoring_quarter_year(ctx.monitoring_point, -horizon_years)
    return {
        "monitoring_point": ctx.monitoring_point,
        "horizon_key": horizon_key,
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
    current = [row["predicted"] for row in current_rows if _finite(row["predicted"])]
    previous = [row["predicted"] for row in previous_rows if _finite(row["predicted"])]
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

    predicted = [row["predicted"] for row in rows if _finite(row["predicted"])]
    observed = [row["observed"] for row in rows if _finite(row["observed"])]
    if not predicted or not observed:
        return dict(empty)

    average_predicted = sum(predicted) / len(predicted)
    average_observed = sum(observed) / len(observed)
    predicted_notch = map_pd_probability_to_crr(average_predicted, crr_scale)
    actual_notch = map_pd_probability_to_crr(average_observed, crr_scale)
    if not _finite(predicted_notch) or not _finite(actual_notch):
        return dict(empty)

    return {
        "actual_notch": actual_notch,
        "predicted_notch": predicted_notch,
        "signed_difference": predicted_notch - actual_notch,
        "difference": abs(predicted_notch - actual_notch),
    }


def calculate_pd_notching_test(rows, crr_scale):
    return calculate_pd_notching_components(rows, crr_scale)["difference"]


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

    predicted = [row["predicted"] for row in rows if _finite(row["predicted"])]
    observed = [row["observed"] for row in rows if _finite(row["observed"])]
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
        if _finite(accuracy_ratio):
            return quarter
    return ""


def calculate_pd_rag_metrics_for_horizon(performance_observations, rating_observations, quarter, horizon_key, ctx: PdFilterContext, crr_scale):
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
        _finite(go_live_accuracy_ratio) and _finite(accuracy_ratio)
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


def calculate_pd_discrimination_section_rag(thresholds, values, default_count_1y=None):
    if default_count_1y is not None and math.isfinite(default_count_1y) and default_count_1y < 15:
        return "Amber"
    accuracy_rag = calculate_pd_metric_rag(thresholds, "Accuracy Ratio", values.get("Accuracy Ratio"))
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
    weighted_label = "—" if not _finite(weighted_score) else f"{weighted_score:.2f}"
    rounded_label = "—" if not _finite(rounded_score) else f"{rounded_score}"

    if not _finite(weighted_score) or not _finite(rounded_score):
        return (
            "Performance PD RAG combines three inputs with weights of 25%, 25%, and 50%. Higher scores are better: "
            f"Green = 3, Amber = 2, Red = 1. Current inputs: {component_summary}. One or more inputs are unavailable, "
            f"so the final Performance PD RAG is {details['rag']}."
        )
    return (
        "Performance PD RAG combines three inputs with weights of 25%, 25%, and 50%. Higher scores are better: "
        f"Green = 3, Amber = 2, Red = 1. Current inputs: {component_summary}. Weighted average score = {weighted_label}. "
        f"Rounded score = {rounded_label}, so the final Performance PD RAG is {details['rag']}."
    )


# ---------------------------------------------------------------------------
# EAD summaries (calculatePdEadSummaries)
# ---------------------------------------------------------------------------


def calculate_pd_ead_summaries(observations, quarter, ctx: PdFilterContext):
    selected_rows = [row for row in observations if matches_pd_selected_population(row, quarter, ctx)]
    empty = {
        "1y": {"ead": None, "share": None, "combined_ead": None},
        "2y": {"ead": None, "share": None, "combined_ead": None},
    }
    if not selected_rows:
        return empty

    def sum_ead_for_horizon(key):
        total = 0.0
        for row in selected_rows:
            value = (row.get("horizons") or {}).get(key, {}).get("ead")
            if _finite(value):
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


def calculate_pd_calibration_conservatism_details(observations, rating_observations, monitoring_quarter, ctx: PdFilterContext, crr_scale, monitoring_thresholds):
    if not monitoring_quarter:
        return {"rag": "N/A", "weighted_average": None, "rounded_score": None, "horizons": [], "total_weight": 0}

    ead_summaries = calculate_pd_ead_summaries(observations, monitoring_quarter, ctx)
    horizon_configs = [("1y", 1), ("2y", 2)]
    weighted_scores = []
    for horizon_key, years in horizon_configs:
        snapshot_quarter = shift_monitoring_quarter_year(monitoring_quarter, -years)
        if not snapshot_quarter:
            continue
        horizon_values = calculate_pd_rag_metrics_for_horizon(
            observations, rating_observations, snapshot_quarter, horizon_key, ctx, crr_scale,
        )
        horizon_notching = calculate_pd_notching_components(
            filter_pd_performance_observations_for_horizon(observations, snapshot_quarter, horizon_key, ctx),
            crr_scale,
        )
        rag = calculate_pd_calibration_assignment_rag(
            horizon_values["Confidence Interval Test"], horizon_notching["signed_difference"], monitoring_thresholds,
        )
        score = pd_rag_score(rag)
        weight = (ead_summaries.get(horizon_key) or {}).get("share")
        if score is not None and _finite(weight):
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


def calculate_pd_calibration_conservatism_rag(observations, rating_observations, monitoring_quarter, ctx: PdFilterContext, crr_scale, monitoring_thresholds):
    return calculate_pd_calibration_conservatism_details(
        observations, rating_observations, monitoring_quarter, ctx, crr_scale, monitoring_thresholds,
    )["rag"]


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
    weighted_label = "—" if not _finite(weighted_average) else f"{weighted_average:.2f}"
    rounded_label = "—" if not _finite(rounded_score) else f"{rounded_score}"

    if not _finite(weighted_average) or not _finite(rounded_score):
        return (
            "Calibration Conservatism RAG (ECL PIT) combines the 1-year and 2-year RAG Assignment results "
            f"using EAD share weights. Higher scores are better: Green = 3, Amber = 2, Red = 1. Current inputs: {pieces}. "
            f"One or more inputs are unavailable, so the final Calibration Conservatism RAG is {details['rag']}."
        )
    return (
        "Calibration Conservatism RAG (ECL PIT) combines the 1-year and 2-year RAG Assignment results "
        f"using EAD share weights. Higher scores are better: Green = 3, Amber = 2, Red = 1. Current inputs: {pieces}. "
        f"Weighted average score = {weighted_label}. Rounded score = {rounded_label}, so the final Calibration "
        f"Conservatism RAG is {details['rag']}."
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
        fallback_text = f" Final displayed RAG = {displayed_rag or 'N/A'}."

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
        f"Confidence Interval = {format_pd_metric(confidence_interval, 'percent')} "
        f"({format_pd_confidence_bucket_label(confidence_bucket)}); signed notch difference = "
        f"{format_pd_signed_notching_label(signed_notching_difference)} ({notching_bucket}). "
        f"Direct lookup result = {lookup_label}.{fallback_text}"
    )


# ---------------------------------------------------------------------------
# Trend builders (buildPdCalibrationRagTrend / buildPdDiscriminationRagTrend / ...)
# ---------------------------------------------------------------------------


def build_pd_calibration_rag_trend(observations, rating_observations, monitoring_quarter, ctx: PdFilterContext, crr_scale, monitoring_thresholds):
    quarters = sorted({q for q in ctx.quarters if q and q <= monitoring_quarter})
    trend = []
    for quarter in quarters:
        details = calculate_pd_calibration_conservatism_details(
            observations, rating_observations, quarter, ctx, crr_scale, monitoring_thresholds,
        )
        trend.append({
            "quarter": quarter,
            "rag": details["rag"],
            "rag_score": pd_rag_score(details["rag"]),
            "weighted_average": details["weighted_average"],
            "rounded_score": details["rounded_score"],
        })
    return trend


def build_pd_discrimination_rag_trend(observations, rating_observations, monitoring_quarter, ctx: PdFilterContext, crr_scale, monitoring_thresholds):
    thresholds = get_pd_thresholds(monitoring_thresholds)
    quarters = sorted({q for q in ctx.quarters if q and q <= monitoring_quarter})
    trend = []
    for quarter in quarters:
        values = calculate_pd_rag_metrics_for_horizon(observations, rating_observations, quarter, "1y", ctx, crr_scale)
        default_count_1y = calculate_pd_default_count_for_horizon(observations, quarter, "1y", ctx)
        accuracy_ratio = values["Accuracy Ratio"]
        delta_accuracy_ratio = values["Delta Accuracy Ratio"]
        accuracy_rag = calculate_pd_metric_rag(thresholds, "Accuracy Ratio", accuracy_ratio)
        delta_accuracy_rag = calculate_pd_metric_rag(thresholds, "Delta Accuracy Ratio", delta_accuracy_ratio)
        rag = calculate_pd_discrimination_section_rag(thresholds, values, default_count_1y)
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


def build_pd_balance_sheet_calibration_rag_trend(observations, rating_observations, monitoring_quarter, ctx: PdFilterContext, crr_scale, monitoring_thresholds):
    thresholds = get_pd_thresholds(monitoring_thresholds)
    quarters = sorted({q for q in ctx.quarters if q and q <= monitoring_quarter})
    trend = []
    for quarter in quarters:
        values = calculate_pd_rag_metrics_for_horizon(observations, rating_observations, quarter, "nco_1y", ctx, crr_scale)
        notching = calculate_pd_notching_components(
            filter_pd_performance_observations_for_horizon(observations, quarter, "nco_1y", ctx), crr_scale,
        )
        assignment_rag = calculate_pd_calibration_assignment_rag(
            values["Confidence Interval Test"], notching["signed_difference"], monitoring_thresholds,
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
            "notching_difference": notching["signed_difference"],
            "notching_rag": calculate_pd_metric_rag(thresholds, "Notching Test", notching["signed_difference"]),
            "assignment_rag": assignment_rag,
        })
    return trend


def build_pd_performance_trend_for_horizon(observations, rating_observations, snapshot_quarter, horizon_key, ctx: PdFilterContext, crr_scale):
    quarters = sorted({q for q in ctx.quarters if q and q <= snapshot_quarter})
    trend = []
    for quarter in quarters:
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


def build_pd_performance_trend(observations, rating_observations, snapshot_quarter, ctx: PdFilterContext, crr_scale):
    horizon_key = get_pd_performance_horizon_key(ctx)
    return build_pd_performance_trend_for_horizon(observations, rating_observations, snapshot_quarter, horizon_key, ctx, crr_scale)


def build_pd_rag_movement_rows(observations, rating_observations, metrics, periods, ctx: PdFilterContext, crr_scale, monitoring_thresholds):
    """Data form of ``buildPdRagMovement``: one row per metric plus a "Section RAG" summary row."""
    thresholds = get_pd_thresholds(monitoring_thresholds)
    status_by_period = []
    for period in periods:
        values = calculate_pd_rag_metrics(observations, rating_observations, period, ctx, crr_scale)
        rags = [calculate_pd_metric_rag(thresholds, metric, values.get(metric)) for metric in metrics]
        status_by_period.append({"period": period, "rags": rags, "group_rag": get_worst_pd_rag(rags)})

    rows = [{"metric": "Section RAG", "rags": [entry["group_rag"] for entry in status_by_period]}]
    for index, metric in enumerate(metrics):
        rows.append({"metric": metric, "rags": [entry["rags"][index] for entry in status_by_period]})
    return rows


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


def format_pd_share(value, total):
    if total:
        return f"{fmt_n(value)} ({value / total * 100:.1f}%)"
    return f"{fmt_n(value)} (—)"


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
    elif _finite(threshold.get("target_value")):
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
    green_min = threshold.get("green_min") if _finite(threshold.get("green_min")) else 0.75
    green_max = threshold.get("green_max") if _finite(threshold.get("green_max")) else 1.25
    amber_min = threshold.get("amber_min") if _finite(threshold.get("amber_min")) else green_min
    amber_max = threshold.get("amber_max") if _finite(threshold.get("amber_max")) else green_max

    finite_ratios = [ratio for ratio in ratios if _finite(ratio)]
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
            {
                "type": "line", "xref": "paper", "x0": 0, "x1": 1, "yref": "y2",
                "y0": 1, "y1": 1, "line": {"color": "#16a34a", "width": 1.5, "dash": "dash"},
            },
        ],
    }


def build_pd_threshold_bands(threshold, values, options=None):
    options = options or {}
    finite_values = [value for value in values if _finite(value)]
    min_value = min(finite_values) if finite_values else 0
    max_value = max(finite_values) if finite_values else 1
    min_axis_max = options.get("min_axis_max") if _finite(options.get("min_axis_max")) else 1

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
        green_min = threshold.get("green_min") if _finite(threshold.get("green_min")) else max_value
        amber_min = threshold.get("amber_min") if _finite(threshold.get("amber_min")) else green_min
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
        green_max = threshold.get("green_max") if _finite(threshold.get("green_max")) else max_value
        amber_max = threshold.get("amber_max") if _finite(threshold.get("amber_max")) else green_max
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
        green_min = threshold.get("green_min") if _finite(threshold.get("green_min")) else min_value
        green_max = threshold.get("green_max") if _finite(threshold.get("green_max")) else max_value
        amber_min = threshold.get("amber_min") if _finite(threshold.get("amber_min")) else green_min
        amber_max = threshold.get("amber_max") if _finite(threshold.get("amber_max")) else green_max
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
        green_max = abs(threshold.get("green_max") if _finite(threshold.get("green_max")) else max_value)
        amber_max = abs(threshold.get("amber_max") if _finite(threshold.get("amber_max")) else green_max)
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

    if threshold.get("lower_is_better") is True and _finite(inferred_green_max) and _finite(inferred_amber_max):
        axis_range = positive_axis(inferred_amber_max * 1.12)
        return {
            "axis_range": axis_range,
            "shapes": [
                band(axis_range[0], inferred_green_max, green),
                band(inferred_green_max, inferred_amber_max, amber),
                band(inferred_amber_max, axis_range[1], red),
            ],
        }

    if threshold.get("higher_is_better") is True and _finite(inferred_green_min) and _finite(inferred_amber_min):
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
