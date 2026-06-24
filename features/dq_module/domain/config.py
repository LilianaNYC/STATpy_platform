"""Dashboard-wide constants: severity ordering, source-system mapping, RAG cutoffs."""

# Severity ranking used when sorting issues / completeness
SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}

# Dummy source-system mapping for reconciliation waterfall
SOURCE_SYSTEMS = {
    "GL":  "Core Banking",
    "FTP": "Lending Platform",
    "OAV": "Collateral System",
    "TTP": "Risk Engine",
}

# Default PSI thresholds when not provided in config.yaml
DEFAULT_PSI_THRESHOLDS = {"minor": 0.10, "moderate": 0.20, "high": 0.50}

# Default completeness thresholds
DEFAULT_COMPLETENESS_THRESHOLDS = {
    "critical": 25.0, "high": 10.0, "medium": 5.0, "low": 1.0
}
