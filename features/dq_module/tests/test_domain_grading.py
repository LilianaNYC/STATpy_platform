"""Domain layer — pure grading rules (no Dash, no I/O)."""

from STATpy_platform.features.dq_module.domain import grading


def test_missing_bucket_boundaries():
    assert grading.missing_bucket(None) == "No Missings"
    assert grading.missing_bucket(0) == "No Missings"
    assert grading.missing_bucket(0.5) == "Low"
    assert grading.missing_bucket(1) == "Low"
    assert grading.missing_bucket(1.01) == "Medium"
    assert grading.missing_bucket(10) == "Medium"
    assert grading.missing_bucket(10.01) == "High"
    assert grading.missing_bucket(99) == "High"
    # every result is one of the 4 canonical buckets
    for v in (None, 0, 0.3, 1, 5, 10, 25, 100):
        assert grading.missing_bucket(v) in grading.MISSING_BUCKETS


def test_verdict_for_thresholds():
    # 3+ red stats -> Drift
    assert grading.verdict_for({"psi": 0.3, "ks_p": 0.005, "anova_p": 0.005})["level"] == "red"
    assert grading.verdict_for({"psi": 0.3, "ks_p": 0.005, "anova_p": 0.005})["red_count"] == 3
    # 1-2 red -> Mixed
    assert grading.verdict_for({"psi": 0.3})["level"] == "amber"
    # 0 red -> Stable
    assert grading.verdict_for({})["level"] == "green"
    assert grading.verdict_for({"psi": 0.05, "ks_p": 0.9})["level"] == "green"


def test_detect_count_anomalies_kinds_and_order():
    segs = {"dim1": {"label": "Dim 1", "column": "D1", "rows": [
        {"segment": "A", "prior_records": 0,   "records": 50},   # appeared
        {"segment": "B", "prior_records": 50,  "records": 0},    # disappeared
        {"segment": "C", "prior_records": 10,  "records": 100},  # drastic_growth
        {"segment": "D", "prior_records": 100, "records": 10},   # drastic_drop
        {"segment": "E", "prior_records": 50,  "records": 52},   # stable -> no alert
    ]}}
    out = grading.detect_count_anomalies(segs)
    kinds = {a["segment"]: a["kind"] for a in out}
    assert kinds.get("A") == "appeared"
    assert kinds.get("B") == "disappeared"
    assert kinds.get("C") == "drastic_growth"
    assert kinds.get("D") == "drastic_drop"
    assert "E" not in kinds
    # sorted by |change| descending
    changes = [abs(a["change"]) for a in out]
    assert changes == sorted(changes, reverse=True)
