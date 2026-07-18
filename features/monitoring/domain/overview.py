"""Cross-portfolio data aggregation for the Overview page.

Builds one RAG row per (Model Group, Model, Segment, Monitoring Period) by
calling each tab's own domain functions directly -- PD's calibration/
discrimination math, and LGD/EAD/Loss's ``build_*_period_summary`` /
``build_*_rag_trend`` helpers -- so the portfolio view always agrees with
what each individual tab shows. No thresholds are re-derived here.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from ....shared.domain import constants as pd_config
from ....shared.domain.calculations import (
    PdFilterContext,
    calculate_pd_calibration_assignment_rag,
    calculate_pd_calibration_conservatism_details,
    calculate_pd_default_count_for_horizon,
    calculate_pd_discrimination_section_rag,
    calculate_pd_metric_rag,
    calculate_pd_notching_components,
    calculate_pd_overview_performance_rag,
    calculate_pd_rag_metrics_for_horizon,
    filter_pd_performance_observations_for_horizon,
    get_pd_crr_master_scale,
    get_pd_performance_context,
    get_pd_performance_context_for_horizon,
    get_pd_thresholds,
    get_worst_pd_rag,
    precomputed_row,
    precomputed_notching_components,
    set_precomputed_metrics,
)
from ....shared.repositories.filters_config import model_names

MODEL_GROUPS = ["PD", "LGD", "EAD", "Loss"]

# "RAG Assignment" mirrors each tab's Chapter 1 -- the core calibration/
# discrimination tests plus the headline Overall RAG. Quarter-conditioned:
# these vary by Monitoring Period like the rest of the row.
RAG_ASSIGNMENT_COLUMNS = [
    "Calibration RAG",
    "Discrimination RAG",
    "Balance Sheet Calibration RAG",
    "Overall RAG",
]
# "Post Subjective Review" mirrors each tab's Chapter 2. Transition Matrix,
# Scenario Ranking, Sensitivity, and MEV Range are reporting-cycle-scoped
# (worst-case across the whole projection horizon for that cycle), not
# quarter-conditioned -- so they carry the same value across every quarter
# row for a given (Model Group, Model, Segment) within one reporting cycle.
# PSI is the exception: it's quarter-conditioned like Chapter 1.
POST_SUBJECTIVE_COLUMNS = [
    "Transition Matrix RAG",
    "PSI RAG",
    "Scenario Ranking RAG",
    "Sensitivity Analysis RAG",
    "MEV Range RAG",
]
HEATMAP_FINAL_COLUMNS = [
    "Post Subjective Review RAG",
    "Pre Mitigation RAG",
    "Post Mitigation RAG",
]
RAG_COLUMNS = RAG_ASSIGNMENT_COLUMNS + POST_SUBJECTIVE_COLUMNS
# Importance ranking for a "driver" finding, most important first: Overall RAG
# leads since it's the roll-up verdict everything else feeds into; then the
# three tests that actually derive it (Calibration, Discrimination, Balance
# Sheet Calibration); Post Subjective Review tests are separate, lower-priority
# checks that don't feed Overall RAG at all. Used to order driver chips in the
# Escalation register and to pick the governance "leading driver".
DRIVER_PRIORITY_COLUMNS = ["Overall RAG"] + [c for c in RAG_ASSIGNMENT_COLUMNS if c != "Overall RAG"] + POST_SUBJECTIVE_COLUMNS


def _driver_priority(metric: str) -> int:
    return DRIVER_PRIORITY_COLUMNS.index(metric) if metric in DRIVER_PRIORITY_COLUMNS else len(DRIVER_PRIORITY_COLUMNS)
RAG_COLUMN_DESCRIPTIONS = {
    "Calibration RAG": "ECL PIT PD - Calibration Conservatism: how closely predicted values track actual outcomes.",
    "Discrimination RAG": "ECL PIT PD - Discriminatory Power: whether the model correctly rank-orders risk (n/a for Loss).",
    "Balance Sheet Calibration RAG": "Balance Sheet PD - Calibration Conservatism, on the NCO 1y horizon (PD only).",
    "Overall RAG": "Calibration, Discrimination, and Balance Sheet roll into Overall",
    "Transition Matrix RAG": "Worst-case migration-margin (MM_Pm - MM_P0) breach across the projection horizon (PD only).",
    "PSI RAG": "Population Stability Index vs. the reference population (n/a for Loss).",
    "Scenario Ranking RAG": "Whether projected values keep a consistent rank order across scenarios for the model use case / cycle.",
    "Sensitivity Analysis RAG": "Whether the baseline-vs-shocked projection stays within the sensitivity threshold.",
    "MEV Range RAG": "Worst-case RAG across in-scope MEVs outside their development range for the scenario.",
    "Post Subjective Review RAG": "Reflects the impact of any subjective overlays and considers the post-subjective review.",
    "Pre Mitigation RAG": "Pre-Overlay RAG obtained from the trend of the post-subjective-review model RAG.",
    "Post Mitigation RAG": "Post-Overlay RAG based on the residual risk of the model, including compensating controls.",
}
# The Final RAG column is a placeholder verdict shown only in the RAG Heatmap
# tables -- deliberately excluded from RAG_COLUMNS so it doesn't leak into the
# RAG Trend dimension picker, governance, or findings, none of which have a
# real value to compute yet. FINAL_RAG_PLACEHOLDER is a static stand-in until
# the actual methodology is defined.
FINAL_RAG_COLUMN = "Final RAG"
FINAL_RAG_PLACEHOLDER = "Amber"
HEATMAP_COLUMNS = RAG_COLUMNS + HEATMAP_FINAL_COLUMNS
RAG_COLUMN_DESCRIPTIONS[FINAL_RAG_COLUMN] = "Placeholder for the model's final RAG verdict. Methodology is still to be defined; the value shown is a static placeholder, not a real assessment."
# Worst-case ranking used for aggregation (max()) -- N/A is treated as Amber
# for counting purposes (an untested model still needs review), but is always
# rendered in its own gray color, never confused visually with a real Amber.
RAG_SCORE = {"Green": 1, "N/A": 2, "Amber": 2, "Red": 3}


def effective_rag(rag: str | None) -> str:
    return "Amber" if rag == "N/A" else rag or "N/A"


def display_rag(rag: str | None) -> str:
    return rag or "N/A"


def _quarter_sort_key(value: str) -> tuple[int, int]:
    text = str(value or "")
    try:
        year, quarter = text.split("Q", 1)
        return int(year), int(quarter)
    except (TypeError, ValueError):
        return 0, 0


# ---------------------------------------------------------------------------
# Row builders -- one per model group, each reusing that tab's own domain logic
# ---------------------------------------------------------------------------


def _pd_chapter1_metrics(
    performance_observations, rating_migration_observations, performance_horizons,
    monitoring_thresholds, thresholds, crr_scale, ctx: PdFilterContext, quarter: str,
) -> dict[str, Any]:
    """Calibration / Discrimination / Balance Sheet / Overall / PSI for one PD
    ctx at one quarter -- mirrors the PD Performance tab's own Chapter 1
    headline cards exactly (features/monitoring/ui/views/pd_performance.py).
    Shared by the by-model rows (Chapter 1) and by-segment rows (Chapter 2);
    ``ctx`` alone determines whether this is pooled-by-model or pooled-by-segment.
    """
    # The 1-year tests are anchored one year *before* the monitoring point
    # (the most recent vintage whose 1-year outcome is fully observable as of
    # this quarter), not the quarter itself.
    context = get_pd_performance_context(performance_horizons, ctx)
    current_rag_values = calculate_pd_rag_metrics_for_horizon(
        performance_observations, rating_migration_observations, context["snapshot_quarter"], "1y", ctx, crr_scale,
    )

    calibration_assignment_details = calculate_pd_calibration_conservatism_details(
        performance_observations, rating_migration_observations, quarter, ctx, crr_scale, monitoring_thresholds,
    )
    calibration_assignment_rag = calibration_assignment_details["rag"]
    if calibration_assignment_rag == "N/A":
        calibration_rag = get_worst_pd_rag([
            calculate_pd_metric_rag(thresholds, metric, current_rag_values[metric])
            for metric in pd_config.PD_RAG_GROUPS["calibration"]
        ])
    else:
        calibration_rag = calibration_assignment_rag

    discrimination_default_count = calculate_pd_default_count_for_horizon(
        performance_observations, context["snapshot_quarter"], "1y", ctx,
    )
    discrimination_rag = calculate_pd_discrimination_section_rag(
        thresholds, current_rag_values, discrimination_default_count,
    )

    balance_sheet_context = get_pd_performance_context_for_horizon(performance_horizons, "nco_1y", ctx)
    balance_sheet_values = calculate_pd_rag_metrics_for_horizon(
        performance_observations, rating_migration_observations, balance_sheet_context["snapshot_quarter"], "nco_1y", ctx, crr_scale,
    )
    balance_sheet_notching = precomputed_notching_components(
        ctx, balance_sheet_context["snapshot_quarter"], "nco_1y", crr_scale,
    ) or calculate_pd_notching_components(
        filter_pd_performance_observations_for_horizon(
            performance_observations, balance_sheet_context["snapshot_quarter"], "nco_1y", ctx,
        ),
        crr_scale,
    )
    balance_sheet_assignment_rag = calculate_pd_calibration_assignment_rag(
        balance_sheet_values["Confidence Interval Test"], balance_sheet_notching["signed_difference"], monitoring_thresholds,
    )
    if balance_sheet_assignment_rag == "N/A":
        balance_sheet_rag = get_worst_pd_rag([
            calculate_pd_metric_rag(thresholds, metric, balance_sheet_values[metric])
            for metric in pd_config.PD_RAG_GROUPS["calibration"]
        ])
    else:
        balance_sheet_rag = balance_sheet_assignment_rag

    overall_rag = calculate_pd_overview_performance_rag(
        calibration_rag, discrimination_rag, balance_sheet_rag,
    )["rag"]

    # PSI mirrors the Chapter 2 PSI trend, which anchors directly on the
    # monitoring-point quarter (unshifted) -- see build_pd_performance_trend_for_horizon.
    psi_values = calculate_pd_rag_metrics_for_horizon(
        performance_observations, rating_migration_observations, quarter, "1y", ctx, crr_scale,
    )
    psi_value = psi_values.get("Population Stability Index")
    psi_rag = calculate_pd_metric_rag(thresholds, "Population Stability Index", psi_value)

    return {
        "Calibration RAG": calibration_rag,
        "Discrimination RAG": discrimination_rag,
        "Balance Sheet Calibration RAG": balance_sheet_rag,
        "Overall RAG": overall_rag,
        "PSI RAG": psi_rag,
        "PSI Metric": f"{psi_value:.3f}" if psi_value is not None else "—",
    }


def _pd_cycle_data(data: dict, reporting_cycle: str) -> tuple[list[str], Any, Any, Any]:
    cycle_data = (data.get("observations_by_cycle") or {}).get(reporting_cycle)
    if cycle_data:
        return cycle_data["quarters"], cycle_data["performance_observations"], cycle_data["rating_migration_observations"], cycle_data.get("metrics_store")
    return data["quarters"], data["performance_observations"], data["rating_migration_observations"], None


def _pd_review_flow_rags(ctx: PdFilterContext, quarter: str) -> dict[str, str]:
    row = (
        precomputed_row(ctx, quarter, "1y")
        or precomputed_row(ctx, quarter, "2y")
        or precomputed_row(ctx, quarter, "nco_1y")
        or {}
    )

    def _text(key: str) -> str:
        value = str(row.get(key, "") or "").strip()
        return value or "N/A"

    return {
        "Post Subjective Review RAG": _text("rag_post_sr"),
        "Pre Mitigation RAG": _text("rag_pre_mitig"),
        "Post Mitigation RAG": _text("rag_post_mitig"),
        "Reviewer Commentary": str(row.get("reviewer_commentary", "") or "").strip(),
    }


def _review_flow_rags_from_metric_row(metric_row: dict[str, Any] | None) -> dict[str, str]:
    row = metric_row or {}

    def _text(key: str) -> str:
        value = str(row.get(key, "") or "").strip()
        return value or "N/A"

    return {
        "Post Subjective Review RAG": _text("rag_post_sr"),
        "Pre Mitigation RAG": _text("rag_pre_mitig"),
        "Post Mitigation RAG": _text("rag_post_mitig"),
        "Reviewer Commentary": str(row.get("reviewer_commentary", "") or "").strip(),
    }


def _pd_rows(data: dict, reporting_cycle: str) -> list[dict[str, Any]]:
    quarters, performance_observations, rating_migration_observations, metrics_store = _pd_cycle_data(data, reporting_cycle)
    set_precomputed_metrics(metrics_store)

    monitoring_thresholds = data["monitoring_thresholds"]
    thresholds = get_pd_thresholds(monitoring_thresholds)
    crr_scale = get_pd_crr_master_scale(monitoring_thresholds)
    performance_horizons = data["performance_horizons"]
    pd_model_names = data.get("model_names", [])

    model_entities = pd_model_names

    rows: list[dict[str, Any]] = []
    for quarter in quarters:
        for model_name in model_entities:
            # Metrics stay pooled across segments here, matching the Models
            # chapter on the PD Performance tab.
            models = {model_name}
            ctx = PdFilterContext(quarters=quarters, models=models, segment="all", monitoring_point=quarter)
            metrics = _pd_chapter1_metrics(
                performance_observations, rating_migration_observations, performance_horizons,
                monitoring_thresholds, thresholds, crr_scale, ctx, quarter,
            )
            rows.append({
                "Monitoring Period": quarter,
                "Model Group": "PD",
                "Model": model_name,
                "Segment": "All",
                **metrics,
                **_pd_review_flow_rags(ctx, quarter),
            })
    return rows


def _pd_segment_rows(data: dict, reporting_cycle: str) -> list[dict[str, Any]]:
    """One row per (real segment, quarter), pooled across every PD model --
    the Segments chapter equivalent of ``_pd_rows``."""
    quarters, performance_observations, rating_migration_observations, metrics_store = _pd_cycle_data(data, reporting_cycle)
    set_precomputed_metrics(metrics_store)

    monitoring_thresholds = data["monitoring_thresholds"]
    thresholds = get_pd_thresholds(monitoring_thresholds)
    crr_scale = get_pd_crr_master_scale(monitoring_thresholds)
    performance_horizons = data["performance_horizons"]
    all_pd_models = set(data.get("model_names", []))

    rows: list[dict[str, Any]] = []
    for quarter in quarters:
        for segment in data.get("segment_values", []):
            ctx = PdFilterContext(quarters=quarters, models=all_pd_models, segment=segment, monitoring_point=quarter)
            metrics = _pd_chapter1_metrics(
                performance_observations, rating_migration_observations, performance_horizons,
                monitoring_thresholds, thresholds, crr_scale, ctx, quarter,
            )
            rows.append({
                "Monitoring Period": quarter,
                "Model Group": "PD",
                "Segment": segment,
                **metrics,
            })
    return rows


def _lgd_segment_rows(data: dict, reporting_cycle: str) -> list[dict[str, Any]]:
    """LGD's segment-level equivalent of ``_lgd_rows``: LGD's precomputed
    metrics store carries its own ``("segment", segment)`` bucket per
    segment (see lgd._lgd_store_key), sourced straight from the portfolio
    workbook."""
    from . import lgd as lgd_domain

    cycle_data = (data.get("lgd_observations_by_cycle") or {}).get(reporting_cycle)
    lgd_domain.set_lgd_metrics(
        cycle_data.get("metrics_store") if cycle_data else None,
        cycle_data.get("quarters") if cycle_data else [],
    )

    rows: list[dict[str, Any]] = []
    for segment in data.get("segment_values", []):
        metric_rows = lgd_domain.lgd_metrics_by_period(data, None, segment)
        if not metric_rows:
            continue
        metric_by_quarter = {row["Monitoring Period"]: row for row in metric_rows}
        calibration_trend = {row["quarter"]: row for row in lgd_domain.build_lgd_calibration_rag_trend(data, metric_rows)}
        discrimination_trend = {row["quarter"]: row for row in lgd_domain.build_lgd_discrimination_rag_trend(data, metric_rows)}
        for quarter, cal_row in calibration_trend.items():
            disc_row = discrimination_trend.get(quarter, {})
            calibration_rag = cal_row.get("rag", "N/A")
            discrimination_rag = disc_row.get("rag", "N/A")
            psi_value = metric_by_quarter.get(quarter, {}).get("Population Stability Index")
            rows.append({
                "Monitoring Period": quarter,
                "Model Group": "LGD",
                "Segment": segment,
                "Calibration RAG": calibration_rag,
                "Discrimination RAG": discrimination_rag,
                "Overall RAG": get_worst_pd_rag([calibration_rag, discrimination_rag]),
                "PSI RAG": lgd_domain.lgd_metric_rag(data, "Population Stability Index", psi_value),
                "PSI Metric": f"{psi_value:.3f}" if psi_value is not None else "—",
                **_review_flow_rags_from_metric_row(metric_by_quarter.get(quarter)),
            })
    return rows


def _ead_segment_rows(data: dict, reporting_cycle: str) -> list[dict[str, Any]]:
    """EAD's segment-level equivalent of ``_ead_rows`` -- see _lgd_segment_rows."""
    from . import ead as ead_domain

    cycle_data = (data.get("ead_observations_by_cycle") or {}).get(reporting_cycle)
    ead_domain.set_ead_metrics(
        cycle_data.get("metrics_store") if cycle_data else None,
        cycle_data.get("quarters") if cycle_data else [],
    )

    rows: list[dict[str, Any]] = []
    for segment in data.get("segment_values", []):
        metric_rows = ead_domain.ead_metrics_by_period(data, None, segment)
        if not metric_rows:
            continue
        metric_by_quarter = {row["Monitoring Period"]: row for row in metric_rows}
        calibration_trend = {row["quarter"]: row for row in ead_domain.build_ead_calibration_rag_trend(data, metric_rows)}
        discrimination_trend = {row["quarter"]: row for row in ead_domain.build_ead_discrimination_rag_trend(data, metric_rows)}
        for quarter, cal_row in calibration_trend.items():
            disc_row = discrimination_trend.get(quarter, {})
            calibration_rag = cal_row.get("rag", "N/A")
            discrimination_rag = disc_row.get("rag", "N/A")
            psi_value = metric_by_quarter.get(quarter, {}).get("Population Stability Index")
            rows.append({
                "Monitoring Period": quarter,
                "Model Group": "EAD",
                "Segment": segment,
                "Calibration RAG": calibration_rag,
                "Discrimination RAG": discrimination_rag,
                "Overall RAG": get_worst_pd_rag([calibration_rag, discrimination_rag]),
                "PSI RAG": ead_domain.ead_metric_rag(data, "Population Stability Index", psi_value),
                "PSI Metric": f"{psi_value:.3f}" if psi_value is not None else "—",
                **_review_flow_rags_from_metric_row(metric_by_quarter.get(quarter)),
            })
    return rows


def _loss_segment_rows(data: dict, reporting_cycle: str) -> list[dict[str, Any]]:
    """Loss's segment-level equivalent of ``_loss_rows`` -- see _lgd_segment_rows."""
    from . import loss as loss_domain

    cycle_data = (data.get("loss_observations_by_cycle") or {}).get(reporting_cycle)
    loss_domain.set_loss_metrics(
        cycle_data.get("metrics_store") if cycle_data else None,
        cycle_data.get("quarters") if cycle_data else [],
    )

    rows: list[dict[str, Any]] = []
    for segment in data.get("segment_values", []):
        metric_rows = loss_domain.loss_metrics_by_period(data, None, segment)
        for row in metric_rows:
            rag = loss_domain.loss_metric_rag(data, "ME %", row.get("ME %"))
            rows.append({
                "Monitoring Period": row["Monitoring Period"],
                "Model Group": "Loss",
                "Segment": segment,
                "Calibration RAG": rag,
                "Discrimination RAG": "N/A",
                "Overall RAG": rag,
            })
    return rows


def _lgd_rows(data: dict, reporting_cycle: str) -> list[dict[str, Any]]:
    from . import lgd as lgd_domain

    cycle_data = (data.get("lgd_observations_by_cycle") or {}).get(reporting_cycle)
    lgd_domain.set_lgd_metrics(
        cycle_data.get("metrics_store") if cycle_data else None,
        cycle_data.get("quarters") if cycle_data else [],
    )

    rows: list[dict[str, Any]] = []
    for model_name in model_names("lgd"):
        metric_rows = lgd_domain.lgd_metrics_by_period(data, model_name, "All")
        if not metric_rows:
            continue
        metric_by_quarter = {row["Monitoring Period"]: row for row in metric_rows}
        calibration_trend = {row["quarter"]: row for row in lgd_domain.build_lgd_calibration_rag_trend(data, metric_rows)}
        discrimination_trend = {row["quarter"]: row for row in lgd_domain.build_lgd_discrimination_rag_trend(data, metric_rows)}
        for quarter, cal_row in calibration_trend.items():
            disc_row = discrimination_trend.get(quarter, {})
            calibration_rag = cal_row.get("rag", "N/A")
            discrimination_rag = disc_row.get("rag", "N/A")
            psi_value = metric_by_quarter.get(quarter, {}).get("Population Stability Index")
            rows.append({
                "Monitoring Period": quarter,
                "Model Group": "LGD",
                "Model": model_name,
                "Segment": "All",
                "Calibration RAG": calibration_rag,
                "Discrimination RAG": discrimination_rag,
                "Overall RAG": get_worst_pd_rag([calibration_rag, discrimination_rag]),
                "PSI RAG": lgd_domain.lgd_metric_rag(data, "Population Stability Index", psi_value),
                "PSI Metric": f"{psi_value:.3f}" if psi_value is not None else "—",
                **_review_flow_rags_from_metric_row(metric_by_quarter.get(quarter)),
            })
    return rows


def _ead_rows(data: dict, reporting_cycle: str) -> list[dict[str, Any]]:
    from . import ead as ead_domain

    cycle_data = (data.get("ead_observations_by_cycle") or {}).get(reporting_cycle)
    ead_domain.set_ead_metrics(
        cycle_data.get("metrics_store") if cycle_data else None,
        cycle_data.get("quarters") if cycle_data else [],
    )

    rows: list[dict[str, Any]] = []
    for model_name in model_names("ead"):
        metric_rows = ead_domain.ead_metrics_by_period(data, model_name, "All")
        if not metric_rows:
            continue
        metric_by_quarter = {row["Monitoring Period"]: row for row in metric_rows}
        calibration_trend = {row["quarter"]: row for row in ead_domain.build_ead_calibration_rag_trend(data, metric_rows)}
        discrimination_trend = {row["quarter"]: row for row in ead_domain.build_ead_discrimination_rag_trend(data, metric_rows)}
        for quarter, cal_row in calibration_trend.items():
            disc_row = discrimination_trend.get(quarter, {})
            calibration_rag = cal_row.get("rag", "N/A")
            discrimination_rag = disc_row.get("rag", "N/A")
            psi_value = metric_by_quarter.get(quarter, {}).get("Population Stability Index")
            rows.append({
                "Monitoring Period": quarter,
                "Model Group": "EAD",
                "Model": model_name,
                "Segment": "All",
                "Calibration RAG": calibration_rag,
                "Discrimination RAG": discrimination_rag,
                "Overall RAG": get_worst_pd_rag([calibration_rag, discrimination_rag]),
                "PSI RAG": ead_domain.ead_metric_rag(data, "Population Stability Index", psi_value),
                "PSI Metric": f"{psi_value:.3f}" if psi_value is not None else "—",
                **_review_flow_rags_from_metric_row(metric_by_quarter.get(quarter)),
            })
    return rows


def _loss_rows(data: dict, reporting_cycle: str) -> list[dict[str, Any]]:
    from . import loss as loss_domain

    cycle_data = (data.get("loss_observations_by_cycle") or {}).get(reporting_cycle)
    loss_domain.set_loss_metrics(
        cycle_data.get("metrics_store") if cycle_data else None,
        cycle_data.get("quarters") if cycle_data else [],
    )

    model_label = (model_names("loss") or ["All Models"])[0]
    metric_rows = loss_domain.loss_metrics_by_period(data, model_label, "All")

    rows: list[dict[str, Any]] = []
    for row in metric_rows:
        rag = loss_domain.loss_metric_rag(data, "ME %", row.get("ME %"))
        rows.append({
            "Monitoring Period": row["Monitoring Period"],
            "Model Group": "Loss",
            "Model": model_label,
            "Segment": "All",
            "Calibration RAG": rag,
            "Discrimination RAG": "N/A",
            "Overall RAG": rag,
        })
    return rows


def build_overview_rows(data: dict, reporting_cycle: str) -> list[dict[str, Any]]:
    """Build the full cross-portfolio row set for one reporting cycle.

    PD, LGD, EAD, and Loss each keep a separate precomputed metrics store per
    reporting cycle, so every row builder needs ``reporting_cycle`` to pick
    the right one -- mirroring how each tab's own callback scopes its data.
    """
    return _pd_rows(data, reporting_cycle) + _lgd_rows(data, reporting_cycle) + _ead_rows(data, reporting_cycle) + _loss_rows(data, reporting_cycle)


# ---------------------------------------------------------------------------
# Segment rows (Chapter 2) -- every model group's book of business sliced by
# portfolio segment instead of by model, mirroring build_overview_rows'
# per-group structure (PD pools its models per segment; LGD/EAD/Loss each
# read their own precomputed segment-level bucket).
# ---------------------------------------------------------------------------


def build_overview_segment_rows(data: dict, reporting_cycle: str) -> list[dict[str, Any]]:
    return (
        _pd_segment_rows(data, reporting_cycle)
        + _lgd_segment_rows(data, reporting_cycle)
        + _ead_segment_rows(data, reporting_cycle)
        + _loss_segment_rows(data, reporting_cycle)
    )


# ---------------------------------------------------------------------------
# Scoping
# ---------------------------------------------------------------------------


def available_periods(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({row["Monitoring Period"] for row in rows}, key=_quarter_sort_key)


def periods_through(periods: list[str], monitoring_point: str) -> list[str]:
    """``periods`` truncated to those up to and including ``monitoring_point``.

    Returns ``periods`` unchanged when there's no explicit monitoring point
    (``"All"`` or falsy), since there's then no cutoff to trend up to.
    """
    if not monitoring_point or monitoring_point == "All":
        return periods
    cutoff = _quarter_sort_key(monitoring_point)
    return [period for period in periods if _quarter_sort_key(period) <= cutoff]


def resolve_current_rows(
    rows: list[dict[str, Any]],
    monitoring_period: str = "All",
    group_keys: tuple[str, ...] = ("Model Group", "Model"),
) -> list[dict[str, Any]]:
    """Rows for "the current state": an explicit period, or each entity's own
    latest period (entity = ``group_keys``, e.g. (Model Group, Model) or (Segment,)).

    Model groups can have different quarter ranges (PD's dataset vs. each
    LGD/EAD/Loss reporting cycle's own cutoff), so "latest" is resolved per
    entity rather than against one global max period.
    """
    if not rows:
        return []
    if monitoring_period and monitoring_period != "All":
        return [row for row in rows if row["Monitoring Period"] == monitoring_period]

    latest_by_key: dict[tuple, str] = {}
    for row in rows:
        key = tuple(row[k] for k in group_keys)
        if key not in latest_by_key or _quarter_sort_key(row["Monitoring Period"]) > _quarter_sort_key(latest_by_key[key]):
            latest_by_key[key] = row["Monitoring Period"]
    return [row for row in rows if row["Monitoring Period"] == latest_by_key[tuple(row[k] for k in group_keys)]]


def resolve_current_segment_rows(rows: list[dict[str, Any]], monitoring_period: str = "All") -> list[dict[str, Any]]:
    return resolve_current_rows(rows, monitoring_period, group_keys=("Model Group", "Segment"))


# ---------------------------------------------------------------------------
# 1. RAG Assignment overview
# ---------------------------------------------------------------------------


def overview_summary(current_rows: list[dict[str, Any]]) -> dict[str, int]:
    by_model: dict[tuple[str, str], str] = {}
    for row in current_rows:
        key = (row["Model Group"], row["Model"])
        rag = effective_rag(row["Overall RAG"])
        if key not in by_model or RAG_SCORE.get(rag, 0) >= RAG_SCORE.get(by_model[key], 0):
            by_model[key] = rag

    counts = Counter(by_model.values())
    red, amber, green = counts.get("Red", 0), counts.get("Amber", 0), counts.get("Green", 0)
    return {"models": len(by_model), "red": red, "amber": amber, "green": green, "breaches": red + amber}


def models_by_overall_rag(current_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Model names grouped by their current worst Overall RAG tone -- the
    named-model complement of overview_summary's red/amber/green counts."""
    by_model: dict[tuple[str, str], str] = {}
    for row in current_rows:
        key = (row["Model Group"], row["Model"])
        rag = effective_rag(row["Overall RAG"])
        if key not in by_model or RAG_SCORE.get(rag, 0) >= RAG_SCORE.get(by_model[key], 0):
            by_model[key] = rag

    ordered_keys = sorted(by_model, key=lambda key: (MODEL_GROUPS.index(key[0]) if key[0] in MODEL_GROUPS else 99, key[1]))
    grouped: dict[str, list[str]] = {"Red": [], "Amber": [], "Green": []}
    for group, model in ordered_keys:
        name = model if model.lower().startswith(group.lower()) else f"{group} {model}"
        grouped.setdefault(by_model[(group, model)], []).append(name)
    return grouped


def segments_by_overall_rag(current_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Segment names grouped by their current worst Overall RAG tone -- the
    named-segment complement of segment_overview_summary's red/amber/green
    counts, same convention as models_by_overall_rag."""
    by_segment: dict[tuple[str, str], str] = {}
    for row in current_rows:
        key = (row["Model Group"], row["Segment"])
        rag = effective_rag(row["Overall RAG"])
        if key not in by_segment or RAG_SCORE.get(rag, 0) >= RAG_SCORE.get(by_segment[key], 0):
            by_segment[key] = rag

    ordered_keys = sorted(by_segment, key=lambda key: (MODEL_GROUPS.index(key[0]) if key[0] in MODEL_GROUPS else 99, key[1]))
    grouped: dict[str, list[str]] = {"Red": [], "Amber": [], "Green": []}
    for group, segment in ordered_keys:
        grouped.setdefault(by_segment[(group, segment)], []).append(f"{group} · {segment}")
    return grouped


def segment_overview_summary(current_rows: list[dict[str, Any]]) -> dict[str, int]:
    by_segment: dict[tuple[str, str], str] = {}
    for row in current_rows:
        key = (row["Model Group"], row["Segment"])
        rag = effective_rag(row["Overall RAG"])
        if key not in by_segment or RAG_SCORE.get(rag, 0) >= RAG_SCORE.get(by_segment[key], 0):
            by_segment[key] = rag

    counts = Counter(by_segment.values())
    red, amber, green = counts.get("Red", 0), counts.get("Amber", 0), counts.get("Green", 0)
    return {"segments": len(by_segment), "red": red, "amber": amber, "green": green, "breaches": red + amber}


# ---------------------------------------------------------------------------
# 2. Model RAG Heatmap
# ---------------------------------------------------------------------------


def _worst_rag_from_rows(rows: list[dict[str, Any]], column: str) -> str:
    return max(
        (row.get(column, "N/A") for row in rows),
        key=lambda rag: (RAG_SCORE.get(effective_rag(rag), 0), 0 if rag == "N/A" else 1),
        default="N/A",
    )


def _worst_row_for_column(rows: list[dict[str, Any]], column: str) -> dict[str, Any] | None:
    if not rows:
        return None
    return max(
        rows,
        key=lambda row: (
            RAG_SCORE.get(effective_rag(row.get(column, "N/A")), 0),
            0 if row.get(column, "N/A") == "N/A" else 1,
        ),
    )


def heatmap_rows(current_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for model_key in sorted({(row["Model Group"], row["Model"]) for row in current_rows}, key=lambda key: (MODEL_GROUPS.index(key[0]) if key[0] in MODEL_GROUPS else 99, key[1])):
        model_rows = [row for row in current_rows if (row["Model Group"], row["Model"]) == model_key]
        selected_period = model_rows[0]["Monitoring Period"] if model_rows else ""
        entry = {
            "Monitoring Period": selected_period,
            "Model Group": model_key[0],
            "Model": model_key[1],
            **{column: _worst_rag_from_rows(model_rows, column) for column in RAG_COLUMNS},
            **{column: _worst_rag_from_rows(model_rows, column) for column in HEATMAP_FINAL_COLUMNS},
        }
        # The headline metric behind each Post Subjective Review RAG (e.g. peak
        # migration gap, latest PSI, peak shock impact) -- pulled from whichever
        # row produced that column's worst RAG, so the metric always explains
        # the color shown next to it.
        for column in POST_SUBJECTIVE_COLUMNS:
            metric_key = column.replace(" RAG", " Metric")
            worst_row = _worst_row_for_column(model_rows, column)
            entry[metric_key] = (worst_row or {}).get(metric_key, "—")
        output.append(entry)
    return output


def segment_heatmap_rows(current_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    segment_keys = sorted(
        {(row["Model Group"], row["Segment"]) for row in current_rows},
        key=lambda key: (MODEL_GROUPS.index(key[0]) if key[0] in MODEL_GROUPS else 99, key[1]),
    )
    for group, segment in segment_keys:
        segment_rows = [row for row in current_rows if row["Model Group"] == group and row["Segment"] == segment]
        selected_period = segment_rows[0]["Monitoring Period"] if segment_rows else ""
        entry = {
            "Monitoring Period": selected_period,
            "Model Group": group,
            "Segment": segment,
            **{column: _worst_rag_from_rows(segment_rows, column) for column in RAG_COLUMNS},
            **{column: _worst_rag_from_rows(segment_rows, column) for column in HEATMAP_FINAL_COLUMNS},
        }
        for column in POST_SUBJECTIVE_COLUMNS:
            metric_key = column.replace(" RAG", " Metric")
            worst_row = _worst_row_for_column(segment_rows, column)
            entry[metric_key] = (worst_row or {}).get(metric_key, "—")
        output.append(entry)
    return output


# ---------------------------------------------------------------------------
# 3. RAG Trend Analysis
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 4. Top Findings
# ---------------------------------------------------------------------------


def _finding_rank(rag: str | None) -> int:
    if effective_rag(rag) == "Red":
        return 0
    if rag == "Amber":
        return 1
    if rag == "N/A":
        return 2
    return 3


def top_findings(current_rows: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    findings = []
    for row in current_rows:
        for column in RAG_COLUMNS:
            rag = row.get(column)
            # Raw comparison (not effective_rag, which folds N/A into Amber for
            # RAG-counting purposes) -- N/A means "no data", not "a finding".
            if rag in {"Red", "Amber"}:
                findings.append({
                    "Monitoring Period": row.get("Monitoring Period", "-"),
                    "Model Group": row["Model Group"],
                    "Model": row["Model"],
                    "Segment": row.get("Segment", "All"),
                    "Metric": column,
                    "Current": display_rag(rag),
                    "RAG": rag,
                })
    findings.sort(key=lambda row: (_finding_rank(row["RAG"]), row["Model Group"], row["Model"], row["Metric"]))
    return findings[:limit] if limit is not None else findings


def segment_top_findings(current_rows: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    findings = []
    for row in current_rows:
        for column in RAG_COLUMNS:
            rag = row.get(column)
            # Raw comparison (not effective_rag, which folds N/A into Amber for
            # RAG-counting purposes) -- N/A means "no data", not "a finding".
            if rag in {"Red", "Amber"}:
                findings.append({
                    "Monitoring Period": row.get("Monitoring Period", "-"),
                    "Model Group": row["Model Group"],
                    "Segment": row["Segment"],
                    "Metric": column,
                    "Current": display_rag(rag),
                    "RAG": rag,
                })
    findings.sort(key=lambda row: (_finding_rank(row["RAG"]), row["Model Group"], row["Segment"], row["Metric"]))
    return findings[:limit] if limit is not None else findings


# ---------------------------------------------------------------------------
# 5. Governance Summary -- escalation & next steps
# ---------------------------------------------------------------------------

# Sidebar path of each model group's own Performance tab (see page_registry),
# so escalation records can link straight to the tab whose Conclusion section
# owns the review-flow RAGs being acted on.
MODEL_GROUP_TAB_PATHS = {"PD": "/", "LGD": "/lgd-performance", "EAD": "/ead-performance", "Loss": "/loss-performance"}

# (playbook field key, overview row column, display label) for the three
# review-flow stages, in pipeline order. The field keys match what
# actions.select_pd_monitoring_actions expects; the columns are the same
# portfolio-file values each tab's 3.1 Conclusion section edits.
REVIEW_FLOW_STAGES = [
    ("post_subjective", "Post Subjective Review RAG", "Post Subjective Review"),
    ("pre_mitigation", "Pre Mitigation RAG", "Pre Mitigation"),
    ("post_mitigation", "Post Mitigation RAG", "Post Mitigation"),
]

# Kept out of the escalation cards' "driven by" chips: the roll-up Performance
# verdict and the three review-flow stages are already shown as the pipeline on
# the card, so the chips list only the underlying diagnostic tests behind them.
DRIVER_EXCLUDED_COLUMNS = frozenset(
    ["Overall RAG"] + [column for _field, column, _label in REVIEW_FLOW_STAGES]
)


def _entity_label(group: str, entity: str, entity_key: str) -> str:
    if entity_key == "Segment":
        return f"{group} · {entity}"
    return entity if entity.lower().startswith(group.lower()) else f"{group} {entity}"


def _previous_post_mitigation_rag(
    scoped_rows: list[dict[str, Any]], entity_key: str, group: str, entity: str, period: str,
) -> str:
    """The entity's saved Post Mitigation RAG in the monitoring period before ``period``.

    Feeds the playbook's persistent-breach escalation (two consecutive Red
    quarters), exactly as each tab's Conclusion section detects it.
    """
    prior = [
        row for row in scoped_rows
        if row["Model Group"] == group
        and str(row.get(entity_key, "") or "") == entity
        and _quarter_sort_key(row["Monitoring Period"]) < _quarter_sort_key(period)
    ]
    if not prior:
        return ""
    latest_prior = max(prior, key=lambda row: _quarter_sort_key(row["Monitoring Period"]))
    value = str(latest_prior.get("Post Mitigation RAG", "") or "").strip()
    return value if value in ("Green", "Amber", "Red") else ""


def escalation_next_steps(
    current_rows: list[dict[str, Any]],
    scoped_rows: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    monitoring_actions: list[dict[str, Any]],
    entity_key: str = "Model",
) -> dict[str, Any]:
    """Escalation tiers with the governance playbook's next steps per entity.

    Mirrors each Performance tab's 3.1 Conclusion: an entity's review-flow RAGs
    (Post Subjective Review -> Pre Mitigation -> Post Mitigation, read from the
    same portfolio columns the tabs edit) are matched against the monitoring
    playbook via ``select_pd_monitoring_actions``, so the next step shown on the
    Overview is always the same action the tab's own Required Actions panel
    prescribes -- including the two-consecutive-Red persistent-breach protocol,
    detected from the entity's prior monitoring period in ``scoped_rows``.

    Tiers: ``escalate`` (any Red across Overall RAG, a review-flow stage, or an
    underlying test finding -- or a persistent breach), ``watch`` (Amber
    somewhere, nothing Red), ``clear`` (everything Green). Entities without
    review-flow data (e.g. the Loss workstream) still tier off their findings;
    they just carry no playbook selections.
    """
    from .actions import select_pd_monitoring_actions

    entity_keys = sorted(
        {(row["Model Group"], str(row.get(entity_key, "") or "")) for row in current_rows},
        key=lambda key: (MODEL_GROUPS.index(key[0]) if key[0] in MODEL_GROUPS else 99, key[1]),
    )
    tiers: dict[str, list[dict[str, Any]]] = {"escalate": [], "watch": [], "clear": []}
    for group, entity in entity_keys:
        if not entity:
            continue
        entity_rows = [
            row for row in current_rows
            if row["Model Group"] == group and str(row.get(entity_key, "") or "") == entity
        ]
        period = entity_rows[0].get("Monitoring Period", "")
        overall = _worst_rag_from_rows(entity_rows, "Overall RAG")
        review_flow = {field: _worst_rag_from_rows(entity_rows, column) for field, column, _ in REVIEW_FLOW_STAGES}
        has_review_flow = any(value in ("Green", "Amber", "Red") for value in review_flow.values())
        commentary = next(
            (text for row in entity_rows if (text := str(row.get("Reviewer Commentary", "") or "").strip())),
            "",
        )

        # Worst finding per metric for this entity, Red first then playbook
        # driver priority -- the "what's driving it" chips on the card. The
        # roll-up verdict (Overall/Performance RAG) and the three review-flow
        # stages are excluded: they're already shown as the pipeline above, so
        # the chips surface only the underlying diagnostic tests that drove it.
        driver_map: dict[str, str] = {}
        for finding in findings:
            if finding["Model Group"] != group or str(finding.get(entity_key, "") or "") != entity:
                continue
            if finding["RAG"] not in ("Red", "Amber"):
                continue
            metric = finding["Metric"]
            if metric in DRIVER_EXCLUDED_COLUMNS:
                continue
            if metric not in driver_map or RAG_SCORE.get(finding["RAG"], 0) > RAG_SCORE.get(driver_map[metric], 0):
                driver_map[metric] = finding["RAG"]
        drivers = sorted(driver_map.items(), key=lambda kv: (0 if kv[1] == "Red" else 1, _driver_priority(kv[0])))

        selections: list[dict[str, Any]] = []
        persistent_breach = False
        if has_review_flow and monitoring_actions:
            previous_post_mitigation = _previous_post_mitigation_rag(scoped_rows, entity_key, group, entity, period)
            selections = select_pd_monitoring_actions(monitoring_actions, review_flow, previous_post_mitigation)
            persistent_breach = any(selection.get("persistent_breach") for selection in selections)

        red_signal = (
            persistent_breach
            or overall == "Red"
            or any(value == "Red" for value in review_flow.values())
            or any(rag == "Red" for _metric, rag in drivers)
        )
        amber_signal = overall == "Amber" or any(value == "Amber" for value in review_flow.values()) or bool(drivers)
        tier = "escalate" if red_signal else ("watch" if amber_signal else "clear")

        tiers[tier].append({
            "Model Group": group,
            "Entity": entity,
            "Entity Label": _entity_label(group, entity, entity_key),
            "Monitoring Period": period,
            "Overall RAG": overall,
            "Review Flow": review_flow,
            "Has Review Flow": has_review_flow,
            "Drivers": drivers,
            "Selections": selections,
            "Persistent Breach": persistent_breach,
            "Commentary": commentary,
            "Tab Path": MODEL_GROUP_TAB_PATHS.get(group, "/"),
        })

    tiers["escalate"].sort(
        key=lambda record: (
            0 if record["Persistent Breach"] else 1,
            -sum(1 for value in record["Review Flow"].values() if value == "Red"),
            MODEL_GROUPS.index(record["Model Group"]) if record["Model Group"] in MODEL_GROUPS else 99,
            record["Entity"],
        )
    )

    counts = {tier: len(records) for tier, records in tiers.items()}
    total = sum(counts.values())
    period = current_rows[0]["Monitoring Period"] if current_rows else ""
    noun = "segment" if entity_key == "Segment" else "model"

    def _n(count: int) -> str:
        return f"{count} {noun}" if count == 1 else f"{count} {noun}s"

    if total == 0:
        narrative = f"No {noun}s are in scope for the selected filters."
    elif counts["escalate"]:
        names = ", ".join(record["Entity Label"] for record in tiers["escalate"])
        requires = "requires" if counts["escalate"] == 1 else "require"
        narrative = (
            f"As of {period}, {_n(counts['escalate'])} {requires} escalation -- Red on a review-flow stage or an "
            f"underlying test: {names}. The next steps below come from the monitoring playbook, matching each "
            f"Performance tab's own Conclusion section."
        )
        if counts["watch"]:
            is_are = "is" if counts["watch"] == 1 else "are"
            narrative += f" {_n(counts['watch'])} more {is_are} on watch with Amber findings."
    elif counts["watch"]:
        names = ", ".join(record["Entity Label"] for record in tiers["watch"])
        narrative = (
            f"As of {period}, no {noun} requires escalation, but {_n(counts['watch'])} carry Amber findings to "
            f"keep on watch: {names}."
        )
    else:
        narrative = f"As of {period}, all {_n(total)} are fully in tolerance. Continue normal monitoring."

    return {"period": period, "tiers": tiers, "counts": counts, "total": total, "narrative": narrative}
