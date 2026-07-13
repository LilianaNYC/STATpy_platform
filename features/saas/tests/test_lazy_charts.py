"""SAAS charts render lazily: nothing is built until a panel is opened."""

from __future__ import annotations

from dash import no_update

import STATpy_platform.features.saas.callbacks.workspace as cb
import STATpy_platform.shared.registration as reg


def _capture_callbacks(monkeypatch) -> dict:
    captured: dict = {}

    class StubApp:
        def callback(self, *args, **kwargs):
            def decorator(fn):
                captured[fn.__name__] = fn
                return fn

            return decorator

    monkeypatch.setattr(reg, "already_registered", lambda app, key: False)
    cb.register_callbacks(StubApp())
    return captured


def test_grid_callback_does_not_build_until_panel_opened(monkeypatch):
    # The grid callback also fires when the dropdowns mount and when sync sets
    # their values; with a zero/None chart trigger (panel never opened) it must
    # return no_update so the dozens of charts are not built up front.
    fn = _capture_callbacks(monkeypatch)["update_model_mev_chart_controls"]
    grid_id = {"type": "saas-model-mev-grid", "model": "PD_model_a"}
    applied = {"run_for": ["cycle"]}

    for trigger in (0, None):
        result = fn("family", ["baseline"], [], "MEV", "all", None, None, "light", trigger, grid_id, applied)
        assert result == (no_update, no_update)
