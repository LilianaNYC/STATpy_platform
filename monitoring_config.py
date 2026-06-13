"""Static configuration for the standalone PD Performance Dash app.

Values mirror ``monitoring_config.yaml`` (data column names / source files)
and the JS constants defined at the top of
``pages/monitoring_pd_models_page.py`` (RAG groups, default lookup tables,
go-live window, RAG colours, etc.). Keeping these as plain constants avoids
re-reading the YAML/JS at import time and documents exactly which values
were carried over.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# Source data files are bundled inside this app (source_data/) so the app
# is self-contained and works regardless of where this folder lives.
APP_DIR = Path(__file__).resolve().parent
SOURCE_DATA_DIR = APP_DIR / "source_data"

PORTFOLIO_FILE = SOURCE_DATA_DIR / "portfolio.xlsx"
PORTFOLIO_SHEET_NAME = "Portfolio"

MONITORING_THRESHOLDS_FILE = SOURCE_DATA_DIR / "statpy_monitoring_thresholds.xlsm"
PD_THRESHOLDS_SHEET_NAME = "PD_Thresholds"
CRR_MASTER_SCALE_SHEET_NAME = "CRR_Master_Scale"
RAG_ASSIGNMENT_PD_SHEET_NAME = "RAG_Assignment_PD"

MEV_DUMMY_DATA_FILE = SOURCE_DATA_DIR / "mev_dummy_data.json"
DUMMY_MEV_DATA_FILE = SOURCE_DATA_DIR / "dummy_mev_data.xlsx"
DUMMY_MEV_TRANSFORMED_DESCRIPTION_SHEET_NAME = "transformed_mevs_description"
DUMMY_MEV_RAW_DESCRIPTION_SHEET_NAME = "raw_mevs_description"
DUMMY_MEV_TIME_SERIES_SHEET_NAME = "mev_data"
DUMMY_MEV_MODEL_CHARACTERISTIC_SHEET_NAME = "model_characteristic"
DUMMY_MEV_MODEL_NAME_COLUMN = "Model Name"
FACILITIES_DUMMY_DATA_FILE = SOURCE_DATA_DIR / "facilities_dummy_data.json"

# ---------------------------------------------------------------------------
# Portfolio column names (from monitoring_config.yaml -> data:)
# ---------------------------------------------------------------------------
DATE_COLUMN = "MONTH END-SNAPSHOT DATE"
SEGMENT_COLUMN = "Portfolio"
FACILITY_ID_COLUMN = "facility id"
PD_MODEL_COLUMN = "pd_model"
RATING_COLUMN = "rating_grade"

PD_PREDICTED_1Y_COLUMN = "CPD_1y_base"
PD_PREDICTED_2Y_COLUMN = "CPD_2y_base"
PD_PREDICTED_NCO_1Y_COLUMN = "CPD_NCO_1y"
PD_OBSERVED_DEFAULT_1Y_COLUMN = "default flag 1y"
PD_OBSERVED_DEFAULT_2Y_COLUMN = "default flag 2y"
EAD_PREDICTED_1Y_COLUMN = "EAD_1y_base"
EAD_PREDICTED_2Y_COLUMN = "EAD_2y_base"

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
INVERSE_RAG_SCORE = {score: rag for rag, score in RAG_SCORE.items()}

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
