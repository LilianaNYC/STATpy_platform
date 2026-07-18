"""Regression test for the SAAS MEV chart's "Projection starts" marker.

A chart's per-model "visible date range" window can narrow the plotted data
to a span that never reaches the cycle's actual jump-off date (e.g. a purely
historical custom range). The marker/annotation used to be drawn at the
jump-off date regardless, which -- since it's on the data axis -- forced
Plotly to auto-range out to that far off-screen date, squeezing all the
actually-visible data into a sliver with overlapping tick labels.
"""

from __future__ import annotations

from datetime import date

from STATpy_platform.shared.ui.charts import build_saas_mev_time_series_figure


def _record(day, value):
    return {
        "Model Name": "Model A",
        "MEV Name": "MEV A",
        "Scenario": "baseline",
        "Run For": "Cycle A",
        "Date": day,
        "MEV Value": value,
    }


def _has_projection_starts_annotation(fig) -> bool:
    return any(getattr(annotation, "text", None) == "Projection starts" for annotation in fig.layout.annotations)


def test_projection_marker_hidden_when_visible_window_is_fully_historical():
    records = [
        _record(date(2005, 10, 1), 1.0),
        _record(date(2006, 1, 1), 1.1),
        _record(date(2008, 1, 1), 1.2),
    ]

    fig = build_saas_mev_time_series_figure(
        records,
        snapshot_period="history_projection",
        primary_run_for="Cycle A",
        projection_start_date=date(2025, 1, 1),
    )

    assert not _has_projection_starts_annotation(fig)


def test_projection_marker_hidden_when_visible_window_is_fully_projection():
    records = [
        _record(date(2026, 1, 1), 1.0),
        _record(date(2026, 4, 1), 1.1),
    ]

    fig = build_saas_mev_time_series_figure(
        records,
        snapshot_period="history_projection",
        primary_run_for="Cycle A",
        projection_start_date=date(2025, 1, 1),
    )

    assert not _has_projection_starts_annotation(fig)


def test_projection_marker_shown_when_visible_window_spans_the_jump_off_date():
    records = [
        _record(date(2024, 10, 1), 1.0),
        _record(date(2025, 1, 1), 1.1),
        _record(date(2025, 4, 1), 1.2),
    ]

    fig = build_saas_mev_time_series_figure(
        records,
        snapshot_period="history_projection",
        primary_run_for="Cycle A",
        projection_start_date=date(2025, 1, 1),
    )

    assert _has_projection_starts_annotation(fig)
