"""Shared KPI / RAG / heading card builders.

Metric-agnostic presentation components used by more than one dashboard:
Monitoring's PD/LGD/EAD/Loss pages and the Backtesting dashboard. Promoted here
from ``features/monitoring/ui/views/cards.py`` once Backtesting became a second
consumer (the "rule of two").

**The emitted CSS class names keep their ``pd-`` prefix** (``pd-test-card``,
``pd-test-status-*``, ``pd-rag-dot``, ``pd-domain-heading``,
``pd-chapter-heading``, ...). Read ``pd-`` here as a legacy prefix meaning
"platform default card chrome", not as a claim about the PD page: renaming those
classes would mean rewriting ~331 selectors in ``assets/styles.css`` and is
explicitly out of scope. Monitoring keeps importing these under their original
``build_pd_*`` names via re-export aliases, so its call sites are unchanged.

Monitoring-only card builders stay in ``features/monitoring/ui/views/cards.py``:
the EAD-share card and the 1.1 Overview process-flow diagram.

Originally ported from the HTML card builders in
``pages/monitoring_pd_models_page.py`` (``buildPdTestCard``,
``buildPdSectionRagCard``, ``buildPdSectionHeading``, ``buildPdChapterHeading``,
``pdRagDot``). ``escapePdHtml`` has no equivalent -- Dash/React escapes text
children automatically, so plain strings are passed straight through.
"""

from __future__ import annotations

from dash import html

from ..domain.calculations import (
    calculate_pd_metric_rag,
    format_pd_metric,
    format_pd_rag_change,
    format_pd_test_change,
    get_pd_quarter_years_back,
    pd_tone_class,
)


def _info_chip(tooltip: str | None):
    if not tooltip:
        return None
    return html.Span(
        "?",
        className="pd-info-chip",
        role="img",
        **{"aria-label": tooltip, "title": tooltip},
    )


def _meta_rows(rows):
    return [html.Div(f"{row['label']}: {row['value']}", className="pd-test-meta") for row in (rows or [])]


def _snapshot_meta(context) -> tuple[str, str]:
    """The card's snapshot line, as a ``(label, value)`` pair.

    A horizon-scoped test does not measure a single quarter -- it measures the
    1- or 2-year window *ending* at the monitoring point -- so it reports that
    whole window: ``Snapshot range: 2024Q2 to 2025Q2`` for a 1 year test,
    ``Snapshot range: 2023Q2 to 2025Q2`` for a 2 year one. The window length
    comes from ``horizon_years`` in the context (see
    ``get_pd_performance_context_for_horizon``, and the LGD/EAD/Loss contexts,
    whose tests are all 1 year).

    Cards whose context carries no ``horizon_years`` -- PSI, which compares the
    current snapshot against a reference rather than over a horizon -- keep the
    single-quarter ``Snapshot date``, as do contexts whose snapshot is not a
    real ``YYYYQn`` quarter (e.g. the "No monitoring point" placeholder).
    """
    quarter = context.get("snapshot_quarter")
    years = context.get("horizon_years")
    if years:
        start = get_pd_quarter_years_back(quarter, years)
        if start:
            return "Snapshot range", f"{start} to {quarter}"
    return "Snapshot date", quarter


def rag_dot(rag: str) -> html.Span:
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


def build_test_card(metric, current_values, previous_values, thresholds, context, options=None):
    options = options or {}
    fmt = options.get("format", "ratio")
    value = current_values.get(metric)
    previous_value = previous_values.get(metric)
    rag = calculate_pd_metric_rag(thresholds, metric, value)
    threshold = next((row for row in thresholds if row.get("metric") == metric), {})
    movement = format_pd_test_change(value, previous_value, fmt, threshold)

    # RAG-Assignment fallback (low default count, see resolve_fallback_rule).
    # Both outcomes show the card as Amber: "Fallback Amber" forces the test to
    # Amber outright, and a "Non-Applicable" test is likewise flagged rather than
    # greyed out to N/A -- what Non-Applicable changes is that the test drops out
    # of its dimension's RAG, which happens upstream of this card. Either way the
    # underlying metric is not a valid measurement, so its value (and
    # period-over-period comparison) are suppressed and a note explains why.
    fallback_status = options.get("fallback_status")
    fallback_note = options.get("fallback_note")
    hide_metric = fallback_status in ("fallback_amber", "non_applicable")
    if hide_metric:
        rag = "Amber"

    title_row = [html.H4(options.get("card_title") or metric)]
    chip = _info_chip(options.get("tooltip"))
    if chip is not None:
        title_row.append(chip)

    heading_left = []
    if options.get("test_label"):
        heading_left.append(html.Span(options["test_label"]))
    heading_left.append(html.Div(title_row, className="pd-card-title-row"))

    value_display = "—" if hide_metric else format_pd_metric(value, fmt)
    children = [
        html.Div(
            className="pd-test-card-heading",
            children=[
                html.Div(heading_left),
                html.Div(rag, className=f"pd-test-status pd-test-status-{pd_tone_class(rag)}"),
            ],
        ),
        html.Div(value_display, className="pd-test-value"),
    ]
    if fallback_note:
        children.append(html.Div(fallback_note, className="pd-test-fallback-note"))
    if not options.get("hide_snapshot"):
        snapshot_label, snapshot_value = _snapshot_meta(context)
        children.append(html.Div(f"{snapshot_label}: {snapshot_value}", className="pd-test-meta"))
    children.extend(_meta_rows(options.get("extra_meta_rows")))
    # Every card carries the period-over-period footer, fallback or not, so a
    # row of cards stays comparable. Change is N/A under a fallback though: it
    # would otherwise be measured against a current value the card deliberately
    # does not show. Previous stands on its own and stays as measured.
    if hide_metric:
        movement = {"text": "N/A", "css": "pd-change-neutral"}
    children.append(
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
        )
    )

    return html.Article(
        className=f"pd-test-card pd-test-{pd_tone_class(rag)} {options.get('extra_class', '')}".strip(),
        children=children,
    )


def build_section_rag_card(title, current_rag, previous_rag, context, options=None):
    options = options or {}
    movement = format_pd_rag_change(current_rag, previous_rag)
    meta_label = options.get("meta_label")
    if meta_label:
        # A caller that relabels this line (e.g. "Monitoring point") is naming a
        # single quarter, not the test's observation window.
        meta_value = options.get("meta_value", context.get("snapshot_quarter"))
    else:
        meta_label, default_meta_value = _snapshot_meta(context)
        meta_value = options.get("meta_value", default_meta_value)

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
# Section / chapter headings (buildPdSectionHeading / buildPdChapterHeading)
# ---------------------------------------------------------------------------


def build_section_heading(index, title, description, rag, options=None):
    options = options or {}
    heading_row = [html.H3(title)]
    chip = _info_chip(options.get("tooltip"))
    if chip is not None:
        heading_row.append(chip)

    copy_children = [
        html.Div(index, className="pd-content-kicker"),
        html.Div(heading_row, className="pd-heading-row"),
    ]
    if description:
        copy_children.append(html.P(description))
    main_children = [html.Div(copy_children, className="pd-domain-heading-copy")]
    aside_children = []

    if options.get("controls") is not None:
        aside_children.append(html.Div(options["controls"], className="pd-domain-heading-controls"))

    if options.get("show_rag", True):
        status_children = [
            html.Span(options.get("status_label", "Section RAG")),
            html.Strong([rag_dot(rag), f" {rag}"]),
        ]
        if options.get("status_note"):
            status_children.append(html.Small(options["status_note"]))
        aside_children.append(html.Div(status_children, className=f"pd-domain-status pd-domain-{pd_tone_class(rag)}"))

    if aside_children:
        main_children.append(html.Div(aside_children, className="pd-domain-heading-aside"))

    return html.Div([html.Div(main_children, className="pd-domain-heading-main")], className="pd-domain-heading")


def build_chapter_heading(index, title, description, options=None):
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
