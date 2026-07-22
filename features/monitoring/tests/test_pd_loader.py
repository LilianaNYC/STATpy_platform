from __future__ import annotations

import pandas as pd

from STATpy_platform.features.monitoring.repositories.loader import _build_metrics_store, _build_model_segment_map


def test_build_metrics_store_maps_total_defaults_to_1y_default_count():
    cycle_df = pd.DataFrame([
        {
            "reporting_cycle": "CCAR 2026",
            "quarter": "2026Q1",
            "model": "PD Model A",
            "segment": "All",
            "horizon": "1y",
            "total_defaults": 17,
        },
    ])

    row = _build_metrics_store(cycle_df)[("PD Model A", "All", "2026Q1", "1y")]

    assert row["default_count_1y"] == 17
    assert row["total_defaults"] == 17


def test_build_metrics_store_keeps_non_1y_total_defaults_out_of_1y_default_count():
    cycle_df = pd.DataFrame([
        {
            "reporting_cycle": "CCAR 2026",
            "quarter": "2026Q1",
            "model": "PD Model A",
            "segment": "All",
            "horizon": "2y",
            "total_defaults": 11,
        },
    ])

    row = _build_metrics_store(cycle_df)[("PD Model A", "All", "2026Q1", "2y")]

    assert row["total_defaults"] == 11
    assert row.get("default_count_1y") is None


def test_build_model_segment_map_excludes_all_and_dedupes_per_model():
    agg_df = pd.DataFrame([
        {"model": "PD Model A", "segment": "All"},
        {"model": "PD Model A", "segment": "Cyclical"},
        {"model": "PD Model A", "segment": "Cyclical"},
        {"model": "PD Model A", "segment": "Defensive"},
        {"model": "PD Model D", "segment": "All"},
        {"model": "PD Model D", "segment": "Defensive"},
    ])

    segment_map = _build_model_segment_map(agg_df)

    assert segment_map["PD Model A"] == ["Cyclical", "Defensive"]
    assert segment_map["PD Model D"] == ["Defensive"]
