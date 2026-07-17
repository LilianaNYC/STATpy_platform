"""Governance action playbook: selection logic and the Conclusion panel."""

from __future__ import annotations

from STATpy_platform.features.monitoring.domain.actions import (
    is_persistent_breach_trigger,
    select_pd_monitoring_actions,
    trigger_driver_field,
)

from .test_pd_performance import (
    _collect_nodes_with_class,
    _collect_text,
    _render_pd_content_with,
)

_BREACH_TRIGGER = "Two consecutive Post Mitigation RAGs are Red"


def _playbook() -> list[dict]:
    def row(stage, rag, trigger, **extra):
        return {
            "stage": stage, "rag": rag, "trigger": trigger,
            "description": f"{stage} {rag} description",
            "required_action": f"{stage} {rag} action",
            "additional_requirements": "", "escalation": "",
            "sponsor_approval": "No", "deep_dive": "No", "redevelopment": "No",
            "owner": "Monitoring Lead", "due_in_report": "Current Monitoring Report",
            **extra,
        }

    pre_trigger = "Latest Post Subjective Review RAG"
    post_trigger = "Latest Post Mitigation RAG"
    return [
        row("Pre Mitigation", "Green", pre_trigger),
        row("Pre Mitigation", "Amber", pre_trigger),
        row("Pre Mitigation", "Red", pre_trigger, deep_dive="Yes"),
        row("Post Mitigation", "Green", post_trigger),
        row("Post Mitigation", "Amber", post_trigger),
        row("Post Mitigation", "Red", post_trigger, redevelopment="Yes"),
        row(
            "Post Mitigation", "Red", _BREACH_TRIGGER,
            sponsor_approval="Yes", redevelopment="Yes",
            required_action="Persistent breach action",
        ),
    ]


def test_trigger_text_names_the_driving_review_flow_card():
    assert trigger_driver_field("Latest Post Subjective Review RAG", "Pre Mitigation") == "post_subjective"
    assert trigger_driver_field("Latest Post Mitigation RAG", "Post Mitigation") == "post_mitigation"
    assert trigger_driver_field("Latest Pre Mitigation RAG", "Pre Mitigation") == "pre_mitigation"
    # Unrecognized trigger falls back to the stage's namesake RAG.
    assert trigger_driver_field("Latest Model RAG", "Pre Mitigation") == "pre_mitigation"


def test_trigger_matching_tolerates_punctuation_and_case_edits():
    assert trigger_driver_field("LATEST POST-SUBJECTIVE REVIEW RAG", "Pre Mitigation") == "post_subjective"
    assert is_persistent_breach_trigger("Two consecutive Post-Mitigation RAGs are Red")
    assert is_persistent_breach_trigger(_BREACH_TRIGGER)
    assert not is_persistent_breach_trigger("Latest Post Mitigation RAG")


def test_pre_mitigation_action_keys_off_the_post_subjective_rag_named_in_its_trigger():
    selections = select_pd_monitoring_actions(
        _playbook(),
        {"post_subjective": "Red", "pre_mitigation": "Green", "post_mitigation": "Green"},
    )
    pre = selections[0]
    assert pre["rag"] == "Red"
    assert pre["action"]["required_action"] == "Pre Mitigation Red action"
    assert pre["drivers"] == [("post_subjective", "Red")]


def test_post_mitigation_action_matches_the_standard_row_for_a_single_red():
    selections = select_pd_monitoring_actions(
        _playbook(),
        {"post_subjective": "Green", "pre_mitigation": "Green", "post_mitigation": "Red"},
        previous_post_mitigation_rag="Green",
    )
    post = selections[1]
    assert post["action"]["required_action"] == "Post Mitigation Red action"
    assert post["persistent_breach"] is False


def test_two_consecutive_post_mitigation_reds_escalate_to_the_persistent_breach_row():
    selections = select_pd_monitoring_actions(
        _playbook(),
        {"post_subjective": "Green", "pre_mitigation": "Green", "post_mitigation": "Red"},
        previous_post_mitigation_rag="Red",
    )
    post = selections[1]
    assert post["persistent_breach"] is True
    assert post["action"]["required_action"] == "Persistent breach action"
    assert post["action"]["sponsor_approval"] == "Yes"


def test_na_rags_select_no_action():
    selections = select_pd_monitoring_actions(
        _playbook(),
        {"post_subjective": "N/A", "pre_mitigation": "N/A", "post_mitigation": "N/A"},
    )
    assert all(selection["action"] is None for selection in selections)


def _render_text(**overrides) -> str:
    return " ".join(_collect_text(node) for node in _render_pd_content_with(**overrides))


def test_conclusion_panel_renders_playbook_actions_and_reacts_to_staged_rag_edits():
    baseline = _render_text()
    assert "Required actions" in baseline

    staged = _render_text(
        review_flow_pending_edits={"post_subjective": "Red", "post_mitigation": "Amber"},
    )
    # Workbook rows for Pre Mitigation Red / Post Mitigation Amber surface immediately,
    # before the staged picks are saved to the portfolio file.
    assert "Clearly document problems and mitigating controls/remediation plan." in staged
    assert "Document compensating controls and mitigating controls." in staged
    assert "unsaved" in staged


def test_required_actions_and_reviewer_signoff_fold_via_native_details():
    from dash import html

    layout = _render_pd_content_with()
    collapsibles = []
    for node in layout:
        collapsibles.extend(_collect_nodes_with_class(node, "pd-collapsible-card"))
    by_id = {getattr(card, "id", None): card for card in collapsibles}
    assert {"pd-conclusions-action-plan", "pd-conclusions-reviewer"} <= set(by_id)
    for card in by_id.values():
        assert isinstance(card, html.Details)
        assert card.open is False
        assert isinstance(card.children[0], html.Summary)
