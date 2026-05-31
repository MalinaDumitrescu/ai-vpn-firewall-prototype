"""Benchmark service for the unified and legacy comparison models.

Runs legacy comparison models against uploaded benchmark CSVs.
This is strictly read-only / benchmark-only and must NOT affect firewall decisions.

Executable model (v2) — NOT part of this benchmark page:
  - unified_relative_shape_v2__lgbm  (12 features, unified feature contract v2)
    → Tested in Live VM / Dashboard only.

Raw-feature benchmark-compatible legacy models (4 selectable):
  - full_canonical__lgbm            (34 features, legacy mixed-feature baseline)
  - robust9_firewall                (9 features, legacy baseline)
  - balanced_bagging_3ds_reference  (7 features, 3-dataset reference)
  - balanced_bagging_baseline       (7 features, 2-dataset baseline)

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

# ── executable + benchmark-compatible models ──────────────────────────────────
COMPATIBLE_BENCHMARK_MODEL_IDS: List[str] = [
    "unified_relative_shape_v2__lgbm",
]

# ── legacy benchmark models (comparison-only, not executable) ─────────────────
# These 4 models run against the simultaneous raw-feature benchmark CSV.
# full_canonical__lgbm is included as a legacy comparison baseline (domain_auc=1.0 — not the recommended model).
LEGACY_BENCHMARK_MODEL_IDS: List[str] = [
    "full_canonical__lgbm",
    "robust9_firewall",
    "balanced_bagging_3ds_reference",
    "balanced_bagging_baseline",
]

# Disabled: active runtime model — must never be run on the benchmark page.
BENCHMARK_DISABLED_RUNTIME_MODEL_ID: str = EXECUTABLE_FIREWALL_MODEL_ID  # "unified_relative_shape_v2__lgbm"
BENCHMARK_DISABLED_RUNTIME_REASON: str = (
    "Current final runtime model — tested in Live VM and Dashboard, "
    "not part of legacy benchmark comparison."
)

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
            "Legacy models (full_canonical__lgbm, robust9_firewall, etc.) are not executable — comparison/documentation only.",
        ],
    }


# ── legacy benchmark runner ───────────────────────────────────────────────────

def _score_model_for_legacy_benchmark(
    engine: RuntimeModelEngine,
    df: pd.DataFrame,
    has_labels: bool,
) -> Dict[str, Any]:
    """Score df with engine and return per-session + per-flow results."""
    from .policy_service import decide_action  # local import to avoid circular

    entry = get_model_entry(engine.model_id) or {}
    role = entry.get("role", "benchmark_comparison")

    scored, session_col, missing = engine.score_dataframe(df)
    if missing:
        return {
            "model_id": engine.model_id,
            "role": role,
            "executable": False,
            "comparison_only": True,
            "benchmark_compatible": False,
            "skipped": True,
            "skipped_reason": f"CSV missing {len(missing)} required feature(s)",
            "missing_features": missing,
            "rows_used": 0,
            "captures_used": 0,
            "sessions": [],
            "warning": BENCHMARK_WARNING,
        }

    # Prefer capture_id as session column
    if "capture_id" in scored.columns:
        session_col = "capture_id"

    prob_col = (
        engine.probability_column
        if engine.probability_column in scored.columns
        else "prob_raw"
    )

    block_thr = _get_block_threshold(engine)
    session_scores: List[float] = []
    session_labels: List[int] = []
    sessions_out: List[Dict[str, Any]] = []

    for sid, grp in scored.groupby(session_col, sort=False):
        flow_scores = grp[prob_col].to_numpy(dtype=float)
        sess_score = _aggregate(flow_scores, engine.session_aggregation)
        action, strict_trig, bal_trig = decide_action(sess_score, engine.thresholds)
        sess_label = _capture_label(grp)
        session_scores.append(sess_score)
        session_labels.append(sess_label)
        sessions_out.append({
            "session_id": str(sid),
            "n_flows": int(len(grp)),
            "session_score": round(float(sess_score), 4),
            "action": action,
            "strict_trigger": bool(strict_trig),
            "balanced_trigger": bool(bal_trig),
            "label": int(sess_label) if sess_label >= 0 else None,
            "correct": (
                int((action == "BLOCK") == bool(sess_label == 1))
                if sess_label >= 0 else None
            ),
        })

    counts: Dict[str, int] = {"PASS": 0, "FLAG_REVIEW": 0, "BLOCK": 0}
    for s in sessions_out:
        counts[s["action"]] = counts.get(s["action"], 0) + 1

    auc: Optional[float] = None
    confusion: Dict[str, int] = {}
    if has_labels and any(l >= 0 for l in session_labels):
        auc = _compute_auc(session_scores, session_labels)
        confusion = _compute_confusion(session_scores, session_labels, block_thr)

    result: Dict[str, Any] = {
        "model_id": engine.model_id,
        "role": role,
        "executable": False,
        "comparison_only": True,
        "benchmark_compatible": True,
        "skipped": False,
        "probability_column": prob_col,
        "aggregation": engine.session_aggregation,
        "block_threshold_used": round(block_thr, 6),
        "rows_used": int(len(scored)),
        "captures_used": int(len(sessions_out)),
        "missing_features": [],
        "action_counts": counts,
        "sessions": sessions_out,
        "warning": BENCHMARK_WARNING,
    }
    if auc is not None:
        result["AUC"] = round(auc, 4)
    if confusion:
        result.update(confusion)
    return result


def run_legacy_benchmark(
    df: pd.DataFrame,
    selected_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run selected legacy comparison models against df.

    selected_ids: subset of LEGACY_BENCHMARK_MODEL_IDS to run.
                  If None/empty, all compatible legacy models are attempted.
    Never runs unified_relative_shape_v2__lgbm — that belongs to Live VM / Dashboard.
    Results are benchmark-only and do NOT affect firewall decisions.
    """
    has_labels = "label" in df.columns

    # Validate selection — never allow the executable firewall model here
    safe_ids: List[str] = []
    if selected_ids:
        for mid in selected_ids:
            if mid == EXECUTABLE_FIREWALL_MODEL_ID:
                logger.warning("Legacy benchmark: rejected %s — this is the runtime firewall model", mid)
                continue
            if mid not in LEGACY_BENCHMARK_MODEL_IDS:
                logger.warning("Legacy benchmark: unknown/not-allowed model %s, skipping", mid)
                continue
            safe_ids.append(mid)
    if not safe_ids:
        safe_ids = list(LEGACY_BENCHMARK_MODEL_IDS)

    models_run: List[str] = []
    models_skipped: List[str] = []
    per_model_results: List[Dict[str, Any]] = []

    for model_id in safe_ids:
        try:
            engine = get_engine(model_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Legacy benchmark: engine load failed for %s: %s", model_id, exc)
            models_skipped.append(model_id)
            entry = get_model_entry(model_id) or {}
            per_model_results.append({
                "model_id": model_id,
                "role": entry.get("role", "benchmark_comparison"),
                "executable": False,
                "comparison_only": True,
                "benchmark_compatible": True,
                "skipped": True,
                "skipped_reason": f"Engine load error: {exc}",
                "missing_features": [],
                "rows_used": 0,
                "captures_used": 0,
                "sessions": [],
                "warning": BENCHMARK_WARNING,
            })
            continue

        result = _score_model_for_legacy_benchmark(engine, df, has_labels)
        per_model_results.append(result)
        if result["skipped"]:
            models_skipped.append(model_id)
        else:
            models_run.append(model_id)

    # Append incompatible models as always-disabled info entries
    not_selected_compatible = [
        mid for mid in LEGACY_BENCHMARK_MODEL_IDS if mid not in safe_ids
    ]
    for model_id in not_selected_compatible:
        entry = get_model_entry(model_id) or {}
        per_model_results.append({
            "model_id": model_id,
            "role": entry.get("role", "benchmark_comparison"),
            "executable": False,
            "comparison_only": True,
            "benchmark_compatible": True,
            "skipped": True,
            "skipped_reason": "Not selected for this benchmark run.",
            "missing_features": [],
            "rows_used": 0,
            "captures_used": 0,
            "sessions": [],
            "warning": BENCHMARK_WARNING,
        })

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
                "the raw-feature benchmark CSV."
            ),
            "missing_features": INCOMPATIBLE_MISSING_FEATURES,
            "rows_used": 0,
            "captures_used": 0,
            "sessions": [],
            "warning": (
                "Not benchmark-compatible. Requires session-derived probability features."
            ),
        })

    total_sessions = (
        int(df["capture_id"].nunique())
        if "capture_id" in df.columns
        else int(df["session_id"].nunique())
        if "session_id" in df.columns
        else int(len(df))
    )

    # Build per-flow comparison table: each row = one flow, columns = per-model scores
    per_flow_rows: List[Dict[str, Any]] = []
    if models_run:
        # Only include columns that exist in df
        id_cols = [c for c in ["flow_id", "session_id", "capture_id", "dataset", "label"] if c in df.columns]
        base = df[id_cols].copy() if id_cols else pd.DataFrame(index=df.index)
        base = base.reset_index(drop=True)
        for i, row in base.iterrows():
            flow_row: Dict[str, Any] = {k: (None if pd.isna(v) else v) for k, v in row.items()}
            per_flow_rows.append(flow_row)

        for model_id in models_run:
            engine = get_engine(model_id)
            scored, _, _ = engine.score_dataframe(df)
            if scored is None:
                continue
            prob_col = (
                engine.probability_column
                if engine.probability_column in scored.columns
                else "prob_raw"
            )
            from .policy_service import decide_action
            scores = scored[prob_col].to_numpy(dtype=float)
            has_lbl = "label" in df.columns
            for i, (score, flow_row) in enumerate(zip(scores, per_flow_rows)):
                action, _, _ = decide_action(float(score), engine.thresholds)
                flow_row[f"{model_id}__score"] = round(float(score), 4)
                flow_row[f"{model_id}__action"] = action
                if has_lbl and flow_row.get("label") is not None:
                    try:
                        lbl = float(flow_row["label"])
                        pred_pos = action == "BLOCK"
                        flow_row[f"{model_id}__correct"] = bool(pred_pos == (lbl == 1.0))
                    except (TypeError, ValueError):
                        pass

    return {
        "benchmark_only": True,
        "runtime_model_note": (
            f"'{EXECUTABLE_FIREWALL_MODEL_ID}' is the active runtime firewall model "
            "and is NOT included in this legacy benchmark. "
            "See Dashboard and Live VM for runtime inference."
        ),
        "benchmark_csv_info": {
            "rows": int(len(df)),
            "sessions": total_sessions,
            "has_labels": has_labels,
        },
        "models_run": models_run,
        "models_skipped": models_skipped,
        "per_model_results": per_model_results,
        "per_flow_predictions": per_flow_rows,
        "per_flow_model_columns": [mid for mid in models_run],
        "warnings": [
            BENCHMARK_WARNING,
            "These are legacy comparison models — not the active runtime firewall model.",
            (
                "balanced_bagging_xgb_baseline and robust13_comparison require "
                "session-derived probability features and are excluded."
            ),
        ],
    }


def get_legacy_benchmark_model_info() -> Dict[str, Any]:
    """Return metadata for all legacy benchmark models (compatible + incompatible + disabled)."""
    from .registry_loader import RUNTIME_MODELS_DIR, _read_json

    def _feature_order(model_id: str) -> List[str]:
        model_dir = RUNTIME_MODELS_DIR / model_id
        try:
            fo = _read_json(model_dir / "feature_order.json")
            if fo:
                return fo.get("feature_order", fo.get("features", []))
        except Exception:
            pass
        return []

    compatible = []
    for model_id in LEGACY_BENCHMARK_MODEL_IDS:
        entry = get_model_entry(model_id) or {}
        fo = _feature_order(model_id)
        compatible.append({
            "model_id": model_id,
            "benchmark_compatible": True,
            "selectable": True,
            "executable": False,
            "comparison_only": True,
            "role": entry.get("role", "benchmark_comparison"),
            "ui_badge": entry.get("ui_badge", ""),
            "ui_warning": entry.get("ui_warning", ""),
            "feature_count": len(fo),
            "feature_order": fo,
            "status": entry.get("status", "policy_computed"),
        })

    # Incompatible: require session-derived features
    incompatible_reasons: Dict[str, str] = {
        "balanced_bagging_xgb_baseline": (
            "Requires session-derived features not present in the raw benchmark CSV."
        ),
        "robust13_comparison": (
            "Requires session-derived features not present in the raw benchmark CSV."
        ),
    }
    incompatible = []
    for model_id in INCOMPATIBLE_MODEL_IDS:
        entry = get_model_entry(model_id) or {}
        incompatible.append({
            "model_id": model_id,
            "benchmark_compatible": False,
            "selectable": False,
            "executable": False,
            "comparison_only": True,
            "role": entry.get("role", "benchmark_comparison"),
            "ui_badge": entry.get("ui_badge", ""),
            "ui_warning": entry.get("ui_warning", ""),
            "disabled_reason": incompatible_reasons.get(
                model_id,
                "Requires session-derived/extra features; not compatible with raw benchmark CSV.",
            ),
            "missing_features": INCOMPATIBLE_MISSING_FEATURES,
            "status": entry.get("status", "comparison_only"),
        })

    # Explicitly disabled: the active runtime firewall model
    disabled_runtime = []
    runtime_entry = get_model_entry(EXECUTABLE_FIREWALL_MODEL_ID) or {}
    runtime_fo = _feature_order(EXECUTABLE_FIREWALL_MODEL_ID)
    disabled_runtime.append({
        "model_id": EXECUTABLE_FIREWALL_MODEL_ID,
        "benchmark_compatible": False,
        "selectable": False,
        "executable": True,
        "comparison_only": False,
        "role": runtime_entry.get("role", "recommended_firewall"),
        "ui_badge": runtime_entry.get("ui_badge", ""),
        "ui_warning": runtime_entry.get("ui_warning", ""),
        "disabled_reason": BENCHMARK_DISABLED_RUNTIME_REASON,
        "feature_count": len(runtime_fo),
        "feature_order": runtime_fo,
        "status": runtime_entry.get("status", "recommended_firewall"),
    })

    union_features: set = set()
    for m in compatible:
        union_features.update(m["feature_order"])

    return {
        "compatible_models": compatible,
        "incompatible_models": incompatible,
        "disabled_runtime_models": disabled_runtime,
        "union_required_features": sorted(union_features),
        "union_feature_count": len(union_features),
        "optional_columns": ["session_id", "capture_id", "flow_id", "dataset", "label"],
        "runtime_model_note": (
            f"'{EXECUTABLE_FIREWALL_MODEL_ID}' is the active runtime model "
            "and cannot be selected on this benchmark page. "
            "Use Live VM or Dashboard for runtime inference."
        ),
    }
