"""App-level smoke tests: the app builds and callback registration is idempotent."""

from __future__ import annotations

from STATpy_platform.app import create_app


def test_app_builds_with_callbacks():
    app = create_app()
    assert app.layout is not None
    assert len(app.callback_map) > 0


def test_callback_registration_is_idempotent_per_app():
    # Two independent apps each register the full set; building twice in one
    # process must not silently drop callbacks (the per-app guard, not a
    # module-level global).
    app1 = create_app()
    app2 = create_app()
    assert len(app1.callback_map) == len(app2.callback_map)
