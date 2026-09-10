"""Monitoring-only card builders, plus re-exports of the shared ones.

The metric-agnostic card and heading builders moved to :mod:`shared.ui.cards`
when the Backtesting dashboard became a second consumer. They are re-exported
here under their original ``build_pd_*`` names so this feature's six view
modules keep their existing imports unchanged -- the same module-attribute
re-export convention used elsewhere in this codebase.

What remains genuinely monitoring-only:

* :func:`build_pd_ead_card` -- the EAD-share card on the EAD section.
* the 1.1 Overview process-flow diagram builders.
"""

from __future__ import annotations

from dash import html

from .....shared.domain.calculations import (
    format_pd_compact_amount,
    format_pd_metric,
    pd_tone_class,
)

# Re-exported under their original names: shared implementations, monitoring
# spellings. Do not "clean these up" -- six view modules import them from here.
from .....shared.ui.cards import (  # noqa: F401
    _info_chip,
    _snapshot_meta,
    build_chapter_heading as build_pd_chapter_heading,
    build_section_heading as build_pd_section_heading,
    build_section_rag_card as build_pd_section_rag_card,
    build_test_card as build_pd_test_card,
    rag_dot as pd_rag_dot,
)


# ---------------------------------------------------------------------------
# EAD card (buildPdEadCard)
# ---------------------------------------------------------------------------


def build_pd_ead_card(current_summary, previous_summary, context, options=None):
    options = options or {}
    share = current_summary.get("share")
    previous_share = previous_summary.get("share")
    combined_ead = current_summary.get("combined_ead")

    share_label = "—" if share is None else f"{share * 100:.1f}%"
    previous_share_label = "—" if previous_share is None else f"{previous_share * 100:.1f}%"
    combined_label = "—" if combined_ead is None else format_pd_compact_amount(combined_ead)

    snapshot_label, snapshot_value = _snapshot_meta(context)
    current_label = options.get("current_label") or snapshot_value
    previous_label = options.get("previous_label") or context.get("previous_quarter") or "No prior quarter"

    title_row = [html.H4(options.get("card_title") or "EAD")]
    chip = _info_chip(options.get("tooltip"))
    if chip is not None:
        title_row.append(chip)

    heading_left = []
    if options.get("test_label"):
        heading_left.append(html.Span(options["test_label"]))
    heading_left.append(html.Div(title_row, className="pd-card-title-row"))

    return html.Article(
        className=f"pd-test-card {options.get('extra_class', '')}".strip(),
        children=[
            html.Div(className="pd-test-card-heading", children=[html.Div(heading_left)]),
            html.Div(format_pd_compact_amount(current_summary.get("ead")), className="pd-test-value"),
            html.Div(f"{snapshot_label}: {current_label}", className="pd-test-meta"),
            html.Div(f"% EAD: {share_label} of combined {combined_label}", className="pd-test-meta"),
            html.Div(
                className="pd-performance-comparison",
                children=[
                    html.Div([
                        html.Span(f"Previous ({previous_label})"),
                        html.Strong(format_pd_compact_amount(previous_summary.get("ead"))),
                    ]),
                    html.Div([
                        html.Span("Previous % EAD"),
                        html.Strong(previous_share_label),
                    ]),
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# 1.1 Overview "RAG Assignment Overview" process-flow diagram
# (buildPdOverviewFlow* / buildPdOverviewHeatmap)
# ---------------------------------------------------------------------------


def _flow_connector_spans(options):
    spans = []
    if options.get("incoming"):
        spans.append(html.Span(className="pd-overview-flow-connector pd-overview-flow-connector-in", **{"aria-hidden": "true"}))
    if options.get("outgoing"):
        spans.append(html.Span(className="pd-overview-flow-connector pd-overview-flow-connector-out", **{"aria-hidden": "true"}))
    return spans


def build_pd_overview_flow_stage(number, title, subtitle=""):
    label = " ".join(part for part in (number, title, subtitle) if part)
    return html.Div(html.Span(label), className="pd-overview-flow-stage")


def build_pd_overview_flow_input(label, options=None):
    options = options or {}
    children = [html.Strong(label)]
    if options.get("note"):
        children.append(html.Span(options["note"]))
    extra_class = options.get("extra_class", "")
    return html.Div(children, className=f"pd-overview-flow-input {extra_class}".strip())


def build_pd_overview_flow_metric(label, value, fmt, rag, options=None):
    options = options or {}
    tone = pd_tone_class(options.get("rag_override") or rag)

    if options.get("is_rag"):
        value_markup = [pd_rag_dot(value), f" {value}"]
    else:
        value_markup = format_pd_metric(value, fmt)

    label_children = [label]
    chip = _info_chip(options.get("tooltip"))
    if chip is not None:
        label_children.append(chip)

    body_children = _flow_connector_spans(options)
    body_children.append(html.Span(label_children, className="pd-overview-flow-node-label"))
    value_class = "pd-overview-flow-node-value" + (" pd-overview-flow-node-value-rag" if options.get("is_rag") else "")
    body_children.append(html.Span(value_markup, className=value_class))
    if options.get("note"):
        body_children.append(html.Span(options["note"], className="pd-overview-flow-node-note"))

    if options.get("href"):
        body = html.A(
            body_children,
            className="pd-overview-flow-link",
            href=options["href"],
            **{"aria-label": f"Jump to {label} section"},
        )
    else:
        body = body_children

    extra_class = options.get("extra_class", "")
    return html.Article(body, className=f"pd-overview-flow-node pd-overview-flow-node-{tone} {extra_class}".strip())


def build_pd_overview_flow_test_stack(metrics, options=None):
    options = options or {}
    children = _flow_connector_spans(options) + list(metrics)
    extra_class = options.get("extra_class", "")
    return html.Div(children, className=f"pd-overview-flow-test-stack {extra_class}".strip())


def build_pd_overview_flow_pass_through(extra_class=""):
    children = [
        html.Span(className="pd-overview-flow-connector pd-overview-flow-connector-in", **{"aria-hidden": "true"}),
        html.Span(className="pd-overview-flow-connector pd-overview-flow-connector-out", **{"aria-hidden": "true"}),
    ]
    return html.Div(
        children,
        className=f"pd-overview-flow-pass-through {extra_class}".strip(),
        **{"aria-hidden": "true"},
    )


def build_pd_overview_flow_performance(overview):
    performance_pd = overview["performance_pd"]
    rag = performance_pd["rag"]
    tone = pd_tone_class(rag)
    return html.Article(
        className=f"pd-overview-flow-performance pd-overview-flow-performance-{tone}",
        children=[
            html.Span(
                ["Performance RAG", _info_chip(performance_pd.get("tooltip"))],
                className="pd-overview-flow-performance-title",
            ),
            html.Strong([pd_rag_dot(rag), f" {rag}"]),
        ],
    )


def _flow_note_options(note, href):
    """Flow-node options carrying an optional fallback note. The metric value is
    suppressed to ``None`` upstream when a note is present, so the node shows only
    the RAG-toned ``—`` plus this note explaining the fallback."""
    options = {"href": href}
    if note:
        options["note"] = note
    return options


def _notching_flow_options(source, href):
    """Flow-node options for a Notching Test node, flagging a not-calculated
    (Non-Applicable) metric. The value/RAG are already suppressed to
    ``None``/``"N/A"`` upstream so the node renders no number."""
    note = source.get("notching_flow_note") or "Fallback Amber applied" if source.get("notching_non_applicable") else None
    return _flow_note_options(note, href)


def build_pd_overview_heatmap(overview):
    """Port of ``buildPdOverviewHeatmap``: the 5-stage 1.1 Overview process-flow diagram."""
    calibration = overview["calibration"]
    discrimination = overview["discrimination"]
    balance_sheet = overview["balance_sheet"]
    one_year = calibration.get("one_year") or {}
    two_year = calibration.get("two_year") or {}

    ecl_pit_calibration_summary = build_pd_overview_flow_metric(
        "Calibration Conservatism RAG (ECL PIT)", calibration.get("overall_rag"), "rag", calibration.get("overall_rag"),
        options={
            "is_rag": True,
            "href": "#pd-calibration-rag",
            "tooltip": calibration.get("tooltip"),
            "outgoing": True,
            "extra_class": "pd-flow-dimension-calibration",
        },
    )
    discrimination_summary = build_pd_overview_flow_metric(
        "Discriminatory Power RAG (ECL PIT)", discrimination.get("overall_rag"), "rag", discrimination.get("overall_rag"),
        options={
            "is_rag": True,
            "href": "#pd-discrimination-rag",
            "tooltip": discrimination.get("tooltip"),
            "incoming": True,
            "outgoing": True,
            "extra_class": "pd-flow-dimension-discrimination",
        },
    )
    balance_sheet_summary = build_pd_overview_flow_metric(
        "Calibration Conservatism RAG (Balance Sheet)", balance_sheet.get("overall_rag"), "rag", balance_sheet.get("overall_rag"),
        options={
            "is_rag": True,
            "href": "#pd-balance-sheet-calibration",
            "tooltip": balance_sheet.get("assignment_tooltip"),
            "incoming": True,
            "outgoing": True,
            "extra_class": "pd-flow-dimension-balance",
        },
    )

    flow_children = [
        html.Div(build_pd_overview_flow_stage("1.", "Components"), className="pd-flow-stage-input"),
        html.Div(build_pd_overview_flow_stage("2.", "Tests"), className="pd-flow-stage-tests"),
        html.Div(build_pd_overview_flow_stage("3.", "RAG Assignment"), className="pd-flow-stage-assignment"),
        html.Div(build_pd_overview_flow_stage("4.", "Monitoring Dimension RAG"), className="pd-flow-stage-dimension"),
        html.Div(build_pd_overview_flow_stage("5.", "Performance RAG"), className="pd-flow-stage-performance"),

        html.Div(build_pd_overview_flow_input("ECL PIT PD", {"extra_class": "pd-overview-flow-input-ecl"}), className="pd-flow-input-ecl"),
        html.Div(build_pd_overview_flow_input("Balance Sheet PD", {"extra_class": "pd-overview-flow-input-balance"}), className="pd-flow-input-balance"),

        build_pd_overview_flow_test_stack(
            [
                build_pd_overview_flow_metric("Notching Test 1 year", one_year.get("notching_value"), "count", one_year.get("notching_rag"), _notching_flow_options(one_year, "#pd-calibration-rag")),
                build_pd_overview_flow_metric("Confidence Interval 1 year", one_year.get("confidence_value"), "percent", one_year.get("confidence_rag"), {"href": "#pd-calibration-rag"}),
            ],
            {"incoming": True, "extra_class": "pd-flow-tests-calibration-1"},
        ),

        build_pd_overview_flow_metric(
            "RAG Assignment 1 year", one_year.get("assignment_rag"), "rag", one_year.get("assignment_rag"),
            options={
                "is_rag": True,
                "href": "#pd-calibration-rag",
                "tooltip": one_year.get("assignment_tooltip"),
                "incoming": True,
                "outgoing": True,
                "extra_class": "pd-flow-assignment-1",
            },
        ),

        build_pd_overview_flow_test_stack(
            [
                build_pd_overview_flow_metric("Notching Test 2 year", two_year.get("notching_value"), "count", two_year.get("notching_rag"), _notching_flow_options(two_year, "#pd-calibration-rag")),
                build_pd_overview_flow_metric("Confidence Interval 2 year", two_year.get("confidence_value"), "percent", two_year.get("confidence_rag"), {"href": "#pd-calibration-rag"}),
            ],
            {"incoming": True, "extra_class": "pd-flow-tests-calibration-2"},
        ),

        build_pd_overview_flow_metric(
            "RAG Assignment 2 year", two_year.get("assignment_rag"), "rag", two_year.get("assignment_rag"),
            options={
                "is_rag": True,
                "href": "#pd-calibration-rag",
                "tooltip": two_year.get("assignment_tooltip"),
                "incoming": True,
                "outgoing": True,
                "extra_class": "pd-flow-assignment-2",
            },
        ),

        build_pd_overview_flow_test_stack(
            [
                build_pd_overview_flow_metric("Accuracy Ratio 1 year", discrimination.get("accuracy_value"), "ratio", discrimination.get("accuracy_rag"), _flow_note_options(discrimination.get("accuracy_flow_note"), "#pd-discrimination-rag")),
                build_pd_overview_flow_metric("Delta Accuracy Ratio 1 year", discrimination.get("delta_value"), "ratio", discrimination.get("delta_rag"), _flow_note_options(discrimination.get("delta_flow_note"), "#pd-discrimination-rag")),
            ],
            {"incoming": True, "extra_class": "pd-flow-tests-discrimination"},
        ),

        build_pd_overview_flow_pass_through("pd-flow-pass-discrimination"),

        build_pd_overview_flow_test_stack(
            [
                build_pd_overview_flow_metric("Notching Test 1 year", balance_sheet.get("notching_value"), "count", balance_sheet.get("notching_rag"), _notching_flow_options(balance_sheet, "#pd-balance-sheet-calibration")),
                build_pd_overview_flow_metric("Confidence Interval 1 year", balance_sheet.get("confidence_value"), "percent", balance_sheet.get("confidence_rag"), {"href": "#pd-balance-sheet-calibration"}),
            ],
            {"incoming": True, "extra_class": "pd-flow-tests-balance"},
        ),

        build_pd_overview_flow_pass_through("pd-flow-pass-balance"),

        ecl_pit_calibration_summary,
        discrimination_summary,
        balance_sheet_summary,

        html.Div(build_pd_overview_flow_performance(overview), className="pd-flow-performance"),
    ]

    return html.Div(
        className="pd-overview-flow-wrap",
        children=html.Div(
            flow_children,
            className="pd-overview-flow",
            **{"aria-label": "PD monitoring overview process flow"},
        ),
    )
