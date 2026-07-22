from __future__ import annotations

from STATpy_platform.shared.domain.calculations import (
    PD_SEGMENT_HOME_MODEL,
    PdFilterContext,
    ctx_store_keys,
)


def _ctx(models, segment):
    return PdFilterContext(quarters=[], models=set(models), segment=segment, monitoring_point="")


def test_ctx_store_keys_single_model_with_segment_resolves_to_that_model():
    ctx = _ctx({"PD Model D"}, "Defensive")

    assert ctx_store_keys(ctx) == ("PD Model D", "Defensive")


def test_ctx_store_keys_multiple_models_with_segment_falls_back_to_home_model():
    ctx = _ctx({"PD Model A", "PD Model B", "PD Model C", "PD Model D"}, "Cyclical")

    assert ctx_store_keys(ctx) == (PD_SEGMENT_HOME_MODEL, "Cyclical")


def test_ctx_store_keys_no_models_with_segment_falls_back_to_home_model():
    ctx = _ctx(set(), "Cyclical")

    assert ctx_store_keys(ctx) == (PD_SEGMENT_HOME_MODEL, "Cyclical")


def test_ctx_store_keys_model_with_no_segment_resolves_to_all():
    ctx = _ctx({"PD Model C"}, "all")

    assert ctx_store_keys(ctx) == ("PD Model C", "All")


def test_ctx_store_keys_no_model_no_segment_resolves_to_empty_all():
    ctx = _ctx(set(), "all")

    assert ctx_store_keys(ctx) == ("", "All")
