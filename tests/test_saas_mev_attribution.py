"""Unit tests for deriving MEV time-series model attribution.

``mev_data``'s own ``Model Name`` column is unreliable -- it stays in the
workbook, but ``features/saas/repositories/loader.py`` intentionally never
reads it, deriving each row's owning model(s) from ``model_mev_map`` (built
from ``transformed_mevs_description``) instead, exploding rows whose MEV is
shared across more than one model.
"""

from __future__ import annotations

import pandas as pd

from STATpy_platform.features.saas.repositories.loader import _attribute_mev_rows_to_models

_MODEL_MEV_MAP = {
    "LGD Model A": {"transformed": {"TRANSFORMED_GDP"}, "raw": {"RAW_GDP"}},
    "EAD Model A": {"transformed": {"TRANSFORMED_GDP"}, "raw": set()},
    "PD Model A": {"transformed": {"TRANSFORMED_UNEMP"}, "raw": set()},
}


def _time_series_row(mev_name: str) -> dict:
    return {
        "Date": pd.Timestamp("2025-03-31"),
        "Quarter": 0,
        "Run For": "CCAR 2026",
        "Scenario": "baseline",
        "MEV Name": mev_name,
        "MEV Value": 1.23,
    }


def test_mev_shared_across_models_is_duplicated_once_per_model():
    df = pd.DataFrame([_time_series_row("TRANSFORMED_GDP")])
    result = _attribute_mev_rows_to_models(df, _MODEL_MEV_MAP)

    assert len(result) == 2
    assert set(result["Model Name"]) == {"LGD Model A", "EAD Model A"}


def test_mev_owned_by_a_single_model_produces_one_row():
    df = pd.DataFrame([_time_series_row("TRANSFORMED_UNEMP")])
    result = _attribute_mev_rows_to_models(df, _MODEL_MEV_MAP)

    assert len(result) == 1
    assert result.iloc[0]["Model Name"] == "PD Model A"


def test_raw_mev_resolves_via_raw_bucket():
    df = pd.DataFrame([_time_series_row("RAW_GDP")])
    result = _attribute_mev_rows_to_models(df, _MODEL_MEV_MAP)

    assert len(result) == 1
    assert result.iloc[0]["Model Name"] == "LGD Model A"


def test_mev_unclaimed_by_any_model_is_dropped():
    df = pd.DataFrame([_time_series_row("UNKNOWN_MEV")])
    result = _attribute_mev_rows_to_models(df, _MODEL_MEV_MAP)

    assert result.empty


def test_other_columns_are_preserved_on_exploded_rows():
    df = pd.DataFrame([_time_series_row("TRANSFORMED_GDP")])
    result = _attribute_mev_rows_to_models(df, _MODEL_MEV_MAP)

    for column in ("Date", "Quarter", "Run For", "Scenario", "MEV Name", "MEV Value"):
        assert (result[column] == df.iloc[0][column]).all()
