"""Layout for the LGD Performance page (placeholder).

No LGD data source has been wired up yet, so this page only renders a top
bar and a placeholder card. See :mod:`pages.monitoring_pd_performance_layout`
for the fully ported page.
"""

from __future__ import annotations

from dash import html


def page_layout() -> list:
    """Top bar + placeholder content for the LGD Performance page."""
    return [
        html.Div(
            className="top-bar",
            children=[
                html.Div(
                    style={"flex": "1"},
                    children=[
                        html.Div("LGD Performance", className="monitoring-dashboard-title"),
                    ],
                ),
            ],
        ),
        html.Div(
            className="content",
            children=[
                html.Div(
                    className="section-card pd-placeholder-card",
                    children=[
                        html.Div("Placeholder page", className="pd-placeholder-badge"),
                        html.Div("LGD Performance", className="pd-placeholder-title"),
                        html.P(
                            "This page is reserved for the LGD Performance dashboard. Its layout, "
                            "data sources, and callbacks will be added here, following the same "
                            "structure as the PD Performance page."
                        ),
                    ],
                ),
            ],
        ),
    ]
