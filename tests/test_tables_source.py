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
    """``Run For`` -> ``reporting_cycle``, holding the **composite**, so the
    ~491 downstream references keep working unchanged.

    There is no ``cycle`` column any more: the bare cycle and the use case are
    both derived from the composite rather than stored, so the sheet carries one
    column where it used to carry three."""
    df = tables.read_table("PD_Performance_Metrics")

    assert "reporting_cycle" in df.columns
    assert config.RUN_FOR_COLUMN not in df.columns
    # the composite, not the bare cycle
    assert df["reporting_cycle"].str.contains(" ").all()

    assert "cycle" not in df.columns
    assert config.MODEL_USE_CASE_COLUMN not in df.columns
    assert config.REPORTING_CYCLE_COLUMN not in df.columns


def test_the_derived_parts_match_what_the_columns_used_to_hold():
    """The point of the deletion: deriving must give the same answers the stored
    columns did."""
    from STATpy_platform.shared.domain.reporting_cycle import split_run_for

    df = tables.read_table("PD_Performance_Metrics")
    derived = {c: split_run_for(c) for c in df["reporting_cycle"].dropna().unique()}
    assert derived, "no composites to derive from"
    for composite, parts in derived.items():
        assert parts is not None, composite
        use_case, cycle = parts
        assert composite.endswith(cycle)
        assert use_case in {"CCAR", "CECL"}


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
    # Neither workbook stores the derived parts any more -- see
    # test_no_workbook_stores_the_derived_cycle_parts.
    assert config.MODEL_USE_CASE_COLUMN not in df.columns
    assert config.REPORTING_CYCLE_COLUMN not in df.columns


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


# --- production coordinates for the portfolio tables -----------------------
#
# The whole point of the seam is that the Excel -> SQL switch is a change to
# one module. That only holds if every table carries its production address
# *before* the switch, so these pin the portfolio half of it.

_PORTFOLIO_KEYS = [key for key, spec in tables.TABLES.items() if spec.workbook == tables.PORTFOLIO]


def test_every_portfolio_table_has_production_coordinates():
    """Left as None, a portfolio table would raise "no production mapping yet"
    on the day the backend is switched -- one blank dashboard per sheet nobody
    filled in."""
    assert len(_PORTFOLIO_KEYS) >= 8, _PORTFOLIO_KEYS
    missing = [k for k in _PORTFOLIO_KEYS
               if not tables.TABLES[k].sql_object or not tables.TABLES[k].sql_database]
    assert missing == []


def test_portfolio_tables_are_per_cycle_outputs():
    """One database per active Run For, mirroring the inputs fan-out. The
    workbook keeps every cycle in one sheet, so read_table has to stitch them
    back together -- which is what the placeholder marks."""
    for key in _PORTFOLIO_KEYS:
        spec = tables.TABLES[key]
        assert spec.is_per_cycle, key
        assert spec.sql_database == "STAT_Outputs_{run_for}_BHC", key
        assert spec.database_for("CCAR 2026") == "STAT_Outputs_CCAR_2026_BHC", key


def test_portfolio_objects_are_lowercase_snake_case_in_the_output_schema():
    """Unlike the MEV tables, the logical key is *not* the production table
    name here. Anything re-deriving the object from the key would ask SQL for
    a table that does not exist."""
    for key in _PORTFOLIO_KEYS:
        assert tables.TABLES[key].sql_object == f"[output].[{key.lower()}]", key
    assert tables.TABLES["PD_Performance_Metrics"].sql_object == "[output].[pd_performance_metrics]"


def test_the_scenario_fan_out_uses_the_same_mechanism():
    """One rule for both per-cycle families, rather than a hardcoded special
    case for ``scenario`` that the portfolio tables would not benefit from."""
    scenario = tables.TABLES["scenario"]
    assert scenario.is_per_cycle
    assert scenario.database_for("CCAR 2026") == "STAT_Inputs_CCAR_2026_BHC"
    # ... and the flat config tables are not swept into it
    assert tables.TABLES["model_names"].is_per_cycle is False


def test_rules_tables_stay_file_based():
    """Thresholds are config, not run output -- coordinates would be a guess."""
    for key, spec in tables.TABLES.items():
        if spec.workbook == tables.RULES:
            assert spec.sql_object is None, key


def test_the_commented_sql_reader_is_still_valid_python():
    """It is kept inert so it cannot fail -- but commented code rots silently.
    Uncommenting it in-memory and parsing catches a stale signature or a typo
    on the day someone actually flips the backend.
    """
    import ast
    import inspect
    import textwrap

    # the contiguous commented block starting at the function
    lines = inspect.getsource(tables).splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("# def _read_sql_table"))
    end = start
    while end < len(lines) and (lines[end].startswith("#") or not lines[end].strip()):
        end += 1
    uncommented = textwrap.dedent("\n".join(
        l[2:] if l.startswith("# ") else l[1:] if l.startswith("#") else l
        for l in lines[start:end]
    ))
    ast.parse(uncommented)

    # and it must reference the names the module docstring promises it needs
    for name in ("get_sql_data", "RUN_FOR_COLUMN", "spec.is_per_cycle", "spec.database_for"):
        assert name in uncommented, f"the commented reader no longer uses {name}"


def test_normalize_flag_matches_workbook():
    """Only portfolio tables get the column swap."""
    for spec in tables.TABLES.values():
        assert spec.normalize == (spec.workbook == tables.PORTFOLIO)


# --- model codes -> descriptive names ---------------------------------------

def test_portfolio_model_codes_resolve_to_descriptive_names():
    """portfolio.xlsx stores the raw model code, mirroring the production table.
    The descriptive name is the model's identity everywhere above the seam --
    mev_catalog is keyed by it, the metrics store is keyed by it, and it is what
    the Model filter shows -- so the lookup happens once on read."""
    import pandas as pd
    from STATpy_platform.config.settings import settings

    raw = pd.read_excel(settings.portfolio_file, sheet_name="PD_Performance_Metrics")
    assert raw["Model"].astype(str).str.startswith("PD_model_").all(), "the sheet should hold codes"

    df = tables.read_table("PD_Performance_Metrics")
    assert set(df["model"]) == {"PD Model A", "PD Model D"}


def test_an_unmapped_code_passes_through_rather_than_vanishing():
    """Loss's portfolio-wide "All Models" has no catalogue entry by design. A
    code that cannot be resolved must still reach the filter -- dropping it
    would empty the tab with no error."""
    df = tables.read_table("Loss_Performance_Metrics")
    assert set(df["model"]) == {"All Models"}


def test_the_lookup_is_keyed_on_the_code_not_the_descriptive_name():
    """Guards the direction. Keyed the other way round the mapping would be a
    no-op on production data and silently leave codes in the filter."""
    lookup = tables._descriptive_name_by_code()
    assert lookup.get("PD_model_a") == "PD Model A"
    assert "PD Model A" not in lookup
    # Two codes legitimately share one descriptive name -- it is the group
    # identity, not a 1:1 rename.
    assert lookup.get("PD_model_d") == lookup.get("PD_model_e") == "PD Model D"
