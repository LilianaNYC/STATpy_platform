"""Persistence / source-data loading for the backtesting dashboard.

Reads ``backtesting_results.xlsx`` -- five facility-grain result sheets of model
projections -- into plain Python structures, applying the run-level dedupe on
``Execution Datetime`` before anything downstream sees a row.

Feature-private: only :mod:`features.backtesting.data_access` reads from this
module. Sheet and column names come from :mod:`shared.domain.constants`; the
file location comes from :mod:`config.settings`. Nothing is inlined here.

The workbook's own contract is documented in
``source_data/Backtesting_Workbook_Guide.md``. Two properties of it shape this
module:

* **Repeated runs must be deduped wholesale.** A re-run of the same
  configuration emits a second set of rows under a later ``Execution
  Datetime``. Keeping the latest *per run key, whole run at a time* is the only
  correct reduction -- see :func:`dedupe_latest_execution`.
* **The two PD sheets cover disjoint facility populations.** ``results.pd``
  carries one PD model's facilities and ``results.pd_crr`` the other's, so a
  portfolio-level PD is the union of both. Neither sheet alone covers the book.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ....config.settings import settings
from ....shared.domain import constants as config

log = logging.getLogger(__name__)

# Key compositions live in shared/domain/constants.py so the repository (which
# dedupes on the run key) and the domain layer (which groups by it, and joins on
# the exposure key) read one definition rather than two.
RUN_KEY_COLUMNS = config.BACKTESTING_RUN_KEY_COLUMNS
NCO_RUN_KEY_COLUMNS = config.BACKTESTING_NCO_RUN_KEY_COLUMNS
EXPOSURE_JOIN_COLUMNS = config.BACKTESTING_EXPOSURE_JOIN_COLUMNS


run_key_columns = config.backtesting_run_key_columns


def dedupe_latest_execution(frame: pd.DataFrame, run_key: tuple[str, ...]) -> pd.DataFrame:
    """Keep only the latest execution of each run key, **whole run at a time**.

    Row-level selection is deliberately avoided. A partial re-run -- one that
    emitted only some quarters -- would otherwise contribute those quarters
    while the superseded execution still contributed the rest, producing a
    projection path stitched from two executions that can be non-monotonic at
    the seam.

    Rows whose ``Execution Datetime`` failed to parse are ``NaT`` and can never
    win: ``max`` skips them, and the equality test below then excludes them
    whenever any real timestamp exists for that run key.
    """
    if frame.empty:
        return frame

    execution_column = config.BACKTESTING_EXECUTION_DATETIME_COLUMN
    latest = frame.groupby(list(run_key), observed=True)[execution_column].transform("max")
    return frame[frame[execution_column] == latest].reset_index(drop=True)


def _normalize_frame(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
    """Coerce dtypes so downstream code never re-parses the same column."""
    frame = frame.copy()

    frame[config.BACKTESTING_SNAPSHOT_COLUMN] = pd.to_datetime(
        frame[config.BACKTESTING_SNAPSHOT_COLUMN], errors="coerce"
    )
    frame[config.BACKTESTING_EXECUTION_DATETIME_COLUMN] = pd.to_datetime(
        frame[config.BACKTESTING_EXECUTION_DATETIME_COLUMN], errors="coerce"
    )
    frame[config.BACKTESTING_QUARTER_COLUMN] = pd.to_numeric(
        frame[config.BACKTESTING_QUARTER_COLUMN], errors="coerce"
    ).astype("Int64")

    value_column = config.BACKTESTING_METRIC_VALUE_COLUMNS[metric]
    frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce")

    for column in (
        config.BACKTESTING_SEGMENT_COLUMN,
        config.BACKTESTING_RUN_FOR_COLUMN,
        config.BACKTESTING_SCENARIO_COLUMN,
        config.BACKTESTING_JN_FLAG_COLUMN,
        config.BACKTESTING_FACILITY_ID_COLUMN,
        config.BACKTESTING_CREDIT_INSTRUMENT_ID_COLUMN,
    ):
        frame[column] = frame[column].astype(str).str.strip()

    return frame


def _ordered_unique(frame: pd.DataFrame, column: str) -> list[str]:
    if column not in frame.columns:
        return []
    values = frame[column].dropna().astype(str).str.strip()
    return [value for value in dict.fromkeys(values.tolist()) if value]


def _empty_payload() -> dict[str, Any]:
    """The shape returned when the workbook cannot be read.

    Mirrors SAAS's best-effort loading: a missing or unreadable workbook leaves
    the dashboard empty rather than breaking app import, since the payload is
    built at import time.
    """
    return {
        "metrics": {metric: pd.DataFrame() for metric in config.BACKTESTING_METRIC_SHEETS},
        "superseded_run_counts": {metric: 0 for metric in config.BACKTESTING_METRIC_SHEETS},
        "segment_values": [],
        "run_for_values": [],
        "scenario_values": [],
        "jn_flag_values": [],
        "model_values": {metric: [] for metric in config.BACKTESTING_METRIC_SHEETS},
        "model_catalog": {},
        "snapshot_dates": [],
        "quarters": [],
        "loaded": False,
    }


def load_model_catalog(model_names: set[str] | None = None) -> dict[str, dict]:
    """Model attributes from the ``model_names`` sheet of the MEV workbook.

    ``model_names`` is the platform's model *catalogue*: which segments a model
    serves plus its region, portfolio, type and descriptive name. Monitoring and
    SAAS already read it, so sourcing backtesting's Region / Portfolio / Model
    Group filters and its model labels from the same sheet keeps one vocabulary
    across all three dashboards instead of three drifting ones.

    A second workbook read from this feature's repository, deliberately: the
    catalogue is not part of ``backtesting_results.xlsx`` and duplicating it
    there would create a second copy to keep in step.

    Returns ``{model_name: {label, region, portfolio, model_group, segments}}``,
    restricted to ``model_names`` when given. A model whose attribute is blank
    gets :data:`BACKTESTING_UNASSIGNED_LABEL` rather than being dropped -- the
    gap stays visible and the model stays reachable.
    """
    unassigned = config.BACKTESTING_UNASSIGNED_LABEL
    try:
        frame = pd.read_excel(
            settings.dummy_mev_data_file,
            sheet_name=config.DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME,
        )
    except Exception as exc:  # noqa: BLE001 - the page must survive a missing catalogue
        log.warning(
            "Unable to read the model catalogue from %s [%s]: %s",
            settings.dummy_mev_data_file,
            config.DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME,
            exc,
        )
        return {}

    def _clean(value) -> str:
        if value is None or pd.isna(value):
            return ""
        return str(value).strip()

    catalog: dict[str, dict] = {}
    for row in frame.to_dict(orient="records"):
        name = _clean(row.get(config.DUMMY_MEV_MODEL_NAME_COLUMN))
        if not name or (model_names is not None and name not in model_names):
            continue

        entry = catalog.setdefault(
            name,
            {
                "label": _clean(row.get(config.DUMMY_MEV_MODEL_DESCRIPTIVE_NAME_COLUMN)) or name,
                "region": _clean(row.get(config.DUMMY_MEV_REGION_COLUMN)) or unassigned,
                "portfolio": _clean(row.get(config.DUMMY_MEV_PORTFOLIO_COLUMN)) or unassigned,
                "model_group": _clean(row.get(config.DUMMY_MEV_MODEL_TYPE_COLUMN)) or unassigned,
                "segments": [],
            },
        )
        # A model appears once per (segment, cycle); collect the distinct
        # segments it serves.
        segment = _clean(row.get(config.DUMMY_MEV_SEGMENT_NAME_COLUMN))
        if segment and segment not in entry["segments"]:
            entry["segments"].append(segment)

    return catalog


def load_backtesting_workbook_data() -> dict[str, Any]:
    """Load the backtesting workbook into an in-memory payload.

    Returns deduped, dtype-normalised frames per metric plus the filter
    catalogs derived from the data (never hard-coded, so a new ``Run For`` value
    in the workbook populates the filters on the next process restart).
    """
    path = settings.backtesting_results_file
    frames: dict[str, pd.DataFrame] = {}
    superseded: dict[str, int] = {}

    try:
        workbook = pd.ExcelFile(path)
    except Exception as exc:  # noqa: BLE001 - keep the app importable without the workbook
        log.warning("Unable to open backtesting workbook %s: %s", path, exc)
        return _empty_payload()

    for metric, sheet_name in config.BACKTESTING_METRIC_SHEETS.items():
        try:
            raw = workbook.parse(sheet_name)
        except Exception as exc:  # noqa: BLE001 - one bad sheet should not lose the rest
            log.warning("Unable to read sheet %s from %s: %s", sheet_name, path, exc)
            frames[metric] = pd.DataFrame()
            superseded[metric] = 0
            continue

        normalized = _normalize_frame(raw, metric)
        run_key = run_key_columns(metric)
        deduped = dedupe_latest_execution(normalized, run_key)

        superseded[metric] = len(normalized) - len(deduped)
        if superseded[metric]:
            log.info(
                "%s: dropped %d superseded row(s) from earlier executions.",
                sheet_name,
                superseded[metric],
            )
        frames[metric] = deduped

    # Filter catalogs come from the union across sheets: the two PD sheets cover
    # disjoint populations, so reading only one would under-report the models and
    # (potentially) the segments in scope.
    combined = [frame for frame in frames.values() if not frame.empty]
    catalog_source = pd.concat(combined, ignore_index=True) if combined else pd.DataFrame()

    snapshot_dates: list[Any] = []
    quarters: list[int] = []
    if not catalog_source.empty:
        snapshot_dates = sorted(
            value for value in catalog_source[config.BACKTESTING_SNAPSHOT_COLUMN].dropna().unique()
        )
        quarters = sorted(
            int(value) for value in catalog_source[config.BACKTESTING_QUARTER_COLUMN].dropna().unique()
        )

    model_values: dict[str, list[str]] = {}
    for metric, frame in frames.items():
        if metric == config.BACKTESTING_METRIC_NCO:
            model_values[metric] = _ordered_unique(frame, config.BACKTESTING_PD_MODEL_NAME_COLUMN)
        else:
            model_values[metric] = _ordered_unique(frame, config.BACKTESTING_MODEL_NAME_COLUMN)

    return {
        "metrics": frames,
        "superseded_run_counts": superseded,
        "segment_values": _ordered_unique(catalog_source, config.BACKTESTING_SEGMENT_COLUMN),
        "run_for_values": _ordered_unique(catalog_source, config.BACKTESTING_RUN_FOR_COLUMN),
        "scenario_values": _ordered_unique(catalog_source, config.BACKTESTING_SCENARIO_COLUMN),
        "jn_flag_values": _ordered_unique(catalog_source, config.BACKTESTING_JN_FLAG_COLUMN),
        "model_values": model_values,
        # Attributes for exactly the models this workbook actually contains.
        "model_catalog": load_model_catalog(
            {name for names in model_values.values() for name in names}
        ),
        "snapshot_dates": snapshot_dates,
        "quarters": quarters,
        "loaded": bool(combined),
    }
