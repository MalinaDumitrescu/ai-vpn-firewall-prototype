"""Benchmark service for the 4 audit-approved compatible models.

Runs compatible models against the simultaneous benchmark CSV.
This is strictly read-only / benchmark-only and must NOT affect firewall decisions.

Compatible models (raw-feature simultaneous benchmarking):
  - full_canonical__lgbm       (34 features, executable firewall model)
  - robust9_firewall           (9 features, legacy baseline)
  - balanced_bagging_3ds_reference  (7 features, 3-dataset reference)
  - balanced_bagging_baseline  (7 features, 2-dataset baseline)

Incompatible models (require session-derived probability features):
  - balanced_bagging_xgb_baseline   (needs session_mean_prob, etc.)
  - robust13_comparison             (needs session_mean_prob, etc.)
"""
from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .registry_loader import EXECUTABLE_FIREWALL_MODEL_ID, get_model_entry
from .runtime_model_inference import RuntimeModelEngine, _aggregate, get_engine

logger = logging.getLogger("ai_vpn_firewall.benchmark")

# ── audit-approved compatible models ──────────────────────────────────────────
COMPATIBLE_BENCHMARK_MODEL_IDS: List[str] = [
    "full_canonical__lgbm",
    "robust9_firewall",
    "balanced_bagging_3ds_reference",
    "balanced_bagging_baseline",
]

# These require session-derived prior-stage features and cannot run raw-feature benchmark.
INCOMPATIBLE_MODEL_IDS: List[str] = [
    "balanced_bagging_xgb_baseline",
    "robust13_comparison",
]

INCOMPATIBLE_MISSING_FEATURES: List[str] = [
    "session_mean_prob",
    "session_var_prob",
    "session_top_k_mean_prob",
    "session_consecutive_high_runs",
    "session_fraction_high",
]

BENCHMARK_WARNING = "Benchmark-only. Does not affect firewall decisions."


# ── label helpers ─────────────────────────────────────────────────────────────

def _capture_label(grp: pd.DataFrame) -> int:
    """Return capture-level ground-truth: 1 if any flow is VPN/attack, else 0.
    Returns -1 if label column is absent or entirely missing.
    """
    if "label" not in grp.columns:
        return -1
    vals = grp["label"].dropna()
    if len(vals) == 0:
        return -1
    try:
        return int(any(float(v) == 1.0 for v in vals))
    except (ValueError, TypeError):
        return -1


# ── AUC / confusion matrix ────────────────────────────────────────────────────

def _compute_auc(scores: List[float], labels: List[int]) -> Optional[float]:
    """ROC-AUC from session-level scores and binary labels.
    Returns None if both classes are not present.
    """
    valid = [(s, l) for s, l in zip(scores, labels) if l >= 0]
    if len(valid) < 2:
        return None
    s_vals = [v[0] for v in valid]
    l_vals = [v[1] for v in valid]
    if len(set(l_vals)) < 2:
        return None
    try:
        from sklearn.metrics import roc_auc_score  # type: ignore[import]
        return float(roc_auc_score(l_vals, s_vals))
    except ImportError:
        pass
    # Fallback: manual trapezoidal AUC
    n_pos = sum(l_vals)
    n_neg = len(l_vals) - n_pos
    if n_pos == 0 or n_neg == 0:
        return None
    pairs = sorted(zip(s_vals, l_vals), key=lambda x: x[0], reverse=True)
    tp = fp = auc = 0.0
    prev_fpr = 0.0
    prev_tpr = 0.0
    for _, lbl in pairs:
        if lbl == 1:
            tp += 1
        else:
            fp += 1
        tpr = tp / n_pos
        fpr = fp / n_neg
        auc += (fpr - prev_fpr) * (prev_tpr + tpr) / 2.0
        prev_fpr, prev_tpr = fpr, tpr
    return round(float(auc), 6)


def _compute_confusion(
    scores: List[float],
    labels: List[int],
    threshold: float,
) -> Dict[str, int]:
    """TP/FP/TN/FN using `threshold` as the BLOCK decision boundary.

    Positive = score >= threshold (session would be BLOCK).
    Negative = score < threshold  (session is PASS or FLAG_REVIEW).
    """
    tp = fp = tn = fn = 0
    for score, label in zip(scores, labels):
        if label < 0:
            continue
        pred_positive = score >= threshold
        if pred_positive and label == 1:
            tp += 1
        elif pred_positive and label == 0:
            fp += 1
        elif not pred_positive and label == 0:
            tn += 1
        else:
            fn += 1
    return {"TP": tp, "FP": fp, "TN": tn, "FN": fn}


def _get_block_threshold(engine: RuntimeModelEngine) -> float:
    """Extract the block / strict threshold from the engine's thresholds dict."""
    th = engine.thresholds
    if not isinstance(th, dict):
        return 0.5
    # Nested format: {"strict": {"threshold": ...}}
    strict = th.get("strict", {})
    if isinstance(strict, dict) and "threshold" in strict:
        return float(strict["threshold"])
    # Flat format (full_canonical__lgbm): {"block_threshold": ...}
    if "block_threshold" in th:
        return float(th["block_threshold"])
    return 0.5


# ── main benchmark runner ─────────────────────────────────────────────────────

def run_benchmark(df: pd.DataFrame) -> Dict[str, Any]:
    """Score the 4 compatible models against `df` and return structured results.

    - Each model selects its own feature_order.
    - Extra columns in `df` are silently ignored.
    - Missing required features for a model cause that model to be skipped.
    - AUC, TP/FP/TN/FN are computed if `label` column is present.
    - Results are marked benchmark-only and do NOT affect firewall decisions.
    """
    has_labels = "label" in df.columns
    models_run: List[str] = []
    models_skipped: List[str] = []
    per_model_results: List[Dict[str, Any]] = []

    for model_id in COMPATIBLE_BENCHMARK_MODEL_IDS:
        is_firewall = model_id == EXECUTABLE_FIREWALL_MODEL_ID
        entry = get_model_entry(model_id) or {}
        role = entry.get("role", "benchmark_comparison" if not is_firewall else "recommended_firewall")

        # Load engine
        try:
            engine = get_engine(model_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Benchmark: engine load failed for %s: %s", model_id, exc)
            models_skipped.append(model_id)
            per_model_results.append({
                "model_id": model_id,
                "role": role,
                "executable": is_firewall,
                "comparison_only": not is_firewall,
                "benchmark_compatible": True,
                "skipped": True,
                "skipped_reason": f"Engine load error: {exc}",
                "missing_features": [],
                "rows_used": 0,
                "captures_used": 0,
                "warning": BENCHMARK_WARNING,
            })
            continue

        # Score flows (each model selects its own feature_order)
        scored, session_col, missing = engine.score_dataframe(df)

        if missing:
            logger.info("Benchmark: %s skipped — missing %d feature(s)", model_id, len(missing))
            models_skipped.append(model_id)
            per_model_results.append({
                "model_id": model_id,
                "role": role,
                "executable": is_firewall,
                "comparison_only": not is_firewall,
                "benchmark_compatible": False,
                "skipped": True,
                "skipped_reason": f"CSV missing {len(missing)} required feature(s)",
                "missing_features": missing,
                "rows_used": 0,
                "captures_used": 0,
                "warning": BENCHMARK_WARNING,
            })
            continue

        # Prefer capture_id as grouping column
        if "capture_id" in scored.columns:
            session_col = "capture_id"

        # Probability column
        prob_col = (
            engine.probability_column
            if engine.probability_column in scored.columns
            else "prob_raw"
        )

        # Build per-session scores and labels
        session_scores: List[float] = []
        session_labels: List[int] = []
        session_ids: List[str] = []

        for sid, grp in scored.groupby(session_col, sort=False):
            flow_scores = grp[prob_col].to_numpy(dtype=float)
            sess_score = _aggregate(flow_scores, engine.session_aggregation)
            session_scores.append(sess_score)
            session_labels.append(_capture_label(grp))
            session_ids.append(str(sid))

        # Action counts using engine thresholds
        from .policy_service import decide_action  # local import to avoid circular
        counts: Dict[str, int] = {"PASS": 0, "FLAG_REVIEW": 0, "BLOCK": 0}
        for score in session_scores:
            action, _, _ = decide_action(score, engine.thresholds)
            counts[action] = counts.get(action, 0) + 1

        # AUC + confusion matrix
        auc: Optional[float] = None
        confusion: Dict[str, int] = {}
        block_thr = _get_block_threshold(engine)
        if has_labels and any(l >= 0 for l in session_labels):
            auc = _compute_auc(session_scores, session_labels)
            confusion = _compute_confusion(session_scores, session_labels, block_thr)

        models_run.append(model_id)
        result: Dict[str, Any] = {
            "model_id": model_id,
            "role": role,
            "executable": is_firewall,
            "comparison_only": not is_firewall,
            "benchmark_compatible": True,
            "skipped": False,
            "probability_column": prob_col,
            "aggregation": engine.session_aggregation,
            "rows_used": int(len(scored)),
            "captures_used": int(len(session_scores)),
            "missing_features": [],
            "skipped_rows": 0,
            "action_counts": counts,
            "block_threshold_used": round(block_thr, 6),
            "warning": BENCHMARK_WARNING,
        }
        if auc is not None:
            result["AUC"] = round(auc, 4)
        if confusion:
            result.update(confusion)

        per_model_results.append(result)

    # Mark incompatible models as excluded (read-only, never run)
    for model_id in INCOMPATIBLE_MODEL_IDS:
        entry = get_model_entry(model_id) or {}
        per_model_results.append({
            "model_id": model_id,
            "role": entry.get("role", "benchmark_comparison"),
            "executable": False,
            "comparison_only": True,
            "benchmark_compatible": False,
            "skipped": True,
            "skipped_reason": (
                "Requires session-derived probability features not present in "
                "the raw-feature simultaneous benchmark CSV."
            ),
            "missing_features": INCOMPATIBLE_MISSING_FEATURES,
            "rows_used": 0,
            "captures_used": 0,
            "warning": (
                "Not compatible with raw-feature simultaneous benchmark CSV. "
                "Never included in simultaneous benchmark."
            ),
        })

    total_captures = (
        int(df["capture_id"].nunique())
        if "capture_id" in df.columns
        else int(len(df))
    )

    return {
        "benchmark_only": True,
        "firewall_model": EXECUTABLE_FIREWALL_MODEL_ID,
        "executable_firewall_model_only": True,
        "benchmark_csv_info": {
            "rows": int(len(df)),
            "captures": total_captures,
            "has_labels": has_labels,
            "note": "simultaneous_test_selected_models.csv — 7,952 flows, 104 captures",
        },
        "models_run": models_run,
        "models_skipped": models_skipped,
        "per_model_results": per_model_results,
        "warnings": [
            BENCHMARK_WARNING,
            f"Only '{EXECUTABLE_FIREWALL_MODEL_ID}' is executable as the firewall prototype.",
            (
                "balanced_bagging_xgb_baseline and robust13_comparison are excluded from "
                "raw-feature simultaneous benchmarking (require session-derived features)."
            ),
        ],
    }

