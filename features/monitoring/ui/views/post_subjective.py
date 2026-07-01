"""Shared Post-Subjective Review sub-sections for the LGD & EAD tabs.

The PD Performance tab implements PSI, Scenario Ranking and Sensitivity Analysis
inline (``pd_performance.py``). LGD and EAD are structurally identical to each
other (same selection model, same metric shape), so their copies of those three
sub-sections live here once and are parameterised by :class:`PostSubjectiveConfig`.

The functionality mirrors PD exactly:

* **PSI** -- RAG-rates the Population Stability Index against the tab thresholds.
* **Scenario Ranking** -- checks projected paths stay ordered by scenario severity
  (any inversion is Red) with a scenario selector.
* **Sensitivity Analysis** -- baseline vs 2SD-shock projected value, RAG-rated by
  the relative impact against the scenario-test threshold.

Data comes from ``<tab>_sensitivity_projections`` (loaded under the generic
``projected_value`` key) and the per-period ``Population Stability Index`` metric.
"""

from __future__ import annotations

from dataclasses import dataclass

from dash import dcc, html

from .....shared.ui.controls import build_chart_header
from .....shared.ui.charts import (
    build_pd_psi_trend_figure,
    build_pd_scenario_projection_figure,
    build_pd_scenario_rank_figure,
    build_pd_sensitivity_combined_figure,
)
from .....shared.domain.calculations import calculate_pd_metric_rag, pd_tone_class
from .....shared.domain.mev_range import (
    calculate_pd_mev_worst_rag_after_quarter,
    get_mev_selected_models_simple,
    get_pd_mev_available_names_for_models,
    get_pd_mev_scenario_quarter,
)
from .cards import build_pd_section_heading, build_pd_test_card

_GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}

_SCENARIO_ORDER = {"baseline": 0, "other": 1, "intsevere": 2, "baseline_2std_shock": 3}
_RAG_HEX = {"green": "#16a34a", "amber": "#d97706", "red": "#dc2626", "neutral": "#94a3b8"}

PSI_METRIC = "Population Stability Index"


@dataclass(frozen=True)
class PostSubjectiveConfig:
    """Per-tab knobs for the shared Post-Subjective sub-sections."""

    prefix: str            # id/anchor prefix, e.g. "ead" / "lgd"
    label: str             # human label, e.g. "EAD" / "LGD"
    model_type: str        # Scenario_Test_Thresholds model_type, e.g. "EAD" / "LGD"
    sensitivity_key: str   # data payload key, e.g. "ead_sensitivity_projections"
    scenario_filter_id: str


# ---------------------------------------------------------------------------
# Formatting / shared helpers
# ---------------------------------------------------------------------------
def _fmt_pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1%}"


def _fmt_value(value: float | None) -> str:
    return "—" if value is None else f"{value:.2%}"


def _scenario_label(value: str | None) -> str:
    return str(value or "").strip() or "Scenario"


def resolve_entity(selected_model, selected_segment) -> tuple[str, str]:
    """Resolve the sensitivity row's (level, model_or_segment) from the selection."""
    segment = str(selected_segment or "").strip()
    if segment and segment.lower() not in {"all", "all segments"}:
        return "segment", selected_segment
    if isinstance(selected_model, (list, tuple, set)):
        models = sorted(str(m) for m in selected_model if m)
        if len(models) == 1:
            return "model", models[0]
        return "model", "All Models"
    model = str(selected_model or "").strip()
    if model and model.lower() not in {"all", "all models"}:
        return "model", selected_model
    return "model", "All Models"


def _projection_rows(rows, reporting_cycle, level, entity) -> list[dict]:
    return [
        row for row in rows or []
        if row.get("reporting_cycle") == reporting_cycle
        and row.get("level") == level
        and row.get("model_or_segment") == entity
        and row.get("scenario_variant")
    ]


def _available_scenarios(rows) -> list[str]:
    return sorted(
        {str(r.get("scenario_variant")) for r in rows if r.get("scenario_variant")},
        key=lambda s: (_SCENARIO_ORDER.get(str(s).lower(), 99), str(s)),
    )


def resolve_scenario_selection(rows, store: dict | None) -> list[str]:
    available = _available_scenarios(rows)
    if not available:
        return []
    selected = (store or {}).get("scenarios")
    if selected is None:
        return available
    return [s for s in selected if s in available]


def _proj(row: dict):
    value = row.get("projected_value")
    return value if value is not None else row.get("projected_pd")


def _rag_status_card(kicker, title, rag, monitoring_point, methodology, chips, footnote=None, tone=None) -> html.Article:
    active_tone = tone or pd_tone_class(rag)
    chip_nodes = [
        html.Div(
            className=f"pd-psi-threshold-mini pd-psi-threshold-mini-{chip_tone}{' is-active' if chip_tone == active_tone else ''}",
            children=[html.Span(label), html.Strong(rule)],
        )
        for label, rule, chip_tone in chips
    ]
    children = [
        html.Div(className="pd-test-card-heading", children=[html.Div([html.Span(kicker), html.Div([html.H4(title)], className="pd-card-title-row")])]),
        html.Div(rag, className="pd-test-value"),
        html.Div(f"Monitoring point: {monitoring_point}", className="pd-test-meta"),
        html.Div(className="pd-rag-card-method", children=[html.Strong("Methodology: "), methodology]),
        html.Div(className="pd-psi-threshold-mini-grid", children=chip_nodes),
    ]
    if footnote:
        children.append(html.Div(footnote, className="pd-test-footnote"))
    return html.Article(className=f"pd-test-card pd-test-{active_tone}", children=children)


def build_executive_summary(text: str, theme: str = "light") -> html.Div:
    """Executive-summary banner shown at the top of the applied content (mirrors PD)."""
    style = (
        {
            "background": "linear-gradient(180deg, rgba(21,34,56,.96) 0%, rgba(17,28,47,.97) 100%)",
            "borderLeft": "3px solid #38bdf8",
            "borderRadius": "10px",
        }
        if theme == "dark" else
        {
            "background": "linear-gradient(135deg, #eff6ff 0%, #f0f9ff 50%, #f8fafc 100%)",
            "borderLeft": "3px solid #2563eb",
            "borderRadius": "10px",
        }
    )
    return html.Div(
        className="pd-performance-note",
        style=style,
        children=[html.Strong("Executive summary: "), text],
    )


def build_getting_started_prompt(label: str, full_name: str) -> html.Section:
    """Pre-apply executive summary + how-to guide for the LGD/EAD tabs (mirrors PD)."""
    return html.Section(
        className="pd-content-section pd-live-section",
        children=[
            html.Div(
                className="pd-performance-note",
                children=[
                    html.Strong("Executive summary: "),
                    f"The {label} Performance dashboard is the monitoring view for {full_name} ({label}) models "
                    "across the wholesale portfolio. It tracks each model's calibration conservatism and "
                    "discriminatory power against agreed RAG thresholds, and adds a post subjective review layer "
                    "(population stability, scenario rank ordering, sensitivity, and MEV range) so reviewers can "
                    "judge whether model behaviour remains defensible across reporting cycles and stress scenarios.",
                ],
            ),
            html.Div(
                className="saas-model-panel-stack",
                children=[
                    html.Div(
                        className="section-card pd-mev-empty-state saas-getting-started",
                        children=[
                            html.Div(f"Getting started with the {label} Performance dashboard", className="pd-mev-chart-title"),
                            html.P(
                                "Set your filters in the top bar, then click “Apply filters” to render the dashboard. "
                                "Use the quick guide below to move from setup to analysis smoothly.",
                                className="pd-section-subtitle",
                            ),
                            html.Div(
                                className="saas-getting-started-summary",
                                children=[
                                    html.Div("Quick start", className="saas-getting-started-summary-title"),
                                    html.Div(
                                        className="saas-getting-started-highlights",
                                        children=[
                                            html.Span("1. Choose Reporting Cycle, Scenario, and Monitoring Point.", className="saas-getting-started-highlight"),
                                            html.Span("2. Pick a Segment or a Specific Model — not both.", className="saas-getting-started-highlight"),
                                            html.Span("3. Click Apply filters to load the dashboard.", className="saas-getting-started-highlight"),
                                        ],
                                    ),
                                    html.Div(
                                        "The dashboard always reflects the most recent applied filter snapshot, not any unapplied edits still sitting in the top bar.",
                                        className="saas-getting-started-summary-note",
                                    ),
                                ],
                            ),
                            html.Ol(
                                className="saas-getting-started-steps",
                                children=[
                                    html.Li([
                                        html.Strong("Pick a Reporting Cycle. "),
                                        "Choose the cycle to review (e.g. CCAR 2026). This sets which monitoring points and "
                                        "precomputed metrics are available for every section.",
                                    ]),
                                    html.Li([
                                        html.Strong("Choose a Scenario. "),
                                        "Select the macro scenario (e.g. intsevere, baseline). The scenario drives the MEV "
                                        "Range and sensitivity sections and the scenario-conditioned views.",
                                    ]),
                                    html.Li([
                                        html.Strong("Set the Monitoring Point. "),
                                        "Pick the as-of quarter for the snapshot. The available quarters follow the selected "
                                        "reporting cycle, and trends are shown up to this point.",
                                    ]),
                                    html.Li([
                                        html.Strong("Choose your population. "),
                                        "Select a Segment or a single Specific Model — these two filters are mutually "
                                        "exclusive. Leaving both at “All” reads the portfolio-level (All Models) metrics.",
                                    ]),
                                    html.Li([
                                        html.Strong("Click “Apply filters”. "),
                                        "The dashboard loads here. Nothing renders until you apply, so this starting guide "
                                        "stays visible until the first Apply.",
                                    ]),
                                    html.Li([
                                        html.Strong("Read the analysis in two chapters. "),
                                        "Once loaded, the dashboard is organised as:",
                                        html.Ul(
                                            className="saas-getting-started-substeps",
                                            children=[
                                                html.Li([
                                                    html.Strong("1. RAG Assignment — "),
                                                    f"the core model-health view: overview, calibration conservatism (Mean Error and "
                                                    f"RMSE), and discriminatory power (Kendall's Tau), RAG-rated against the {label} thresholds.",
                                                ]),
                                                html.Li([
                                                    html.Strong("2. Post Subjective Review Analysis — "),
                                                    "a review scorecard overview, then population stability (PSI), scenario rank "
                                                    "ordering, sensitivity analysis, and MEV range.",
                                                ]),
                                            ],
                                        ),
                                    ]),
                                    html.Li([
                                        html.Strong("Fine-tune within each section. "),
                                        "Many charts have Window / From / To range controls, and the Scenario Ranking section has a "
                                        "scenario selector, for on-screen analysis — these do not require re-applying the top filters.",
                                    ]),
                                    html.Li([
                                        html.Strong("Start over. "),
                                        "Refresh the page at any time to clear the dashboard and return to this starting view.",
                                    ]),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# 2.1 Overview (review scorecard)
# ---------------------------------------------------------------------------
def _review_scorecard_card(summary: dict) -> html.Article:
    """Per-test scorecard card (mirrors the PD 2.1 review card)."""
    tone = pd_tone_class(summary["rag"])
    return html.Article(
        className=f"pd-test-card pd-test-{tone} pd-review-card",
        children=[
            html.Div(
                className="pd-card-title-row",
                style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "gap": "8px"},
                children=[
                    html.H4(summary["name"]),
                    html.Span(
                        summary["rag"],
                        style={"flex": "0 0 auto", "fontSize": "11px", "fontWeight": "800",
                               "letterSpacing": "0.3px", "color": _RAG_HEX.get(tone, "#94a3b8")},
                    ),
                ],
            ),
            html.Div(summary["metric"], className="pd-test-value", style={"marginTop": "10px"}),
            html.Div(
                summary["metric_label"], className="pd-test-meta",
                style={"fontWeight": "700", "textTransform": "uppercase", "fontSize": "9.5px",
                       "letterSpacing": "0.35px", "color": "#64748b", "marginTop": "2px"},
            ),
            html.Div(summary["takeaway"], className="pd-test-meta", style={"marginTop": "8px"}),
        ],
    )


def _review_legend(label: str, count: int, tone: str) -> html.Div:
    return html.Div(
        className="pd-review-legend-chip",
        style={"display": "inline-flex", "alignItems": "center", "gap": "7px", "padding": "6px 11px",
               "border": "1px solid #dbe4f0", "borderRadius": "999px", "background": "rgba(248,250,252,.9)"},
        children=[
            html.Span(style={"width": "10px", "height": "10px", "borderRadius": "999px",
                             "background": _RAG_HEX[tone], "boxShadow": "0 0 0 2px rgba(255,255,255,.9) inset"}),
            html.Strong(str(count), style={"fontSize": "13px", "color": "#0f172a"}),
            html.Span(label, style={"fontSize": "11px", "color": "#64748b", "fontWeight": "700"}),
        ],
    )


def _mev_range_summary(cfg: PostSubjectiveConfig, data: dict, selected_model, selected_segment, reporting_cycle: str, scenario: str) -> dict:
    """Worst-case MEV-range RAG across the entity's in-scope MEVs (2.5 MEV Range)."""
    catalog = data.get("mev_catalog") or {}
    selected_models = get_mev_selected_models_simple(catalog, selected_model, selected_segment, model_type=cfg.model_type)
    available = get_pd_mev_available_names_for_models(catalog, selected_models)
    counts = {"Green": 0, "Amber": 0, "Red": 0, "N/A": 0}
    total = 0
    for model_name in selected_models:
        model_data = catalog.get(model_name, {})
        for name, mev_data in (model_data.get("mevs") or {}).items():
            if name not in available:
                continue
            sq = get_pd_mev_scenario_quarter(mev_data, reporting_cycle, scenario)
            rag = calculate_pd_mev_worst_rag_after_quarter(mev_data, sq, reporting_cycle, scenario)
            counts[rag] = counts.get(rag, 0) + 1
            total += 1
    breached = counts["Red"] + counts["Amber"]
    mev_rag = "Red" if counts["Red"] else ("Amber" if counts["Amber"] else ("Green" if total else "N/A"))
    return {
        "name": "MEV Range", "anchor": f"{cfg.prefix}-mev-range", "rag": mev_rag,
        "metric": f"{breached}/{total}" if total else "—", "metric_label": "MEVs outside dev range",
        "takeaway": (f"{counts['Red']} red · {counts['Amber']} amber across {total} MEVs at the {scenario} scenario."
                     if total else "No MEVs in scope for the current scenario."),
    }


def build_overview_section(
    cfg: PostSubjectiveConfig,
    data: dict,
    level: str,
    entity: str,
    reporting_cycle: str,
    scenario: str,
    monitoring_point: str,
    summary: dict,
    thresholds: list[dict],
    selected_model,
    selected_segment,
    store: dict | None = None,
) -> html.Section:
    """Review scorecard summarising every applicable post-subjective test.

    Mirrors the PD 2.1 overview (posture hero + per-test scorecard cards) for the
    tests that apply to LGD/EAD: PSI, Scenario Ranking, Sensitivity and MEV Range.
    (PD's Transition Matrix card is omitted -- there is no MM_P0/MM_Pm data here.)
    """
    summaries: list[dict] = []

    # PSI
    current_psi = (summary.get("current") or {}).get(PSI_METRIC)
    psi_rag = calculate_pd_metric_rag(thresholds, PSI_METRIC, current_psi) if current_psi is not None else "N/A"
    summaries.append({
        "name": "PSI", "anchor": f"{cfg.prefix}-psi", "rag": psi_rag,
        "metric": f"{current_psi:.3f}" if current_psi is not None else "—",
        "metric_label": f"Latest PSI ({monitoring_point})",
        "takeaway": "Population stability vs reference — lower is more stable (green ≤ 0.10, red > 0.25).",
    })

    # Scenario Ranking + Sensitivity (shared projection rows)
    all_rows = _projection_rows(data.get(cfg.sensitivity_key) or [], reporting_cycle, level, entity)
    if all_rows:
        selected = resolve_scenario_selection(all_rows, store)
        rank = _scenario_ranking_summary([r for r in all_rows if r.get("scenario_variant") in selected])
        summaries.append({
            "name": "Scenario Ranking", "anchor": f"{cfg.prefix}-scenario-ranking",
            "rag": "Green" if rank["status"] == "Ranking maintained" else "Red",
            "metric": rank["status"], "metric_label": f"{rank['scenario_count']} scenario paths",
            "takeaway": f"{rank['inversion_count']} rank inversion(s) over {rank['quarter_count']} quarters · "
                        f"max spread {_fmt_value(rank['max_spread'])}.",
        })
        threshold = _sensitivity_threshold(data.get("monitoring_thresholds") or {}, cfg.model_type)
        impact = _impact_summary([r for r in all_rows if r.get("scenario_variant") in {"baseline", "baseline_2std_shock"}], threshold)
        breaches = impact["total_count"] - impact["within_count"]
        summaries.append({
            "name": "Sensitivity Analysis", "anchor": f"{cfg.prefix}-sensitivity-analysis",
            "rag": {"green": "Green", "red": "Red"}.get(impact["tone"], "N/A"),
            "metric": _fmt_pct(impact["max_impact"]), "metric_label": "Peak shock impact",
            "takeaway": f"{breaches}/{impact['total_count']} quarters above the {_fmt_pct(threshold)} threshold."
                        if impact["total_count"] else "No sensitivity projection data for the current scope.",
        })
    else:
        for name, anchor, label in (("Scenario Ranking", "scenario-ranking", "scenario paths"),
                                    ("Sensitivity Analysis", "sensitivity-analysis", "Peak shock impact")):
            summaries.append({
                "name": name, "anchor": f"{cfg.prefix}-{anchor}", "rag": "N/A",
                "metric": "—", "metric_label": label,
                "takeaway": "No scenario projection data for the current scope.",
            })

    # MEV Range
    summaries.append(_mev_range_summary(cfg, data, selected_model, selected_segment, reporting_cycle, scenario))

    attention = [s for s in summaries if s["rag"] in ("Amber", "Red")]
    red = sum(1 for s in summaries if s["rag"] == "Red")
    amber = sum(1 for s in summaries if s["rag"] == "Amber")
    green = sum(1 for s in summaries if s["rag"] == "Green")
    posture_tone = "red" if red else ("amber" if amber else "green")

    return html.Section(
        id=f"{cfg.prefix}-post-subjective-overview",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.1 Overview",
                f"{cfg.label} Post Subjective Review Analysis Overview",
                "At-a-glance health of every post subjective review test for the current scope. Each card shows the "
                "worst-case RAG across the projection horizon, a headline metric, and a one-line takeaway.",
                "N/A", {"show_rag": False},
            ),
            html.Div(
                className="overview-command-hero",
                style={"marginBottom": "16px", "padding": "18px 20px"},
                children=[
                    html.Div(
                        style={"display": "flex", "flexWrap": "wrap", "alignItems": "center",
                               "justifyContent": "space-between", "gap": "14px"},
                        children=[
                            html.Div(children=[
                                html.Div("Review posture", className="overview-command-hero-kicker"),
                                html.H4(
                                    f"{len(attention)} of {len(summaries)} areas need attention",
                                    style={"margin": "0", "color": _RAG_HEX[posture_tone]},
                                ),
                            ]),
                            html.Div(
                                style={"display": "flex", "gap": "10px", "flexWrap": "wrap"},
                                children=[_review_legend("Red", red, "red"), _review_legend("Amber", amber, "amber"), _review_legend("Green", green, "green")],
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="pd-test-grid",
                style={"gridTemplateColumns": f"repeat({len(summaries)}, minmax(0, 1fr))"},
                children=[_review_scorecard_card(s) for s in summaries],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# 2.2 PSI
# ---------------------------------------------------------------------------
def build_psi_section(cfg: PostSubjectiveConfig, summary: dict, thresholds: list[dict], monitoring_point: str, theme: str = "light") -> html.Section:
    current = summary.get("current") or {}
    previous = summary.get("previous") or {}
    current_value = current.get(PSI_METRIC)
    previous_value = previous.get(PSI_METRIC)
    rag = calculate_pd_metric_rag(thresholds, PSI_METRIC, current_value)
    tone = pd_tone_class(rag)
    context = {
        "snapshot_quarter": monitoring_point or "No monitoring point",
        "previous_quarter": summary.get("previous_monitoring_point"),
    }

    if current_value is None:
        body = [
            html.Div(
                className="section-card pd-mev-empty-state",
                children=[
                    html.Div("No Population Stability Index is available", className="pd-mev-chart-title"),
                    html.P(
                        f"The {cfg.label}_Performance_Metrics sheet did not return a "
                        "population_stability_index for the selected entity / monitoring point.",
                        className="pd-section-subtitle",
                    ),
                ],
            ),
        ]
    else:
        body = [
            html.Div(
                className="pd-test-grid pd-discrimination-test-grid pd-psi-test-grid",
                children=[
                    _rag_status_card(
                        "PSI test",
                        "PSI Stability RAG",
                        rag,
                        monitoring_point,
                        "Population Stability Index on the key-driver distribution; lower PSI is a more stable population.",
                        [("Green", "value <= 0.10", "green"), ("Amber", "0.10 < value <= 0.25", "amber"), ("Red", "value > 0.25", "red")],
                        footnote="Lower PSI values indicate a more stable population.",
                        tone=tone,
                    ),
                    build_pd_test_card(
                        PSI_METRIC,
                        {PSI_METRIC: current_value},
                        {PSI_METRIC: previous_value},
                        thresholds,
                        context,
                        {
                            "card_title": PSI_METRIC,
                            "test_label": f"PSI ({cfg.label})",
                            "format": "ratio",
                            "tooltip": "Lower PSI indicates a more stable distribution.",
                        },
                    ),
                ],
            ),
        ]

    psi_trend = [
        {"quarter": row.get("Monitoring Period"), "population_stability_index": row.get(PSI_METRIC)}
        for row in (summary.get("metric_rows") or [])
        if row.get("Monitoring Period") and row.get(PSI_METRIC) is not None
    ]
    if psi_trend:
        body.append(
            html.Div(
                id=f"{cfg.prefix}-psi-trend-panel",
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        "Population Stability Index Trend",
                        "Quarter-by-quarter PSI for the selected population, with threshold bands and RAG-colored markers.",
                    ),
                    dcc.Graph(
                        id=f"{cfg.prefix}-psi-trend-chart",
                        figure=build_pd_psi_trend_figure(
                            psi_trend, {"pd_thresholds": thresholds}, monitoring_point, None, theme=theme,
                        ),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart pd-default-rate-trend-chart-medium",
                    ),
                ],
            )
        )

    return html.Section(
        id=f"{cfg.prefix}-psi",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.2 PSI",
                "Population Stability Index",
                "Tracks the stability of the scoring population over time. A rising PSI signals distribution drift "
                "that may undermine the model's calibration and discrimination.",
                rag,
                {"show_rag": False},
            ),
            *body,
        ],
    )


# ---------------------------------------------------------------------------
# 2.3 Scenario Ranking
# ---------------------------------------------------------------------------
def _scenario_ranking_summary(rows: list[dict]) -> dict:
    scenarios = _available_scenarios(rows)
    quarters = sorted({r.get("quarter") for r in rows if r.get("quarter") is not None})
    by_quarter: dict[int, list[dict]] = {}
    by_scenario: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("quarter") is not None:
            by_quarter.setdefault(int(row["quarter"]), []).append(row)
        by_scenario.setdefault(str(row.get("scenario_variant")), []).append(row)

    inversion_count = 0
    spreads = []
    for quarter in quarters:
        quarter_rows = by_quarter.get(int(quarter), [])
        values = {str(r.get("scenario_variant")): _proj(r) for r in quarter_rows if _proj(r) is not None}
        ordered = [values.get(s) for s in scenarios]
        ordered = [v for v in ordered if v is not None]
        if len(ordered) >= 2 and any(ordered[i] > ordered[i + 1] for i in range(len(ordered) - 1)):
            inversion_count += 1
        if values:
            spreads.append(max(values.values()) - min(values.values()))

    averages = {}
    for scenario, scenario_rows in by_scenario.items():
        vals = [_proj(r) for r in scenario_rows if _proj(r) is not None]
        if vals:
            averages[scenario] = sum(vals) / len(vals)
    highest = max(averages, key=averages.get) if averages else None
    status = "Ranking maintained" if inversion_count == 0 and scenarios else "Rank inversion"
    return {
        "scenario_count": len(scenarios),
        "quarter_count": len(quarters),
        "inversion_count": inversion_count,
        "max_spread": max(spreads) if spreads else None,
        "highest_scenario": _scenario_label(highest),
        "status": status,
        "tone": "green" if status == "Ranking maintained" else "red",
    }


def _scenario_filter(cfg: PostSubjectiveConfig, rows, selected) -> html.Div:
    options = [{"label": _scenario_label(s), "value": s} for s in _available_scenarios(rows)]
    return html.Div(
        className="pd-scenario-ranking-filter-row",
        children=[
            html.Div(
                className="pd-scenario-ranking-filter-copy",
                children=[
                    html.Div("Scenario selection", className="pd-scenario-ranking-filter-title"),
                    html.P("Choose which scenario paths to include in the ranking statistics and charts.", className="pd-section-subtitle"),
                ],
            ),
            dcc.Checklist(
                id=cfg.scenario_filter_id,
                options=options,
                value=selected,
                className="pd-scenario-ranking-checklist",
                inputClassName="pd-scenario-ranking-check-input",
                labelClassName="pd-scenario-ranking-check-label",
            ),
        ],
    )


def build_scenario_ranking_section(
    cfg: PostSubjectiveConfig,
    data: dict,
    level: str,
    entity: str,
    reporting_cycle: str,
    monitoring_point: str,
    store: dict | None = None,
    theme: str = "light",
) -> html.Section:
    available_rows = _projection_rows(data.get(cfg.sensitivity_key) or [], reporting_cycle, level, entity)
    selected = resolve_scenario_selection(available_rows, store)
    rows = [r for r in available_rows if r.get("scenario_variant") in selected]
    summary = _scenario_ranking_summary(rows)
    filter_control = _scenario_filter(cfg, available_rows, selected)

    if rows:
        body = [
            filter_control,
            html.Div(
                className="pd-test-grid",
                style={"gridTemplateColumns": "repeat(2, minmax(0, 1fr))"},
                children=[
                    _rag_status_card(
                        "Ranking test",
                        "Scenario Ranking RAG",
                        summary["status"],
                        monitoring_point,
                        "Checks projected values stay ordered by scenario severity in every projection quarter; "
                        "a milder scenario outranking a more severe one is an inversion.",
                        [("Green", "0 inversions", "green"), ("Red", ">= 1 inversion", "red")],
                        footnote=f"{summary['inversion_count']} inversion(s) across {summary['quarter_count']} quarters.",
                        tone=summary["tone"],
                    ),
                    html.Article(
                        className="pd-test-card pd-test-neutral",
                        children=[
                            html.Div(className="pd-test-card-heading", children=[html.Div([html.Div([html.H4(f"Maximum {cfg.label} spread")], className="pd-card-title-row")])]),
                            html.Div(_fmt_value(summary["max_spread"]), className="pd-test-value"),
                            html.Div("Largest high-minus-low scenario gap across projection quarters.", className="pd-test-meta"),
                            html.Div(className="pd-test-card-heading", style={"marginTop": "14px"}, children=[html.Div([html.Div([html.H4(f"Highest average {cfg.label}")], className="pd-card-title-row")])]),
                            html.Div(summary["highest_scenario"], className="pd-test-value"),
                            html.Div(f"Across {summary['scenario_count']} selected scenario paths.", className="pd-test-meta"),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="pd-sensitivity-chart-grid",
                children=[
                    html.Div(
                        className="section-card pd-default-rate-trend-section pd-sensitivity-chart-card",
                        children=[
                            build_chart_header(f"Projected {cfg.label} by Scenario", f"{entity} ({level}) projected {cfg.label} paths for selected scenarios."),
                            dcc.Graph(id=f"{cfg.prefix}-scenario-projection-chart", figure=build_pd_scenario_projection_figure(rows, theme=theme), config=_GRAPH_CONFIG, className="pd-default-rate-trend-chart pd-default-rate-trend-chart-medium"),
                        ],
                    ),
                    html.Div(
                        className="section-card pd-default-rate-trend-section pd-sensitivity-chart-card",
                        children=[
                            build_chart_header("Scenario Rank Matrix", f"Rank 1 identifies the scenario with the highest projected {cfg.label} in each projection quarter."),
                            dcc.Graph(id=f"{cfg.prefix}-scenario-rank-chart", figure=build_pd_scenario_rank_figure(rows, theme=theme), config=_GRAPH_CONFIG, className="pd-default-rate-trend-chart pd-default-rate-trend-chart-medium"),
                        ],
                    ),
                ],
            ),
        ]
    else:
        body = [
            filter_control,
            html.Div(
                className="section-card pd-mev-empty-state",
                children=[
                    html.Div("No scenario projection data matches the current selection", className="pd-mev-chart-title"),
                    html.P(
                        f"Select at least one available scenario, or choose a reporting cycle, segment, or model that exists in the {cfg.label}_Sensitivity_Projections sheet.",
                        className="pd-section-subtitle",
                    ),
                ],
            ),
        ]

    return html.Section(
        id=f"{cfg.prefix}-scenario-ranking",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.3 Scenario Ranking",
                "Scenario Ranking",
                f"Compares projected {cfg.label} paths across selected scenarios and checks whether higher-stress "
                "scenarios consistently rank above lower-stress paths. Any rank inversion suggests the scenario "
                "response may need business review.",
                "N/A",
                {"show_rag": False},
            ),
            *body,
        ],
    )


# ---------------------------------------------------------------------------
# 2.4 Sensitivity Analysis
# ---------------------------------------------------------------------------
def _sensitivity_threshold(monitoring_thresholds: dict, model_type: str) -> float | None:
    rows = (monitoring_thresholds or {}).get("scenario_test_thresholds") or []
    row = next(
        (r for r in rows
         if str(r.get("test", "")).strip().lower() == "sensitivity analysis"
         and str(r.get("model_type", "")).strip().upper() == model_type.upper()),
        {},
    )
    try:
        return float(row.get("threshold"))
    except (TypeError, ValueError):
        return None


def _impact_summary(rows: list[dict], threshold: float | None) -> dict:
    baseline = {r.get("quarter"): _proj(r) for r in rows if r.get("scenario_variant") == "baseline"}
    impacts = []
    for row in rows:
        if row.get("scenario_variant") != "baseline_2std_shock":
            continue
        base = baseline.get(row.get("quarter"))
        shocked = _proj(row)
        if base and shocked is not None and base > 0:
            impacts.append(abs(shocked - base) / base)
    if not impacts:
        return {"max_impact": None, "within_count": 0, "total_count": 0, "status": "N/A", "tone": "neutral"}
    within = sum(1 for i in impacts if threshold is not None and i <= threshold)
    if threshold is None:
        status, tone = "Threshold unavailable", "neutral"
    elif within == len(impacts):
        status, tone = "Within threshold", "green"
    else:
        status, tone = "Threshold breach", "red"
    return {"max_impact": max(impacts), "within_count": within, "total_count": len(impacts), "status": status, "tone": tone}


def build_sensitivity_section(
    cfg: PostSubjectiveConfig,
    data: dict,
    level: str,
    entity: str,
    reporting_cycle: str,
    monitoring_point: str,
    theme: str = "light",
) -> html.Section:
    all_rows = _projection_rows(data.get(cfg.sensitivity_key) or [], reporting_cycle, level, entity)
    rows = [r for r in all_rows if r.get("scenario_variant") in {"baseline", "baseline_2std_shock"}]
    threshold = _sensitivity_threshold(data.get("monitoring_thresholds") or {}, cfg.model_type)
    summary = _impact_summary(rows, threshold)
    threshold_label = _fmt_pct(threshold)

    if rows:
        breaches = summary["total_count"] - summary["within_count"]
        body = [
            html.Div(
                className="pd-test-grid",
                style={"gridTemplateColumns": "repeat(2, minmax(0, 1fr))"},
                children=[
                    _rag_status_card(
                        "Sensitivity test",
                        "Scenario Test RAG",
                        summary["status"],
                        monitoring_point,
                        f"Per quarter, abs(shocked - baseline) / baseline measures how reactive projected {cfg.label} is "
                        "to a 2SD adverse MEV shock; a breach in any quarter turns the test Red.",
                        [("Green", f"<= {threshold_label}", "green"), ("Red", f"> {threshold_label}", "red")],
                        footnote=f"Lower relative impact means projected {cfg.label} is less reactive to the macro shock.",
                        tone=summary["tone"],
                    ),
                    html.Article(
                        className=f"pd-test-card pd-test-{'red' if breaches else 'green'}",
                        children=[
                            html.Div(className="pd-test-card-heading", children=[html.Div([html.Div([html.H4("Threshold Breaches")], className="pd-card-title-row")])]),
                            html.Div(f"{breaches} / {summary['total_count']}", className="pd-test-value"),
                            html.Div(f"quarters above the {threshold_label} scenario-test threshold", className="pd-test-meta"),
                            html.Div(className="pd-test-card-heading", style={"marginTop": "14px"}, children=[html.Div([html.Div([html.H4("Peak Relative Impact")], className="pd-card-title-row")])]),
                            html.Div(_fmt_pct(summary["max_impact"]), className="pd-test-value"),
                            html.Div("Largest abs(shocked - baseline) / baseline across the horizon.", className="pd-test-meta"),
                        ],
                    ),
                ],
            ),
            html.Div(
                id=f"{cfg.prefix}-sensitivity-combined-panel",
                className="section-card pd-default-rate-trend-section",
                children=[
                    build_chart_header(
                        f"Projected {cfg.label} Sensitivity & Relative Shock Impact",
                        f"{entity} ({level}): baseline vs 2SD-shock projected {cfg.label} (left) and the relative shock "
                        "impact by quarter (right), RAG-rated against the scenario-test threshold.",
                    ),
                    dcc.Graph(
                        id=f"{cfg.prefix}-sensitivity-combined-chart",
                        figure=build_pd_sensitivity_combined_figure(rows, threshold, range_value=None, theme=theme),
                        config=_GRAPH_CONFIG,
                        className="pd-default-rate-trend-chart",
                    ),
                ],
            ),
        ]
    else:
        body = [
            html.Div(
                className="section-card pd-mev-empty-state",
                children=[
                    html.Div("No sensitivity projection data matches the current filters", className="pd-mev-chart-title"),
                    html.P(
                        f"Choose a reporting cycle, segment, or model that exists in the {cfg.label}_Sensitivity_Projections sheet.",
                        className="pd-section-subtitle",
                    ),
                ],
            ),
        ]

    return html.Section(
        id=f"{cfg.prefix}-sensitivity-analysis",
        className="pd-content-section pd-live-section",
        children=[
            build_pd_section_heading(
                "2.4 Sensitivity Analysis",
                "Sensitivity Analysis",
                f"Compares baseline projected {cfg.label} values against a simultaneous 2 standard deviation shock "
                "applied to transformed MEVs.",
                "N/A",
                {"show_rag": False},
            ),
            *body,
        ],
    )
