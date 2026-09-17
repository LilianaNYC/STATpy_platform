"""Pure-domain tests for the cross-metric backtesting diagnostics."""

from __future__ import annotations

import pytest

from STATpy_platform.features.backtesting.domain import diagnostics
from STATpy_platform.shared.domain import constants as config


def _record(**overrides):
    row = {
        "vintage_quarter": "2024-Q1",
        "target_quarter": "2024-Q2",
        "quarter": "2024-Q2",
        "horizon": 1,
        config.BACKTESTING_RUN_FOR_COLUMN: "Cycle A",
        "forecast": 110.0,
        "actual": 100.0,
        "error": 10.0,
        "absolute_error": 10.0,
        "percentage_error": 0.10,
        "coverage": 0.95,
        "exposure": 100.0,
    }
    row.update(overrides)
    return row


def test_error_matrix_preserves_direction_and_hover_metadata():
    matrix = diagnostics.build_error_matrix([
        _record(),
        _record(percentage_error=-0.20, error=-20.0, absolute_error=20.0),
    ], "vintage_quarter")
    cell = matrix["cells"][0]
    assert cell["signed_error"] == pytest.approx(-0.05)
    assert cell["mape"] == pytest.approx(0.15)
    assert cell["count"] == 2
    assert cell["coverage"] == pytest.approx(0.95)
    assert cell["target_quarters"] == ["2024-Q2"]


def test_revision_uses_latest_target_with_multiple_vintages():
    revision = diagnostics.build_revision_series([
        _record(vintage_quarter="2023-Q4", target_quarter="2024-Q2", forecast=120.0),
        _record(vintage_quarter="2024-Q1", target_quarter="2024-Q2", forecast=110.0),
        _record(vintage_quarter="2024-Q1", target_quarter="2024-Q3", forecast=130.0),
    ])
    assert revision["target_quarter"] == "2024-Q2"
    assert [point["forecast"] for point in revision["series"][0]["points"]] == [120.0, 110.0]


def test_shapley_product_attribution_is_order_independent_and_reconciles():
    actual = (0.10, 0.50, 100.0)
    forecast = (0.12, 0.40, 110.0)
    parts = diagnostics.shapley_product_attribution(actual, forecast)
    assert sum(parts) == pytest.approx(0.12 * 0.40 * 110.0 - 0.10 * 0.50 * 100.0)


def test_nco_attribution_reconciles_to_reported_mean_error():
    pd = [_record(forecast=0.12, actual=0.10, exposure=100.0)]
    lgd = [_record(forecast=0.40, actual=0.50)]
    ead = [_record(forecast=110.0, actual=100.0)]
    nco = [_record(forecast=5.5, actual=5.0, error=0.5)]
    result = diagnostics.build_nco_attribution(nco, pd, lgd, ead)
    assert result["count"] == 1
    assert sum(result["values"]) == pytest.approx(0.5)
    assert result["total_error"] == pytest.approx(0.5)
    assert result["coverage"] == pytest.approx(1.0)
