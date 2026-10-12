"""The source-data column contract.

Workbook column names are a **stable contract**, not an implementation detail:
they match the production SQL table columns, so renaming one silently
repoints the app at a column that no longer exists. The failure mode is quiet --
a missing column usually degrades to an empty option list or a skipped
write-back rather than an error (see how a mistyped ``monitoring_actions`` key
merely made the Required Actions panel vanish).

These tests pin the contract so drift fails loudly, here, instead of surfacing
as blank panels in the browser. If a rename is genuinely intended, changing
these expectations is the deliberate act of re-signing the contract.
"""

from __future__ import annotations

import pandas as pd
import pytest

from STATpy_platform.config.settings import settings
from STATpy_platform.shared.domain import constants as config

# The three columns that carry the model use case / reporting cycle, spelled
# identically in both workbooks.
CYCLE_COLUMNS = (
    config.RUN_FOR_COLUMN,          # composite, e.g. "CCAR 2026"
    config.MODEL_USE_CASE_COLUMN,   # e.g. "ST - CCAR"
    config.REPORTING_CYCLE_COLUMN,  # bare cycle, e.g. "2026"
)

# The grain columns on every portfolio metrics/projection sheet.
GRAIN_COLUMNS = (
    config.METRICS_QUARTER_COLUMN,
    config.METRICS_MODEL_COLUMN,
    config.METRICS_SEGMENT_COLUMN,
)

PORTFOLIO_SHEETS = (
    "PD_Performance_Metrics",
    "LGD_Performance_Metrics",
    "EAD_Performance_Metrics",
    "Loss_Performance_Metrics",
    "PD_Sensitivity_Projections",
    "LGD_Sensitivity_Projections",
    "EAD_Sensitivity_Projections",
)


def _columns(path, sheet_name: str) -> list[str]:
    return list(pd.read_excel(path, sheet_name=sheet_name, nrows=0).columns)


@pytest.mark.parametrize("sheet_name", PORTFOLIO_SHEETS)
def test_portfolio_sheet_carries_the_cycle_and_grain_columns(sheet_name):
    columns = _columns(settings.portfolio_file, sheet_name)
    missing = [c for c in CYCLE_COLUMNS + GRAIN_COLUMNS if c not in columns]
    assert not missing, f"{sheet_name} is missing {missing}"


def test_model_names_sheet_carries_the_same_cycle_columns():
    """The MEV workbook spells them identically -- that sameness is the point."""
    columns = _columns(settings.dummy_mev_data_file, config.DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME)
    missing = [c for c in CYCLE_COLUMNS if c not in columns]
    assert not missing, f"model_names is missing {missing}"


@pytest.mark.parametrize("sheet_name", PORTFOLIO_SHEETS)
def test_portfolio_sheets_do_not_carry_the_old_lowercase_spellings(sheet_name):
    """Guards against a half-applied rename leaving both spellings present, which
    would make the normalizer pick one and silently drop the other."""
    columns = _columns(settings.portfolio_file, sheet_name)
    stale = [c for c in ("run_for", "reporting_cycle", "model_use_case",
                         "quarter", "model", "segment") if c in columns]
    assert not stale, f"{sheet_name} still has pre-rename columns {stale}"


def test_use_case_values_are_the_agreed_set():
    """``ST - CCAR`` for CCAR cycles, ``CECL`` for the CECL cycle. A new value
    appearing here means new source data that the filters have not been told
    about yet."""
    frames = [
        pd.read_excel(settings.portfolio_file, sheet_name=name)
        for name in PORTFOLIO_SHEETS
    ]
    values = set()
    for df in frames:
        values |= {str(v).strip() for v in df[config.MODEL_USE_CASE_COLUMN].dropna().unique()}
    assert values == {"ST - CCAR", "CECL"}


def test_composite_agrees_with_its_two_parts():
    """``Run For`` must always read as ``<use case token> <cycle>`` -- the parts
    are stored, not derived, so nothing stops them drifting apart in the sheet."""
    for sheet_name in PORTFOLIO_SHEETS:
        df = pd.read_excel(settings.portfolio_file, sheet_name=sheet_name)
        trio = df[list(CYCLE_COLUMNS)].dropna().drop_duplicates()
        for composite, _use_case, cycle in trio.itertuples(index=False):
            assert str(composite).endswith(str(cycle)), (
                f"{sheet_name}: {composite!r} does not end with its "
                f"{config.REPORTING_CYCLE_COLUMN} {cycle!r}"
            )


# --- PD's monitoring point vs cohort quarter -------------------------------

def test_pd_metrics_carries_a_monitoring_point_and_the_mm_margins():
    """PD alone distinguishes the as-of date from the cohort start, because PD
    alone has a ``horizon``."""
    columns = _columns(settings.portfolio_file, "PD_Performance_Metrics")
    for name in (config.MONITORING_POINT_COLUMN, "MM_P0", "MM_Pm", "abs_delta_MM"):
        assert name in columns, f"PD_Performance_Metrics is missing {name}"


@pytest.mark.parametrize("sheet_name", ["LGD_Performance_Metrics",
                                        "EAD_Performance_Metrics",
                                        "Loss_Performance_Metrics"])
def test_the_other_metrics_sheets_have_no_monitoring_point(sheet_name):
    """They have no ``horizon``, so their ``Quarter`` is already the as-of and a
    separate column would be a duplicate. The read seam falls back to it."""
    columns = _columns(settings.portfolio_file, sheet_name)
    assert "horizon" not in columns, sheet_name
    assert config.MONITORING_POINT_COLUMN not in columns, sheet_name


def test_the_cohort_quarter_sits_one_or_two_years_behind_the_monitoring_point():
    """The rule from the production sheet: for one monitoring point, the 1y and
    nco_1y rows carry a quarter a year back and the 2y row two years back, so
    one as-of date spans three different quarters.
    """
    df = pd.read_excel(settings.portfolio_file, sheet_name="PD_Performance_Metrics")
    expected_lag = {"1y": 1, "nco_1y": 1, "2y": 2}

    def _parts(label):
        year, _, quarter = str(label).partition("Q")
        return int(year), int(quarter)

    checked = 0
    for row in df.to_dict(orient="records"):
        horizon = str(row.get("horizon") or "").strip()
        lag = expected_lag.get(horizon, 1)  # blank horizon rides with the 1y cohort
        mp_year, mp_q = _parts(row[config.MONITORING_POINT_COLUMN])
        q_year, q_q = _parts(row[config.METRICS_QUARTER_COLUMN])
        assert (mp_year - q_year, mp_q) == (lag, q_q), (
            f"{row[config.MONITORING_POINT_COLUMN]} / {horizon or 'blank'} -> "
            f"{row[config.METRICS_QUARTER_COLUMN]} (expected {lag}y back, same quarter)"
        )
        checked += 1
    assert checked > 100, checked


def test_abs_delta_mm_is_the_absolute_margin_gap():
    df = pd.read_excel(settings.portfolio_file, sheet_name="PD_Performance_Metrics")
    both = df.dropna(subset=["MM_P0", "MM_Pm", "abs_delta_MM"])
    assert len(both) > 100, len(both)
    assert ((both["abs_delta_MM"] - (both["MM_Pm"] - both["MM_P0"]).abs()).abs() < 1e-9).all()
    # Where a model has no sensitivity projections, all three stay blank
    # together rather than one of them reading as a real zero.
    missing = df[df["MM_P0"].isna()]
    assert missing["MM_Pm"].isna().all() and missing["abs_delta_MM"].isna().all()
