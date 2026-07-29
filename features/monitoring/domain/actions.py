"""Selects governance playbook actions for the PD review-flow RAGs.

The monitoring playbook (``monitoring_rules.xlsx`` · ``monitoring_actions`` sheet)
defines one required-action row per ``(stage, RAG)`` for the "Pre Mitigation"
and "Post Mitigation" stages, plus a persistent-breach escalation row that
replaces the standard Post-Mitigation Red row when two consecutive quarters
are Red.

Which review-flow RAG drives each row is read from the row's ``Trigger``
column (e.g. "Latest Post Subjective Review RAG" keys the row off the Post
Subjective Review RAG card), so re-pointing an action at a different RAG is a
workbook edit, not a code change. Trigger text is matched tolerantly
(case/punctuation-insensitive) so wording tweaks like "Post-Mitigation" vs
"Post Mitigation" don't break the mapping; a trigger that names no known card
falls back to the stage's namesake RAG.
"""

from __future__ import annotations

import re

PD_ACTION_STAGE_PRE = "Pre Mitigation"
PD_ACTION_STAGE_POST = "Post Mitigation"

_RAG_RANK = {"N/A": -1, "Green": 0, "Amber": 1, "Red": 2}

# Longest-first, so "post subjective" wins before any shorter phrase could.
_TRIGGER_FIELD_PHRASES = (
    ("post subjective", "post_subjective"),
    ("pre mitigation", "pre_mitigation"),
    ("post mitigation", "post_mitigation"),
)

_STAGE_DEFAULT_FIELD = {
    PD_ACTION_STAGE_PRE: "pre_mitigation",
    PD_ACTION_STAGE_POST: "post_mitigation",
}


def _normalize_trigger(trigger) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(trigger or "").lower()).strip()


def is_persistent_breach_trigger(trigger) -> bool:
    """True for the "two consecutive ... Red" escalation trigger, however it's punctuated."""
    return "two consecutive" in _normalize_trigger(trigger)


def trigger_driver_field(trigger, stage: str) -> str:
    """The review-flow field a playbook row's ``Trigger`` text names."""
    normalized = _normalize_trigger(trigger)
    for phrase, field in _TRIGGER_FIELD_PHRASES:
        if phrase in normalized:
            return field
    return _STAGE_DEFAULT_FIELD.get(stage, "post_mitigation")


def select_pd_monitoring_actions(
    actions: list[dict],
    review_flow_rags: dict[str, str],
    previous_post_mitigation_rag: str = "",
) -> list[dict]:
    """The playbook action per stage for the current (effective) review-flow RAGs.

    ``review_flow_rags`` carries the effective ``post_subjective`` /
    ``pre_mitigation`` / ``post_mitigation`` values (staged edits already
    applied by the caller). ``previous_post_mitigation_rag`` is the prior
    monitoring quarter's saved Post Mitigation RAG, used only to detect the
    persistent-breach escalation.

    Returns one selection dict per stage (Pre Mitigation first):
    ``{"stage", "rag", "drivers", "action", "persistent_breach"}`` where
    ``action`` is the matched playbook row (or ``None`` when the driving RAG
    is N/A or the playbook has no matching row) and ``drivers`` lists the
    ``(field, rag)`` pairs the stage's rows trigger off.
    """
    selections = []
    for stage in (PD_ACTION_STAGE_PRE, PD_ACTION_STAGE_POST):
        stage_rows = [row for row in actions or [] if str(row.get("stage", "")).strip() == stage]
        standard_rows = [row for row in stage_rows if not is_persistent_breach_trigger(row.get("trigger"))]
        breach_rows = [row for row in stage_rows if is_persistent_breach_trigger(row.get("trigger"))]

        driver_fields: list[str] = []
        for row in standard_rows:
            field = trigger_driver_field(row.get("trigger"), stage)
            if field not in driver_fields:
                driver_fields.append(field)
        if not driver_fields:
            driver_fields = [_STAGE_DEFAULT_FIELD[stage]]
        drivers = [(field, review_flow_rags.get(field, "N/A")) for field in driver_fields]

        action = None
        persistent_breach = False
        if (
            breach_rows
            and review_flow_rags.get("post_mitigation") == "Red"
            and previous_post_mitigation_rag == "Red"
        ):
            action = breach_rows[0]
            persistent_breach = True
        if action is None:
            for row in standard_rows:
                field = trigger_driver_field(row.get("trigger"), stage)
                field_rag = review_flow_rags.get(field, "N/A")
                if field_rag != "N/A" and str(row.get("rag", "")).strip() == field_rag:
                    action = row
                    break

        if action is not None and not persistent_breach:
            rag = str(action.get("rag", "")).strip()
        elif persistent_breach:
            rag = "Red"
        else:
            rag = max((rag for _, rag in drivers), key=lambda value: _RAG_RANK.get(value, -1))

        selections.append({
            "stage": stage,
            "rag": rag,
            "drivers": drivers,
            "action": action,
            "persistent_breach": persistent_breach,
        })
    return selections
