"""Tests for the backtesting repository: dedupe, normalisation, catalogs."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from STATpy_platform.features.backtesting.repositories import loader
from STATpy_platform.shared.domain import constants as config

SEGMENT = config.BACKTESTING_SEGMENT_COLUMN
MODEL = config.BACKTESTING_MODEL_NAME_COLUMN
SNAPSHOT = config.BACKTESTING_SNAPSHOT_COLUMN
RUN_FOR = config.BACKTESTING_RUN_FOR_COLUMN
SCENARIO = config.BACKTESTING_SCENARIO_COLUMN
JN = config.BACKTESTING_JN_FLAG_COLUMN
FACILITY = config.BACKTESTING_FACILITY_ID_COLUMN
INSTRUMENT = config.BACKTESTING_CREDIT_INSTRUMENT_ID_COLUMN
QUARTER = config.BACKTESTING_QUARTER_COLUMN
PD_VALUE = config.BACKTESTING_PD_VALUE_COLUMN
EXECUTED = config.BACKTESTING_EXECUTION_DATETIME_COLUMN


def _row(*, quarter, value, executed, facility="F-1", jn="N", model="PD_model_a"):
    return {
        SEGMENT: "Cyclical",
        MODEL: model,
        SNAPSHOT: pd.Timestamp(date(2024, 3, 31)),
        RUN_FOR: "CCAR 2025",
        SCENARIO: "Base",
        JN: jn,
        FACILITY: facility,
        INSTRUMENT: f"{facility}-1",
        QUARTER: quarter,
        PD_VALUE: value,
        EXECUTED: pd.Timestamp(executed),
    }


# ---------------------------------------------------------------------------
# Dedupe: the latest Execution Datetime wins
# ---------------------------------------------------------------------------


def test_dedupe_keeps_the_latest_execution_datetime():
    """The core dedupe guarantee: a re-run supersedes the earlier attempt."""
    frame = pd.DataFrame([
        _row(quarter=1, value=0.010, executed=datetime(2024, 4, 5, 9, 0)),    # superseded
        _row(quarter=2, value=0.011, executed=datetime(2024, 4, 5, 9, 0)),    # superseded
        _row(quarter=1, value=0.020, executed=datetime(2024, 4, 9, 14, 0)),   # the re-run
        _row(quarter=2, value=0.021, executed=datetime(2024, 4, 9, 14, 0)),
    ])

    deduped = loader.dedupe_latest_execution(frame, loader.RUN_KEY_COLUMNS)

    assert len(deduped) == 2
    assert set(deduped[EXECUTED]) == {pd.Timestamp(datetime(2024, 4, 9, 14, 0))}
    assert sorted(deduped[PD_VALUE]) == pytest.approx([0.020, 0.021])
    # The superseded values are gone entirely, not averaged in.
    assert 0.010 not in set(deduped[PD_VALUE])


def test_dedupe_is_wholesale_per_run_not_per_row():
    """A partial re-run must not be stitched together with the earlier execution.

    The first execution covered quarters 1-3; the re-run only emitted quarters
    1-2. Row-level 'latest wins' would keep quarter 3 from the *old* execution,
    producing a path assembled from two runs. Run-level dedupe drops the old
    execution entirely, so quarter 3 disappears with it.
    """
    frame = pd.DataFrame([
        _row(quarter=1, value=0.010, executed=datetime(2024, 4, 5, 9, 0)),
        _row(quarter=2, value=0.011, executed=datetime(2024, 4, 5, 9, 0)),
        _row(quarter=3, value=0.012, executed=datetime(2024, 4, 5, 9, 0)),
        _row(quarter=1, value=0.020, executed=datetime(2024, 4, 9, 14, 0)),
        _row(quarter=2, value=0.021, executed=datetime(2024, 4, 9, 14, 0)),
    ])

    deduped = loader.dedupe_latest_execution(frame, loader.RUN_KEY_COLUMNS)

    assert sorted(int(value) for value in deduped[QUARTER]) == [1, 2]
    assert 0.012 not in set(deduped[PD_VALUE])


def test_dedupe_is_per_run_key_so_other_runs_are_untouched():
    """Two runs differing only by J/N Flag are separate run keys: re-running one
    must not remove rows from the other."""
    frame = pd.DataFrame([
        _row(quarter=1, value=0.010, executed=datetime(2024, 4, 5, 9, 0), jn="N"),
        _row(quarter=1, value=0.020, executed=datetime(2024, 4, 9, 14, 0), jn="N"),
        _row(quarter=1, value=0.030, executed=datetime(2024, 4, 5, 9, 0), jn="J"),
    ])

    deduped = loader.dedupe_latest_execution(frame, loader.RUN_KEY_COLUMNS)

    by_flag = {row[JN]: row[PD_VALUE] for _, row in deduped.iterrows()}
    assert by_flag["N"] == pytest.approx(0.020)   # re-run won
    assert by_flag["J"] == pytest.approx(0.030)   # untouched


def test_dedupe_keeps_every_row_of_the_winning_execution():
    frame = pd.DataFrame([
        _row(quarter=q, value=0.01 * q, executed=datetime(2024, 4, 5, 9, 0)) for q in range(0, 10)
    ] + [
        _row(quarter=q, value=0.02 * q, executed=datetime(2024, 4, 9, 14, 0)) for q in range(0, 10)
    ])
    deduped = loader.dedupe_latest_execution(frame, loader.RUN_KEY_COLUMNS)
    assert len(deduped) == 10
    assert sorted(int(value) for value in deduped[QUARTER]) == list(range(10))


def test_dedupe_leaves_single_execution_runs_alone():
    frame = pd.DataFrame([_row(quarter=1, value=0.01, executed=datetime(2024, 4, 5, 9, 0))])
    assert len(loader.dedupe_latest_execution(frame, loader.RUN_KEY_COLUMNS)) == 1


def test_dedupe_handles_an_empty_frame():
    empty = pd.DataFrame(columns=[*loader.RUN_KEY_COLUMNS, EXECUTED, PD_VALUE])
    assert loader.dedupe_latest_execution(empty, loader.RUN_KEY_COLUMNS).empty


def test_unparseable_execution_datetime_never_wins():
    """A NaT timestamp must lose to any real one rather than sorting last and
    silently becoming the survivor."""
    frame = pd.DataFrame([
        _row(quarter=1, value=0.010, executed=datetime(2024, 4, 5, 9, 0)),
        _row(quarter=1, value=0.999, executed=datetime(2024, 4, 5, 9, 0)),
    ])
    frame.loc[1, EXECUTED] = pd.NaT

    deduped = loader.dedupe_latest_execution(frame, loader.RUN_KEY_COLUMNS)
    assert len(deduped) == 1
    assert deduped.iloc[0][PD_VALUE] == pytest.approx(0.010)


# ---------------------------------------------------------------------------
# Run keys
# ---------------------------------------------------------------------------


def test_run_key_excludes_facility_grain():
    # The run key identifies a run, not a row: facility/instrument/quarter are
    # the grain *within* a run and must not be part of its identity.
    for column in (FACILITY, INSTRUMENT, QUARTER):
        assert column not in loader.RUN_KEY_COLUMNS


def test_nco_run_key_names_three_models_and_the_loss_method():
    key = loader.run_key_columns(config.BACKTESTING_METRIC_NCO)
    assert config.BACKTESTING_PD_MODEL_NAME_COLUMN in key
    assert config.BACKTESTING_LGD_MODEL_NAME_COLUMN in key
    assert config.BACKTESTING_EAD_MODEL_NAME_COLUMN in key
    assert config.BACKTESTING_LOSS_METHOD_COLUMN in key
    # results.nco has no single "Model Name" column.
    assert MODEL not in key


def test_single_model_sheets_share_one_run_key():
    for metric in (
        config.BACKTESTING_METRIC_PD,
        config.BACKTESTING_METRIC_PD_CRR,
        config.BACKTESTING_METRIC_LGD,
        config.BACKTESTING_METRIC_EAD,
    ):
        assert loader.run_key_columns(metric) == loader.RUN_KEY_COLUMNS


def test_exposure_join_key_excludes_model_name():
    """A facility's PD model is not its EAD model, so the exposure join must not
    key on the model. This is the property the whole weighting depends on."""
    assert MODEL not in loader.EXPOSURE_JOIN_COLUMNS
    for column in (SEGMENT, SNAPSHOT, RUN_FOR, SCENARIO, JN, FACILITY, INSTRUMENT, QUARTER):
        assert column in loader.EXPOSURE_JOIN_COLUMNS


# ---------------------------------------------------------------------------
# Normalisation and catalogs
# ---------------------------------------------------------------------------


def test_normalize_coerces_dtypes_and_strips_text():
    raw = pd.DataFrame([{
        SEGMENT: "  Cyclical  ",
        MODEL: "PD_model_a",
        SNAPSHOT: "2024-03-31",
        RUN_FOR: " CCAR 2025 ",
        SCENARIO: "Base",
        JN: " N ",
        FACILITY: " F-1 ",
        INSTRUMENT: " F-1-1 ",
        QUARTER: "3",
        PD_VALUE: "0.025",
        EXECUTED: "2024-04-09 14:00:00",
    }])

    normalized = loader._normalize_frame(raw, config.BACKTESTING_METRIC_PD)
    row = normalized.iloc[0]

    assert row[SEGMENT] == "Cyclical"
    assert row[RUN_FOR] == "CCAR 2025"
    assert row[JN] == "N"
    assert row[FACILITY] == "F-1"
    assert int(row[QUARTER]) == 3
    assert row[PD_VALUE] == pytest.approx(0.025)
    assert isinstance(row[SNAPSHOT], pd.Timestamp)
    assert isinstance(row[EXECUTED], pd.Timestamp)


def test_missing_workbook_returns_empty_payload_without_raising(monkeypatch, tmp_path):
    """The payload is built at import time, so an unreadable workbook must leave
    the dashboard empty rather than break app import."""
    monkeypatch.setattr(
        type(loader.settings),
        "backtesting_results_file",
        property(lambda self: tmp_path / "does-not-exist.xlsx"),
    )
    payload = loader.load_backtesting_workbook_data()

    assert payload["loaded"] is False
    assert payload["segment_values"] == []
    for metric in config.BACKTESTING_METRIC_SHEETS:
        assert payload["metrics"][metric].empty


# ---------------------------------------------------------------------------
# Against the real workbook
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def payload():
    from STATpy_platform.config.settings import settings

    if not settings.backtesting_results_file.exists():
        pytest.skip("backtesting_results.xlsx not present")
    return loader.load_backtesting_workbook_data()


def test_real_workbook_loads_every_sheet(payload):
    assert payload["loaded"] is True
    for metric in config.BACKTESTING_METRIC_SHEETS:
        assert not payload["metrics"][metric].empty, metric


def test_real_workbook_dedupe_removed_the_superseded_rows(payload):
    # The workbook deliberately carries repeated runs; every sheet should shed
    # some rows, and none should retain a duplicated grain afterwards.
    for metric, frame in payload["metrics"].items():
        assert payload["superseded_run_counts"][metric] > 0, metric
        run_key = list(loader.run_key_columns(metric))
        grain = run_key + [FACILITY, INSTRUMENT, QUARTER]
        assert not frame.duplicated(grain).any(), metric


def test_real_workbook_catalogs_come_from_the_data(payload):
    # O&M is absent by design: the model catalogue has no PD model covering it,
    # and a facility with no PD cannot be backtested.
    assert payload["segment_values"] == ["Cyclical", "Defensive"]
    assert set(payload["scenario_values"]) == {"Base", "Adverse", "Severe"}
    assert set(payload["jn_flag_values"]) == {"J", "N"}
    assert set(payload["run_for_values"]) == {"CCAR 2025", "CCAR 2026"}
    assert payload["quarters"] == list(range(10))
    assert len(payload["snapshot_dates"]) == 9


def test_real_workbook_pd_sheets_carry_one_model_each(payload):
    assert payload["model_values"][config.BACKTESTING_METRIC_PD] == ["PD_model_a"]
    assert payload["model_values"][config.BACKTESTING_METRIC_PD_CRR] == ["PD_model_b"]


def test_real_workbook_pd_segments_match_the_model_catalogue(payload):
    """The workbook is generated to agree with model_names, so the dashboard's
    catalogue-driven cascade never offers a combination with no rows."""
    catalog = payload["model_catalog"]
    for metric, model in (
        (config.BACKTESTING_METRIC_PD, "PD_model_a"),
        (config.BACKTESTING_METRIC_PD_CRR, "PD_model_b"),
    ):
        frame = payload["metrics"][metric]
        present = set(frame[SEGMENT].unique())
        allowed = set(catalog[model]["segments"])
        assert present <= allowed, (metric, sorted(present), sorted(allowed))


def test_model_catalog_carries_attributes_for_every_model(payload):
    catalog = payload["model_catalog"]
    assert catalog["PD_model_a"]["label"] == "PD Model A"
    assert catalog["PD_model_a"]["region"] == "US"
    # PD_model_b has no Portfolio in model_names; the gap is surfaced, not hidden.
    assert catalog["PD_model_b"]["portfolio"] == config.BACKTESTING_UNASSIGNED_LABEL


def test_real_workbook_pd_populations_are_disjoint(payload):
    def pairs(metric):
        frame = payload["metrics"][metric]
        return set(map(tuple, frame[[FACILITY, INSTRUMENT]].drop_duplicates().to_numpy()))

    left = pairs(config.BACKTESTING_METRIC_PD)
    right = pairs(config.BACKTESTING_METRIC_PD_CRR)
    assert left and right
    assert not (left & right)
    # The union is what the full-population sheets cover.
    assert left | right == pairs(config.BACKTESTING_METRIC_EAD)
