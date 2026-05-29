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

from .registry_loader import (
    EXECUTABLE_FIREWALL_MODEL_ID,
    BENCHMARK_COMPATIBLE_MODEL_IDS,
    BENCHMARK_INCOMPATIBLE_MODEL_IDS,
    get_model_entry,
)
from .runtime_model_inference import RuntimeModelEngine, _aggregate, get_engine
from .policy_service import decide_action

logger = logging.getLogger("ai_vpn_firewall.benchmark")

# ── aliases for backward compatibility ────────────────────────────────────────
COMPATIBLE_BENCHMARK_MODEL_IDS: List[str] = BENCHMARK_COMPATIBLE_MODEL_IDS
INCOMPATIBLE_MODEL_IDS: List[str] = BENCHMARK_INCOMPATIBLE_MODEL_IDS

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
    """TP/FP/TN/FN using `threshold` as the BLOCK decision boundary."""
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
    strict = th.get("strict", {})
    if isinstance(strict, dict) and "threshold" in strict:
        return float(strict["threshold"])
    if "block_threshold" in th:
        return float(th["block_threshold"])
    return 0.5


def _parse_label(v: Any) -> Optional[int]:
    """Parse a single label value, returning int (0/1) or None."""
    try:
        if pd.isna(v):
            return None
        return int(float(v))
    except (ValueError, TypeError):
        return None


# ── main benchmark runner ─────────────────────────────────────────────────────

def run_benchmark(
    df: pd.DataFrame,
    selected_model_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Score compatible models against `df` and return structured results.

    Parameters:
        df: DataFrame of flow features.
        selected_model_ids: If provided, only run these model IDs (must all be in
            COMPATIBLE_BENCHMARK_MODEL_IDS). If None, run all 4 compatible models.

    Returns dict with:
        per_model_results / results  — model-level performance
        per_flow_predictions         — per-flow scored rows
        per_session_predictions      — per-session aggregated decisions
    """
    # Validate / resolve model list
    if selected_model_ids is not None:
        invalid = [m for m in selected_model_ids if m not in COMPATIBLE_BENCHMARK_MODEL_IDS]
        if invalid:
            raise ValueError(
                f"The following model IDs are not benchmark-compatible: {invalid}. "
                f"Only {COMPATIBLE_BENCHMARK_MODEL_IDS} are allowed."
            )
        model_ids_to_run = [m for m in COMPATIBLE_BENCHMARK_MODEL_IDS if m in set(selected_model_ids)]
    else:
        model_ids_to_run = list(COMPATIBLE_BENCHMARK_MODEL_IDS)

    has_labels = "label" in df.columns
    models_run: List[str] = []
    models_skipped: List[str] = []
    per_model_results: List[Dict[str, Any]] = []
    per_flow_predictions: List[Dict[str, Any]] = []
    per_session_predictions: List[Dict[str, Any]] = []

    for model_id in model_ids_to_run:
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
        block_thr = _get_block_threshold(engine)

        # ── Per-flow predictions ──────────────────────────────────────────────
        n_rows = len(scored)
        prob_scores_arr = scored[prob_col].to_numpy(dtype=float)
        pred_labels_arr = (prob_scores_arr >= block_thr).astype(int)

        # Passthrough metadata columns
        dataset_vals = scored["dataset"].fillna("").astype(str).tolist() if "dataset" in scored.columns else [""] * n_rows
        capture_vals = scored["capture_id"].astype(str).tolist() if "capture_id" in scored.columns else [None] * n_rows
        session_vals = scored["session_id"].astype(str).tolist() if "session_id" in scored.columns else [None] * n_rows
        flow_vals    = scored["flow_id"].astype(str).tolist() if "flow_id" in scored.columns else [None] * n_rows

        # True labels (flow level)
        true_labels_flow: List[Optional[int]] = []
        if has_labels and "label" in scored.columns:
            for v in scored["label"]:
                true_labels_flow.append(_parse_label(v))
        else:
            true_labels_flow = [None] * n_rows

        for i, (row_idx, prob_score, pred_label, true_label) in enumerate(
            zip(scored.index, prob_scores_arr, pred_labels_arr, true_labels_flow)
        ):
            if true_label is None:
                error_type = "unknown_label"
                correct: Optional[bool] = None
            elif pred_label == 1 and true_label == 1:
                error_type = "TP"; correct = True
            elif pred_label == 1 and true_label == 0:
                error_type = "FP"; correct = False
            elif pred_label == 0 and true_label == 0:
                error_type = "TN"; correct = True
            else:
                error_type = "FN"; correct = False

            per_flow_predictions.append({
                "row_index":          int(row_idx),
                "model_id":           model_id,
                "dataset":            dataset_vals[i],
                "capture_id":         capture_vals[i],
                "session_id":         session_vals[i],
                "flow_id":            flow_vals[i],
                "true_label":         true_label,
                "true_class_text":    "VPN" if true_label == 1 else ("nonVPN" if true_label == 0 else "unknown"),
                "probability_score":  round(float(prob_score), 6),
                "predicted_label":    int(pred_label),
                "predicted_class_text": "VPN" if pred_label == 1 else "nonVPN",
                "threshold_used":     round(block_thr, 6),
                "correct":            correct,
                "error_type":         error_type,
            })

        # ── Per-session / per-capture predictions ─────────────────────────────
        session_scores_list: List[float] = []
        session_labels_list: List[int] = []

        for sid, grp in scored.groupby(session_col, sort=False):
            flow_scores_grp = grp[prob_col].to_numpy(dtype=float)
            sess_score = _aggregate(flow_scores_grp, engine.session_aggregation)
            session_scores_list.append(sess_score)

            pred_positive = sess_score >= block_thr
            pred_lbl = 1 if pred_positive else 0

            sess_true_label = _capture_label(grp)
            session_labels_list.append(sess_true_label)

            if sess_true_label < 0:
                s_error_type = "unknown_label"
                s_correct: Optional[bool] = None
            elif pred_lbl == 1 and sess_true_label == 1:
                s_error_type = "TP"; s_correct = True
            elif pred_lbl == 1 and sess_true_label == 0:
                s_error_type = "FP"; s_correct = False
            elif pred_lbl == 0 and sess_true_label == 0:
                s_error_type = "TN"; s_correct = True
            else:
                s_error_type = "FN"; s_correct = False

            action, _, _ = decide_action(sess_score, engine.thresholds)

            ds_val  = str(grp["dataset"].iloc[0]) if "dataset" in grp.columns and len(grp) > 0 else ""
            cap_val = str(grp["capture_id"].iloc[0]) if "capture_id" in grp.columns and len(grp) > 0 else str(sid)
            ses_val = str(grp["session_id"].iloc[0]) if "session_id" in grp.columns and len(grp) > 0 else str(sid)

            per_session_predictions.append({
                "model_id":            model_id,
                "dataset":             ds_val,
                "capture_id":          cap_val,
                "session_id":          ses_val,
                "n_flows":             int(len(grp)),
                "aggregation":         engine.session_aggregation,
                "aggregated_score":    round(float(sess_score), 6),
                "threshold_used":      round(block_thr, 6),
                "true_label":          sess_true_label if sess_true_label >= 0 else None,
                "true_class_text":     "VPN" if sess_true_label == 1 else ("nonVPN" if sess_true_label == 0 else "unknown"),
                "predicted_label":     pred_lbl,
                "predicted_class_text": "VPN" if pred_lbl == 1 else "nonVPN",
                "correct":             s_correct,
                "error_type":          s_error_type,
                "action":              action,
                "simulated":           True,
            })

        # ── Action counts ─────────────────────────────────────────────────────
        counts: Dict[str, int] = {"PASS": 0, "FLAG_REVIEW": 0, "BLOCK": 0}
        for score in session_scores_list:
            action_name, _, _ = decide_action(score, engine.thresholds)
            counts[action_name] = counts.get(action_name, 0) + 1

        # ── AUC + confusion matrix ────────────────────────────────────────────
        auc: Optional[float] = None
        confusion: Dict[str, int] = {}
        if has_labels and any(l >= 0 for l in session_labels_list):
            auc = _compute_auc(session_scores_list, session_labels_list)
            confusion = _compute_confusion(session_scores_list, session_labels_list, block_thr)

        models_run.append(model_id)
        result: Dict[str, Any] = {
            "model_id":            model_id,
            "role":                role,
            "executable":          is_firewall,
            "comparison_only":     not is_firewall,
            "benchmark_compatible": True,
            "skipped":             False,
            "probability_column":  prob_col,
            "aggregation":         engine.session_aggregation,
            "block_threshold_used": round(block_thr, 6),
            "feature_count":       len(engine.feature_order),
            "rows_used":           int(len(scored)),
            "captures_used":       int(len(session_scores_list)),
            "missing_features":    [],
            "skipped_rows":        0,
            "action_counts":       counts,
            "warning":             BENCHMARK_WARNING,
        }
        if auc is not None:
            result["AUC"] = round(auc, 4)
            result["auc"] = round(auc, 4)
        if confusion:
            result.update(confusion)  # TP, FP, TN, FN (uppercase)
            tp_v = confusion.get("TP", 0)
            fp_v = confusion.get("FP", 0)
            tn_v = confusion.get("TN", 0)
            fn_v = confusion.get("FN", 0)
            result["tp"] = tp_v
            result["fp"] = fp_v
            result["tn"] = tn_v
            result["fn"] = fn_v
            # Extended derived metrics
            result["precision"] = round(tp_v / (tp_v + fp_v), 4) if (tp_v + fp_v) > 0 else None
            result["recall"]    = round(tp_v / (tp_v + fn_v), 4) if (tp_v + fn_v) > 0 else None
            result["fpr"]       = round(fp_v / (fp_v + tn_v), 4) if (fp_v + tn_v) > 0 else None
            result["accuracy"]  = round((tp_v + tn_v) / (tp_v + fp_v + tn_v + fn_v), 4) if (tp_v + fp_v + tn_v + fn_v) > 0 else None

        per_model_results.append(result)

    # Mark incompatible models as excluded (read-only, never run)
    # Only append these when running all models (not a user selection)
    if selected_model_ids is None:
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
        "selected_model_ids": model_ids_to_run,
        "benchmark_csv_info": {
            "rows": int(len(df)),
            "captures": total_captures,
            "has_labels": has_labels,
            "note": "simultaneous_test_selected_models.csv — 7,952 flows, 104 captures",
        },
        "models_run":          models_run,
        "models_skipped":      models_skipped,
        "per_model_results":   per_model_results,
        # `results` alias — only benchmark_compatible (run + skipped-compat) entries
        "results": [r for r in per_model_results if r.get("benchmark_compatible", False)],
        "per_flow_predictions":    per_flow_predictions,
        "per_session_predictions": per_session_predictions,
        "warnings": [
            BENCHMARK_WARNING,
            f"Only '{EXECUTABLE_FIREWALL_MODEL_ID}' is executable as the firewall prototype.",
            (
                "balanced_bagging_xgb_baseline and robust13_comparison are excluded from "
                "raw-feature simultaneous benchmarking (require session-derived features)."
            ),
        ],
    }

