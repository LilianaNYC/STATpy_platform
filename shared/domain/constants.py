"""Data-domain constants for the monitoring analytics engine.

Column names, sheet names, RAG groups/colours, horizon definitions and the
default lookup tables that the PD performance calculations depend on. These
are pure domain constants only: source-data *file locations* are environment
configuration and live in :mod:`config.settings` — the repository layer reads
them straight from ``settings``, so they are deliberately not re-exported here.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Sheet names
# ---------------------------------------------------------------------------
PORTFOLIO_SHEET_NAME = "Portfolio"

PD_THRESHOLDS_SHEET_NAME = "PD_Thresholds"
CRR_MASTER_SCALE_SHEET_NAME = "CRR_Master_Scale"
RAG_ASSIGNMENT_PD_SHEET_NAME = "RAG_Assignment_PD"
LGD_THRESHOLDS_SHEET_NAME = "LGD_Thresholds"
EAD_THRESHOLDS_SHEET_NAME = "EAD_Thresholds"
LOSS_THRESHOLDS_SHEET_NAME = "Loss_Thresholds"

DUMMY_MEV_TRANSFORMED_DESCRIPTION_SHEET_NAME = "mev_transformed"
DUMMY_MEV_RAW_DESCRIPTION_SHEET_NAME = "mev_raw"
DUMMY_MEV_TIME_SERIES_SHEET_NAME = "scenario"
DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME = "model_names"
DUMMY_MEV_MODEL_NAME_COLUMN = "Model Name"

# Model-attribute columns on the ``model_names`` sheet. This sheet is the model
# *catalogue*: which segment a model serves, and its region / portfolio / type /
# descriptive name. Backtesting reads it for its filter attributes.
DUMMY_MEV_MODEL_DESCRIPTIVE_NAME_COLUMN = "Model Descriptive Name"
DUMMY_MEV_MODEL_TYPE_COLUMN = "Model Type"
DUMMY_MEV_REGION_COLUMN = "Region"
DUMMY_MEV_PORTFOLIO_COLUMN = "Portfolio"
DUMMY_MEV_SEGMENT_NAME_COLUMN = "Segment Name"

# ---------------------------------------------------------------------------
# Backtesting workbook (``backtesting_results.xlsx``)
# ---------------------------------------------------------------------------
# Five facility-grain result sheets. ``results.pd`` and ``results.pd_crr`` are
# the same structure over *disjoint* facility populations (split by owning PD
# model), so a portfolio-level PD is the union of the two; ``results.lgd`` /
# ``results.ead`` / ``results.nco`` each cover the full population. See
# ``source_data/Backtesting_Workbook_Guide.md``.
BACKTESTING_PD_SHEET_NAME = "results.pd"
BACKTESTING_PD_CRR_SHEET_NAME = "results.pd_crr"
BACKTESTING_LGD_SHEET_NAME = "results.lgd"
BACKTESTING_EAD_SHEET_NAME = "results.ead"
BACKTESTING_NCO_SHEET_NAME = "results.nco"

BACKTESTING_SHEET_NAMES = (
    BACKTESTING_PD_SHEET_NAME,
    BACKTESTING_PD_CRR_SHEET_NAME,
    BACKTESTING_LGD_SHEET_NAME,
    BACKTESTING_EAD_SHEET_NAME,
    BACKTESTING_NCO_SHEET_NAME,
)

# Run-identity and grain columns, shared by every sheet.
BACKTESTING_SEGMENT_COLUMN = "Segment Name"
BACKTESTING_MODEL_NAME_COLUMN = "Model Name"
BACKTESTING_SNAPSHOT_COLUMN = "Month End Snapshot"
BACKTESTING_RUN_FOR_COLUMN = "Run For"
BACKTESTING_SCENARIO_COLUMN = "Scenario"
BACKTESTING_JN_FLAG_COLUMN = "J/N Flag"
BACKTESTING_FACILITY_ID_COLUMN = "Facility ID"
BACKTESTING_CREDIT_INSTRUMENT_ID_COLUMN = "Credit Instrument ID"
BACKTESTING_QUARTER_COLUMN = "Quarter"
BACKTESTING_EXECUTION_DATETIME_COLUMN = "Execution Datetime"

# ``results.nco`` names the three contributing models instead of one, and adds
# the loss method.
BACKTESTING_PD_MODEL_NAME_COLUMN = "PD Model Name"
BACKTESTING_LGD_MODEL_NAME_COLUMN = "LGD Model Name"
BACKTESTING_EAD_MODEL_NAME_COLUMN = "EAD Model Name"
BACKTESTING_LOSS_METHOD_COLUMN = "Loss Method"

# Metric value columns. Both PD sheets use the same column name.
BACKTESTING_PD_VALUE_COLUMN = "PD Value"
BACKTESTING_LGD_VALUE_COLUMN = "LGD Value"
BACKTESTING_EAD_VALUE_COLUMN = "EAD Value"
BACKTESTING_NCO_VALUE_COLUMN = "NCO Value"

# Metric keys used throughout the backtesting feature, and the sheet / value
# column each one reads.
BACKTESTING_METRIC_PD = "pd"
BACKTESTING_METRIC_PD_CRR = "pd_crr"
BACKTESTING_METRIC_LGD = "lgd"
BACKTESTING_METRIC_EAD = "ead"
BACKTESTING_METRIC_NCO = "nco"

BACKTESTING_METRIC_SHEETS = {
    BACKTESTING_METRIC_PD: BACKTESTING_PD_SHEET_NAME,
    BACKTESTING_METRIC_PD_CRR: BACKTESTING_PD_CRR_SHEET_NAME,
    BACKTESTING_METRIC_LGD: BACKTESTING_LGD_SHEET_NAME,
    BACKTESTING_METRIC_EAD: BACKTESTING_EAD_SHEET_NAME,
    BACKTESTING_METRIC_NCO: BACKTESTING_NCO_SHEET_NAME,
}

BACKTESTING_METRIC_VALUE_COLUMNS = {
    BACKTESTING_METRIC_PD: BACKTESTING_PD_VALUE_COLUMN,
    BACKTESTING_METRIC_PD_CRR: BACKTESTING_PD_VALUE_COLUMN,
    BACKTESTING_METRIC_LGD: BACKTESTING_LGD_VALUE_COLUMN,
    BACKTESTING_METRIC_EAD: BACKTESTING_EAD_VALUE_COLUMN,
    BACKTESTING_METRIC_NCO: BACKTESTING_NCO_VALUE_COLUMN,
}

# The two PD sheets cover disjoint populations; a portfolio PD stacks them.
BACKTESTING_PD_METRICS = (BACKTESTING_METRIC_PD, BACKTESTING_METRIC_PD_CRR)

# Metrics that are exposure-weighted (rates) versus additive (amounts).
# Weighting an amount would understate it; averaging a rate unweighted lets a
# small facility count as much as a large one.
BACKTESTING_EXPOSURE_WEIGHTED_METRICS = (
    BACKTESTING_METRIC_PD,
    BACKTESTING_METRIC_PD_CRR,
    BACKTESTING_METRIC_LGD,
)
BACKTESTING_ADDITIVE_METRICS = (BACKTESTING_METRIC_EAD, BACKTESTING_METRIC_NCO)

# Run identity for the four single-model sheets.
BACKTESTING_RUN_KEY_COLUMNS = (
    BACKTESTING_SEGMENT_COLUMN,
    BACKTESTING_MODEL_NAME_COLUMN,
    BACKTESTING_SNAPSHOT_COLUMN,
    BACKTESTING_RUN_FOR_COLUMN,
    BACKTESTING_SCENARIO_COLUMN,
    BACKTESTING_JN_FLAG_COLUMN,
)

# ``results.nco`` names three models plus the loss method instead of one model.
BACKTESTING_NCO_RUN_KEY_COLUMNS = (
    BACKTESTING_SEGMENT_COLUMN,
    BACKTESTING_PD_MODEL_NAME_COLUMN,
    BACKTESTING_LGD_MODEL_NAME_COLUMN,
    BACKTESTING_EAD_MODEL_NAME_COLUMN,
    BACKTESTING_SNAPSHOT_COLUMN,
    BACKTESTING_RUN_FOR_COLUMN,
    BACKTESTING_SCENARIO_COLUMN,
    BACKTESTING_JN_FLAG_COLUMN,
    BACKTESTING_LOSS_METHOD_COLUMN,
)

# The exposure join key: the run identity *excluding* the model, because a
# facility's PD model is not its EAD model, plus the row grain.
BACKTESTING_EXPOSURE_JOIN_COLUMNS = (
    BACKTESTING_SEGMENT_COLUMN,
    BACKTESTING_SNAPSHOT_COLUMN,
    BACKTESTING_RUN_FOR_COLUMN,
    BACKTESTING_SCENARIO_COLUMN,
    BACKTESTING_JN_FLAG_COLUMN,
    BACKTESTING_FACILITY_ID_COLUMN,
    BACKTESTING_CREDIT_INSTRUMENT_ID_COLUMN,
    BACKTESTING_QUARTER_COLUMN,
)


def backtesting_run_key_columns(metric: str) -> tuple[str, ...]:
    """The run-identity columns for ``metric``'s sheet.

    Kept here beside the tuples so the repository (which dedupes on the run key)
    and the domain layer (which groups by it) cannot drift apart.
    """
    if metric == BACKTESTING_METRIC_NCO:
        return BACKTESTING_NCO_RUN_KEY_COLUMNS
    return BACKTESTING_RUN_KEY_COLUMNS


# ``Quarter == 0`` is the realised anchor: the observed value at the snapshot
# date, identical across scenarios and J/N flags. ``>= 1`` are projections.
BACKTESTING_ANCHOR_QUARTER = 0

# The scenario a backtest scores against. Non-baseline scenarios are
# deliberately conservative, so scoring them against realised outcomes measures
# the conservatism buffer rather than model accuracy.
BACKTESTING_BASE_SCENARIO = "Base"

# Model-attribute keys the backtesting catalogue exposes per model.
BACKTESTING_MODEL_ATTRIBUTES = ("region", "portfolio", "model_group", "segments", "label")

# Shown for a model whose catalogue attribute is blank. Surfacing the gap keeps
# the model reachable instead of silently dropping it from a narrowed filter.
BACKTESTING_UNASSIGNED_LABEL = "Unassigned"

# ---------------------------------------------------------------------------
# Portfolio column names (from monitoring_config.yaml -> data:)
# ---------------------------------------------------------------------------
DATE_COLUMN = "MONTH END-SNAPSHOT DATE"
SEGMENT_COLUMN = "Portfolio"
FACILITY_ID_COLUMN = "facility id"
PD_MODEL_COLUMN = "pd_model"

PD_PREDICTED_1Y_COLUMN = "CPD_1y_base"
PD_PREDICTED_2Y_COLUMN = "CPD_2y_base"
PD_PREDICTED_NCO_1Y_COLUMN = "CPD_NCO_1y"
PD_OBSERVED_DEFAULT_1Y_COLUMN = "default flag 1y"
PD_OBSERVED_DEFAULT_2Y_COLUMN = "default flag 2y"
EAD_PREDICTED_1Y_COLUMN = "EAD_1y_base"
EAD_PREDICTED_2Y_COLUMN = "EAD_2y_base"
EAD_MODEL_COLUMN = "ead_model"
EAD_REALIZED_COLUMN = "realized_ead"
LGD_MODEL_COLUMN = "lgd_model"
LGD_PREDICTED_1Y_COLUMN = "LGD_1y_base"
LGD_REALIZED_COLUMN = "realized_lgd"
LIMIT_AMOUNT_COLUMN = "limit_amount"
BALANCE_COLUMN = "Balance"

NULL_SENTINELS = ["NULL", "ZZZ", "N/A", ""]

# Horizon definitions used to build performance observations. Mirrors
# ``_build_pd_performance_observations``'s ``horizon_columns`` dict.
PD_HORIZON_COLUMNS = {
    "1y": {
        "label": "1 year",
        "observed_column": PD_OBSERVED_DEFAULT_1Y_COLUMN,
        "predicted_column": PD_PREDICTED_1Y_COLUMN,
        "ead_column": EAD_PREDICTED_1Y_COLUMN,
    },
    "2y": {
        "label": "2 years",
        "observed_column": PD_OBSERVED_DEFAULT_2Y_COLUMN,
        "predicted_column": PD_PREDICTED_2Y_COLUMN,
        "ead_column": EAD_PREDICTED_2Y_COLUMN,
    },
    "nco_1y": {
        "label": "NCO PD 1 year",
        "observed_column": PD_OBSERVED_DEFAULT_1Y_COLUMN,
        "predicted_column": PD_PREDICTED_NCO_1Y_COLUMN,
        "ead_column": EAD_PREDICTED_1Y_COLUMN,
    },
}

# ---------------------------------------------------------------------------
# RAG groups / metric aliases (from PD_RAG_GROUPS / PD_THRESHOLD_METRIC_ALIASES)
# ---------------------------------------------------------------------------
PD_RAG_GROUPS = {
    "calibration": ["Confidence Interval Test", "Notching Test"],
    "discrimination": ["Accuracy Ratio", "Gini Coefficient", "KS Statistic", "Kendall's Tau"],
    "performance": ["Brier Score", "Population Stability Index", "Rating Migration Index"],
}

PD_THRESHOLD_METRIC_ALIASES = {
    "Confidence Interval Test": "Confidence Interval",
}

RAG_SCORE = {"N/A": 0, "Green": 1, "Amber": 2, "Red": 3}

# ---------------------------------------------------------------------------
# Go-live window for the frozen 1y discrimination accuracy trend
# ---------------------------------------------------------------------------
PD_GO_LIVE_QUARTER_START = "2019Q2"
PD_GO_LIVE_QUARTER_END = "2019Q4"

# ---------------------------------------------------------------------------
# Default lookup tables, used when the corresponding sheet is missing/empty
# ---------------------------------------------------------------------------
DEFAULT_PD_CRR_MASTER_SCALE = [
    {"crr": 1.0, "min_pd": 0.0, "max_pd": 0.0015},
    {"crr": 2.0, "min_pd": 0.0015, "max_pd": 0.005},
    {"crr": 3.0, "min_pd": 0.005, "max_pd": 0.01},
    {"crr": 4.0, "min_pd": 0.01, "max_pd": 0.025},
    {"crr": 5.0, "min_pd": 0.025, "max_pd": 0.05},
    {"crr": 6.0, "min_pd": 0.05, "max_pd": 0.1},
    {"crr": 7.0, "min_pd": 0.1, "max_pd": 0.2},
    {"crr": 8.0, "min_pd": 0.2, "max_pd": 0.9999},
    {"crr": 9.0, "min_pd": 1.0, "max_pd": 1.0},
]

DEFAULT_PD_CONFIDENCE_INTERVAL_THRESHOLD = {
    "metric": "Confidence Interval",
    "dimension": "ECL PIT PD - Calibration Conservatism",
    "green_rule": "value >= 0.45",
    "amber_rule": "0.35 <= value < 0.45",
    "red_rule": "value < 0.35",
    "green_min": 0.45,
    "green_max": None,
    "amber_min": 0.35,
    "amber_max": 0.45,
    "red_condition": "below amber_min",
    "higher_is_better": True,
    "lower_is_better": False,
    "target_value": None,
    "warning_message": None,
    "notes": "Dummy monitoring metric placeholder.",
}

DEFAULT_PD_RAG_ASSIGNMENT = [
    {"notching_bucket": ">2", "p_low": "Amber", "p_mid": "Green", "p_high": "Amber", "p_very_high": "Red"},
    {"notching_bucket": "+2", "p_low": "Green", "p_mid": "Green", "p_high": "Amber", "p_very_high": "Amber"},
    {"notching_bucket": "0 to +/-1", "p_low": "Green", "p_mid": "Green", "p_high": "Green", "p_very_high": "Amber"},
    {"notching_bucket": "-2", "p_low": "Amber", "p_mid": "Amber", "p_high": "Amber", "p_very_high": "Amber"},
    {"notching_bucket": "<-2", "p_low": "Amber", "p_mid": "Amber", "p_high": "Amber", "p_very_high": "Red"},
]

# ---------------------------------------------------------------------------
# RAG colours (from pdRagColor)
# ---------------------------------------------------------------------------
PD_RAG_COLOR = {
    "Green": "#16a34a",
    "Amber": "#d97706",
    "Red": "#dc2626",
    "N/A": "#94a3b8",
}


def pd_rag_color(rag: str) -> str:
    return PD_RAG_COLOR.get(rag, PD_RAG_COLOR["N/A"])


# ---------------------------------------------------------------------------
# MEV palette (from PD_MEV_PALETTE)
# ---------------------------------------------------------------------------
PD_MEV_PALETTE = [
    "#0f766e", "#2563eb", "#7c3aed", "#ea580c",
    "#0891b2", "#be123c", "#a16207", "#334155",
]
