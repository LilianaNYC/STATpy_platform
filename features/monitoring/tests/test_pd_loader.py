from __future__ import annotations

import pandas as pd

from STATpy_platform.features.monitoring.repositories.loader import _build_metrics_store


def test_build_metrics_store_maps_total_defaults_to_1y_default_count():
    cycle_df = pd.DataFrame([
        {
            "reporting_cycle": "CCAR 2026",
            "level": "model",
            "quarter": "2026Q1",
            "model_or_segment": "PD Model A",
            "horizon": "1y",
            "total_defaults": 17,
        },
    ])

    row = _build_metrics_store(cycle_df)[("model", "PD Model A", "2026Q1", "1y")]

    assert row["default_count_1y"] == 17
    assert row["total_defaults"] == 17


def test_build_metrics_store_keeps_non_1y_total_defaults_out_of_1y_default_count():
    cycle_df = pd.DataFrame([
        {
            "reporting_cycle": "CCAR 2026",
            "level": "model",
            "quarter": "2026Q1",
            "model_or_segment": "PD Model A",
            "horizon": "2y",
            "total_defaults": 11,
        },
    ])

    row = _build_metrics_store(cycle_df)[("model", "PD Model A", "2026Q1", "2y")]

    assert row["total_defaults"] == 11
    assert row.get("default_count_1y") is None
