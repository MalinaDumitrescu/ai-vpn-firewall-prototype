"""Decision / action-mapping logic. Simulation only — never blocks real traffic."""
from __future__ import annotations

from typing import Any, Dict, Tuple

# Sentinel value used by some policies to disable real blocking.
STRICT_ACTION_DISABLED = "DISABLED_DO_NOT_BLOCK"


def decide_action(
    session_score: float,
    thresholds: Dict[str, Any],
) -> Tuple[str, bool, bool]:
    """Map a session score to (action, strict_trigger, balanced_trigger).

    Supports two threshold formats:
      - Nested (robust9 / bagging-ensemble style):
          {"strict": {"threshold": ...}, "balanced": {"threshold": ...}}
      - Flat (full_canonical__lgbm / open_set_three_tier style):
          {"block_threshold": ..., "review_threshold": ...}

    Policy:
      - strict trigger  -> BLOCK (unless strict action is disabled)
      - balanced trigger only -> FLAG_REVIEW
      - neither -> PASS
    """
    strict = thresholds.get("strict", {}) or {}
    balanced = thresholds.get("balanced", {}) or {}

    # Flat-format fallback (full_canonical__lgbm open_set_three_tier)
    if not strict and not balanced:
        block_thr = thresholds.get("block_threshold")
        review_thr = thresholds.get("review_threshold")
        if block_thr is not None:
            strict = {"threshold": float(block_thr), "action": "BLOCK"}
        if review_thr is not None:
            balanced = {"threshold": float(review_thr), "action": "FLAG_REVIEW"}

    strict_thr = float(strict.get("threshold", float("inf")))
    balanced_thr = float(balanced.get("threshold", float("inf")))

    strict_action = str(strict.get("action", "BLOCK")).upper()
    strict_disabled = strict_action == STRICT_ACTION_DISABLED

    strict_trigger = session_score >= strict_thr and not strict_disabled
    balanced_trigger = session_score >= balanced_thr

    mapping = thresholds.get("action_mapping", {}) or {}
    block_label = mapping.get("strict_trigger", "BLOCK")
    review_label = mapping.get("balanced_trigger_only", "FLAG_REVIEW")
    pass_label = mapping.get("no_trigger", "PASS")

    if strict_trigger:
        action = block_label
    elif balanced_trigger:
        action = review_label
    else:
        action = pass_label

    # Hard safety: never emit BLOCK if strict action was disabled.
    if strict_disabled and action == "BLOCK":
        action = review_label

    return action, strict_trigger, balanced_trigger
