"""Tests for the source-data seam (``shared.repositories.tables``).

The registry is the one place that has to stay in step with the real source
data, so the first test walks every registered table and checks it actually
resolves -- that is what catches a mistyped sheet name, which otherwise
degrades silently to an empty option list rather than an error.
"""

from __future__ import annotations

import pandas as pd
import pytest

from STATpy_platform.shared.domain import constants as config
from STATpy_platform.shared.repositories import tables


def test_every_registered_table_resolves_to_a_real_sheet():
    """Each registered key must name a sheet that exists in its workbook.

    ``Portfolio`` is the one documented exception: facility-level detail that is
    not in the bundled workbook, which ``load_portfolio`` handles by degrading to
    an empty frame.
    """
    sheets_by_workbook = {
        workbook: set(pd.ExcelFile(path_of()).sheet_names)
        for workbook, path_of in tables._WORKBOOK_PATHS.items()
    }

    missing = [
        key for key, spec in tables.TABLES.items()
        if spec.key not in sheets_by_workbook[spec.workbook]
    ]
    assert missing == [config.PORTFOLIO_SHEET_NAME]


def test_portfolio_tables_arrive_in_the_internal_column_shape():
    """``Run For`` -> ``reporting_cycle`` (composite) and ``Reporting Cycle`` ->
    ``cycle``, so the ~491 downstream references keep working unchanged."""
    df = tables.read_table("PD_Performance_Metrics")

    assert "reporting_cycle" in df.columns
    assert "cycle" in df.columns
    assert config.RUN_FOR_COLUMN not in df.columns
    # the composite, not the bare cycle
    assert df["reporting_cycle"].str.contains(" ").all()
    assert set(df[config.MODEL_USE_CASE_COLUMN].dropna().unique()) <= {"ST - CCAR", "CECL"}


def test_portfolio_grain_columns_are_folded_to_internal_keys():
    df = tables.read_table("LGD_Performance_Metrics")
    for key in ("quarter", "model", "segment"):
        assert key in df.columns
    for workbook_name in ("Quarter", "Model", "Segment"):
        assert workbook_name not in df.columns


def test_mev_tables_are_not_normalized():
    """The MEV sheets also have a ``Run For`` column, but their readers use it
    under that name -- normalizing them would silently rename it."""
    df = tables.read_table("model_names")

    assert config.RUN_FOR_COLUMN in df.columns
    assert "reporting_cycle" not in df.columns
    assert config.MODEL_USE_CASE_COLUMN in df.columns
    assert config.REPORTING_CYCLE_COLUMN in df.columns


def test_usecols_is_passed_through():
    df = tables.read_table("model_names", usecols=["Model Name"])
    assert list(df.columns) == ["Model Name"]


def test_unregistered_table_raises_a_pointed_error():
    with pytest.raises(KeyError, match="Unregistered table"):
        tables.read_table("no_such_table")


def test_registry_records_production_coordinates_for_the_config_tables():
    """The MEV/config tables have known production homes (from the commented SQL
    loader); the switch to SQL should not need to rediscover them."""
    assert tables.TABLES["model_names"].sql_database == "STAT_Config"
    assert tables.TABLES["model_names"].sql_object == "[dbo].[model_names]"
    assert tables.TABLES["scenario"].sql_object == "[input].[scenario]"


def test_normalize_flag_matches_workbook():
    """Only portfolio tables get the column swap."""
    for spec in tables.TABLES.values():
        assert spec.normalize == (spec.workbook == tables.PORTFOLIO)
