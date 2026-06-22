"""Shared pytest configuration.

Ensures the directory that *contains* the ``STATpy_platform`` package is on
``sys.path`` so tests can ``import STATpy_platform...`` regardless of the
working directory pytest is invoked from.
"""

from __future__ import annotations

import sys
from pathlib import Path

# tests/ -> STATpy_platform/ -> <parent that holds the package>
PACKAGE_PARENT = Path(__file__).resolve().parents[2]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))
