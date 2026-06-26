"""Make ``import STATpy_platform...`` resolve when pytest runs these feature
tests directly (mirrors the repo-root tests/conftest.py)."""

import sys
from pathlib import Path

# tests -> dq_module -> features -> STATpy_platform -> <package parent>
_PKG_PARENT = Path(__file__).resolve().parents[4]
if str(_PKG_PARENT) not in sys.path:
    sys.path.insert(0, str(_PKG_PARENT))
