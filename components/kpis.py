"""KPI / RAG card builders for the PD Performance dashboard.

Ports the HTML card builders from ``pages/monitoring_pd_models_page.py``
(``buildPdTestCard``, ``buildPdSectionRagCard``, ``buildPdEadCard``,
``buildPdStaticInfoCard``, ``buildPdSectionHeading``,
``buildPdChapterHeading``, ``pdRagDot``) to Dash components.

``escapePdHtml`` has no equivalent here - Dash/React escapes text children
automatically, so plain strings are passed straight through.
"""

from __future__ import annotations

from dash import html

from ..data.transformations import (
    calculate_pd_metric_rag,
    fmt_n,
    format_pd_compact_amount,
    format_pd_metric,
    format_pd_rag_change,
    format_pd_test_change,
    pd_tone_class,
)


def _info_chip(tooltip: str | None):
    if not tooltip:
        return None
    return html.Span(
        "i",
        className="pd-info-chip",
        role="img",
        **{"aria-label": tooltip, "title": tooltip},
    )


def _meta_rows(rows):
    return [html.Div(f"{row['label']}: {row['value']}", className="pd-test-meta") for row in (rows or [])]


def pd_rag_dot(rag: str) -> html.Span:
    css = (rag or "N/A").lower().replace("/", "").replace(" ", "-")
    return html.Span(
        "●",
        className=f"pd-rag-dot pd-rag-{css}",
        role="img",
        **{"aria-label": rag, "title": rag},
    )


# ---------------------------------------------------------------------------
# Test / RAG cards (buildPdTestCard / buildPdSectionRagCard)
# ---------------------------------------------------------------------------


def build_pd_test_card(metric, current_values, previous_values, thresholds, context, options=None):
    options = options or {}
    fmt = options.get("format", "ratio")
    value = current_values.get(metric)
    previous_value = previous_values.get(metric)
    rag = calculate_pd_metric_rag(thresholds, metric, value)
    threshold = next((row for row in thresholds if row.get("metric") == metric), {})
    movement = format_pd_test_change(value, previous_value, fmt, threshold)

    title_row = [html.H4(options.get("card_title") or metric)]
    chip = _info_chip(options.get("tooltip"))
    if chip is not None:
        title_row.append(chip)

    heading_left = []
    if options.get("test_label"):
        heading_left.append(html.Span(options["test_label"]))
    heading_left.append(html.Div(title_row, className="pd-card-title-row"))

    return html.Article(
        className=f"pd-test-card pd-test-{pd_tone_class(rag)} {options.get('extra_class', '')}".strip(),
        children=[
            html.Div(
                className="pd-test-card-heading",
                children=[
                    html.Div(heading_left),
                    html.Div(rag, className=f"pd-test-status pd-test-status-{pd_tone_class(rag)}"),
                ],
            ),
            html.Div(format_pd_metric(value, fmt), className="pd-test-value"),
            html.Div(f"Snapshot date: {context['snapshot_quarter']}", className="pd-test-meta"),
            *_meta_rows(options.get("extra_meta_rows")),
            html.Div(
                className="pd-performance-comparison",
                children=[
                    html.Div([
                        html.Span(f"Previous ({context.get('previous_quarter') or 'No prior quarter'})"),
                        html.Strong(format_pd_metric(previous_value, fmt)),
                    ]),
                    html.Div([
                        html.Span("Change"),
                        html.Strong(movement["text"], className=f"pd-change {movement['css']}"),
                    ]),
                ],
            ),
        ],
    )


def build_pd_section_rag_card(title, current_rag, previous_rag, context, options=None):
    options = options or {}
    movement = format_pd_rag_change(current_rag, previous_rag)
    meta_label = options.get("meta_label", "Snapshot date")
    meta_value = options.get("meta_value", context.get("snapshot_quarter"))

    title_row = [html.H4(options.get("card_title") or title)]
    chip = _info_chip(options.get("tooltip"))
    if chip is not None:
        title_row.append(chip)

    heading_left = []
    if options.get("test_label"):
        heading_left.append(html.Span(options["test_label"]))
    heading_left.append(html.Div(title_row, className="pd-card-title-row"))

    heading_children = [html.Div(heading_left)]
    if not options.get("hide_status"):
        heading_children.append(html.Div(current_rag, className=f"pd-test-status pd-test-status-{pd_tone_class(current_rag)}"))

    children = [
        html.Div(className="pd-test-card-heading", children=heading_children),
        html.Div(current_rag, className="pd-test-value"),
        html.Div(f"{meta_label}: {meta_value}", className="pd-test-meta"),
        *_meta_rows(options.get("extra_meta_rows")),
    ]
    if not options.get("hide_comparison"):
        children.append(
            html.Div(
                className="pd-performance-comparison",
                children=[
                    html.Div([
                        html.Span(f"Previous ({context.get('previous_quarter') or 'No prior quarter'})"),
                        html.Strong(previous_rag),
                    ]),
                    html.Div([
                        html.Span("Change"),
                        html.Strong(movement["text"], className=f"pd-change {movement['css']}"),
                    ]),
                ],
            )
        )

    return html.Article(
        className=f"pd-test-card pd-test-{pd_tone_class(current_rag)} {options.get('extra_class', '')}".strip(),
        children=children,
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

    current_label = options.get("current_label") or context.get("snapshot_quarter")
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
            html.Div(f"Snapshot date: {current_label}", className="pd-test-meta"),
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
# Static info card (buildPdStaticInfoCard)
# ---------------------------------------------------------------------------


def build_pd_static_info_card(title, value, meta_rows=None, options=None):
    options = options or {}
    title_row = [html.H4(title)]
    chip = _info_chip(options.get("tooltip"))
    if chip is not None:
        title_row.append(chip)

    heading_left = []
    if options.get("test_label"):
        heading_left.append(html.Span(options["test_label"]))
    heading_left.append(html.Div(title_row, className="pd-card-title-row"))

    children = [
        html.Div(className="pd-test-card-heading", children=[html.Div(heading_left)]),
        html.Div(value, className="pd-test-value"),
        *_meta_rows(meta_rows),
    ]
    if options.get("footnote"):
        children.append(html.Div(options["footnote"], className="pd-test-footnote"))

    return html.Article(className=f"pd-test-card {options.get('extra_class', '')}".strip(), children=children)


# ---------------------------------------------------------------------------
# Section / chapter headings (buildPdSectionHeading / buildPdChapterHeading)
# ---------------------------------------------------------------------------


def build_pd_section_heading(index, title, description, rag, options=None):
    options = options or {}
    heading_row = [html.H3(title)]
    chip = _info_chip(options.get("tooltip"))
    if chip is not None:
        heading_row.append(chip)

    children = [
        html.Div(
            children=[
                html.Div(index, className="pd-content-kicker"),
                html.Div(heading_row, className="pd-heading-row"),
                html.P(description),
            ],
        ),
    ]

    if options.get("show_rag", True):
        status_children = [
            html.Span(options.get("status_label", "Section RAG")),
            html.Strong([pd_rag_dot(rag), f" {rag}"]),
        ]
        if options.get("status_note"):
            status_children.append(html.Small(options["status_note"]))
        children.append(html.Div(status_children, className=f"pd-domain-status pd-domain-{pd_tone_class(rag)}"))

    return html.Div(children, className="pd-domain-heading")


def build_pd_chapter_heading(index, title, description, options=None):
    options = options or {}
    children = [
        html.Div(
            className="pd-chapter-heading-copy",
            children=[
                html.Div(index, className="pd-chapter-kicker"),
                html.H2(title),
                html.P(description),
            ],
        ),
    ]
    if options.get("note"):
        children.append(html.Div(options["note"], className="pd-chapter-note"))

    extra_class = options.get("extra_class", "")
    return html.Div(children, className=f"pd-chapter-heading {extra_class}".strip())


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
                ["Performance", html.Br(), "PD RAG", _info_chip(performance_pd.get("tooltip"))],
                className="pd-overview-flow-performance-title",
            ),
            html.Strong([pd_rag_dot(rag), f" {rag}"]),
        ],
    )


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
        "Discriminatory Power RAG", discrimination.get("overall_rag"), "rag", discrimination.get("overall_rag"),
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
        html.Div(build_pd_overview_flow_stage("5.", "Performance", "PD RAG"), className="pd-flow-stage-performance"),

        html.Div(build_pd_overview_flow_input("ECL PIT PD", {"extra_class": "pd-overview-flow-input-ecl"}), className="pd-flow-input-ecl"),
        html.Div(build_pd_overview_flow_input("Balance Sheet PD", {"extra_class": "pd-overview-flow-input-balance"}), className="pd-flow-input-balance"),

        build_pd_overview_flow_test_stack(
            [
                build_pd_overview_flow_metric("Notching Test 1 year", one_year.get("notching_value"), "count", one_year.get("notching_rag"), {"href": "#pd-calibration-rag"}),
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
                build_pd_overview_flow_metric("Notching Test 2 year", two_year.get("notching_value"), "count", two_year.get("notching_rag"), {"href": "#pd-calibration-rag"}),
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
                build_pd_overview_flow_metric("Accuracy Ratio 1 year", discrimination.get("accuracy_value"), "ratio", discrimination.get("accuracy_rag"), {"href": "#pd-discrimination-rag"}),
                build_pd_overview_flow_metric("Delta Accuracy Ratio 1 year", discrimination.get("delta_value"), "ratio", discrimination.get("delta_rag"), {"href": "#pd-discrimination-rag"}),
            ],
            {"incoming": True, "extra_class": "pd-flow-tests-discrimination"},
        ),

        build_pd_overview_flow_pass_through("pd-flow-pass-discrimination"),

        build_pd_overview_flow_test_stack(
            [
                build_pd_overview_flow_metric("Notching Test 1 year", balance_sheet.get("notching_value"), "count", balance_sheet.get("notching_rag"), {"href": "#pd-balance-sheet-calibration"}),
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
