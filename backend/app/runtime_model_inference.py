"""Generic runtime inference engine for all allowlisted models.

Supports any diverse_bagging_ensemble model in the runtime bundle:
- XGB+LGBM+CatBoost or XGB-only families.
- Calibration: prob_iso (isotonic), prob_platt (Platt/LR), prob_raw (none).
- Session aggregation: p80 (80th-percentile), wt5 (mean of top-5 flows),
  mean, max.
- NEVER performs real blocking.  simulated=True on every decision.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd

from .policy_service import decide_action
from .registry_loader import (
    BUNDLE_ROOT,
    RUNTIME_MODELS_DIR,
    get_allowlisted_model_ids,
    get_model_entry,
    load_inference_allowlist,
)

_OPTIONAL_PASS_COLS = {"session_id", "flow_id", "dataset", "label"}


# --------------------------------------------------------------------------- helpers

def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _aggregate(scores: np.ndarray, method: str) -> float:
    if len(scores) == 0:
        return 0.0
    if method == "p80":
        return float(np.percentile(scores, 80))
    if method == "mean":
        return float(np.mean(scores))
    if method == "max":
        return float(np.max(scores))
    if method == "wt5":
        # Mean of top-5 highest flow scores (or all if < 5).
        k = max(1, min(5, len(scores)))
        return float(np.sort(scores)[-k:].mean())
    # Fallback: p80
    return float(np.percentile(scores, 80))


# --------------------------------------------------------------------------- engine

class RuntimeModelEngine:
    """Load and run one allowlisted bagging-ensemble model."""

    def __init__(self, model_id: str) -> None:
        allowed = get_allowlisted_model_ids()
        if model_id not in allowed:
            raise ValueError(
                f"Model '{model_id}' is not in the runtime inference allowlist."
            )

        model_dir: Path = RUNTIME_MODELS_DIR / model_id
        if not model_dir.exists():
            raise FileNotFoundError(
                f"Runtime model directory not found: {model_dir}"
            )

        self.model_id = model_id
        self.loader_config: Dict[str, Any] = _read_json(model_dir / "runtime_loader_config.json")
        self.feature_order: List[str] = _read_json(model_dir / "feature_order.json")["feature_order"]
        self.thresholds: Dict[str, Any] = _read_json(model_dir / "thresholds.json")

        self.probability_column: str = self.loader_config.get("probability_column", "prob_raw")
        self.session_aggregation: str = self.loader_config.get("session_aggregation", "p80")
        self.session_grouping_column: str = self.loader_config.get(
            "session_grouping_column", "session_id"
        )

        # Load model pickles (only families that exist).
        families: Dict[str, List[str]] = self.loader_config.get("model_files", {})
        self.models: Dict[str, List[Any]] = {}
        for family, paths in families.items():
            loaded = []
            for rel in paths:
                pkl = BUNDLE_ROOT / rel
                if pkl.exists():
                    loaded.append(joblib.load(pkl))
            if loaded:
                self.models[family] = loaded

        if not self.models:
            raise RuntimeError(
                f"No model pickles found for '{model_id}' in runtime bundle."
            )

        # Calibrators (optional — only load if file exists).
        cal = self.loader_config.get("calibrators", {})
        self.isotonic = self._load_optional_pkl(cal.get("isotonic"))
        self.platt = self._load_optional_pkl(cal.get("platt"))

        # Allowlist metadata.
        alist_data = load_inference_allowlist()
        self.is_default_firewall: bool = (
            alist_data.get("default_firewall") == model_id
        )
        self.is_comparison_only: bool = not self.is_default_firewall

    # ------------------------------------------------------------------ private

    @staticmethod
    def _load_optional_pkl(rel: Optional[str]) -> Optional[Any]:
        if not rel:
            return None
        path = BUNDLE_ROOT / rel
        return joblib.load(path) if path.exists() else None

    @staticmethod
    def _proba(model: Any, X: np.ndarray) -> np.ndarray:
        proba = np.asarray(model.predict_proba(X))
        if proba.ndim == 1:
            return proba
        return proba[:, -1]

    def _ensemble_raw(self, X: np.ndarray) -> np.ndarray:
        family_means: List[np.ndarray] = []
        for family, members in self.models.items():
            stacked = np.vstack([self._proba(m, X) for m in members])
            family_means.append(stacked.mean(axis=0))
        return np.mean(np.vstack(family_means), axis=0)

    def _calibrate(self, raw: np.ndarray) -> np.ndarray:
        col = self.probability_column
        if col == "prob_iso" and self.isotonic is not None:
            return np.asarray(self.isotonic.transform(raw))
        if col == "prob_platt" and self.platt is not None:
            try:
                return np.asarray(self.platt.predict_proba(raw.reshape(-1, 1))[:, 1])
            except Exception:
                try:
                    return np.asarray(self.platt.transform(raw))
                except Exception:
                    pass
        return raw  # prob_raw or calibrator unavailable

    # ------------------------------------------------------------------ public

    def score_dataframe(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, str, List[str]]:
        """Score flows.  Returns (scored_df, session_col, missing_features)."""
        missing = [f for f in self.feature_order if f not in df.columns]
        if missing:
            return df, "", missing

        X = df.loc[:, self.feature_order].to_numpy(dtype=float)
        raw = self._ensemble_raw(X)
        calibrated = self._calibrate(raw)

        out = df.copy()
        out["prob_raw"] = raw
        if self.probability_column != "prob_raw":
            out[self.probability_column] = calibrated

        # Session column resolution.
        session_col = self.session_grouping_column
        if session_col not in out.columns:
            for alt in ("session_id", "capture_id"):
                if alt in out.columns:
                    session_col = alt
                    break
            else:
                out["_session"] = np.arange(len(out)).astype(str)
                session_col = "_session"

        return out, session_col, []

    def build_session_decisions(
        self, scored: pd.DataFrame, session_col: str
    ) -> List[Dict[str, Any]]:
        prob_col = self.probability_column if self.probability_column in scored.columns else "prob_raw"
        results: List[Dict[str, Any]] = []
        for sid, grp in scored.groupby(session_col, sort=False):
            flow_scores = grp[prob_col].to_numpy(dtype=float)
            sess_score = _aggregate(flow_scores, self.session_aggregation)
            action, strict_trig, bal_trig = decide_action(sess_score, self.thresholds)
            results.append(
                {
                    "session_id": str(sid),
                    "n_flows": int(len(grp)),
                    "flow_score_mean": round(float(np.mean(flow_scores)), 4),
                    "flow_score_max": round(float(np.max(flow_scores)), 4),
                    "session_score": round(float(sess_score), 4),
                    "aggregation": self.session_aggregation,
                    "strict_trigger": bool(strict_trig),
                    "balanced_trigger": bool(bal_trig),
                    "action": action,
                    "simulated": True,
                    "action_mode": "simulation",
                }
            )
        return results

    def run(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Score a DataFrame and return a full result dict."""
        scored, session_col, missing = self.score_dataframe(df)
        if missing:
            return self._skipped_result(missing)

        sessions = self.build_session_decisions(scored, session_col)
        counts: Dict[str, int] = {"PASS": 0, "FLAG_REVIEW": 0, "BLOCK": 0}
        for s in sessions:
            counts[s["action"]] = counts.get(s["action"], 0) + 1

        registry_entry = get_model_entry(self.model_id) or {}

        return {
            "model_id": self.model_id,
            "status": registry_entry.get("status", "policy_computed"),
            "ui_badge": registry_entry.get("ui_badge", ""),
            "ui_warning": registry_entry.get("ui_warning", ""),
            "default_firewall": self.is_default_firewall,
            "comparison_only": self.is_comparison_only,
            "action_mode": "simulation",
            "production_readiness": False,
            "probability_column": self.probability_column,
            "aggregation": self.session_aggregation,
            "thresholds": {
                "strict": float(
                    self.thresholds.get("strict", {}).get("threshold", float("nan"))
                ),
                "balanced": float(
                    self.thresholds.get("balanced", {}).get("threshold", float("nan"))
                ),
            },
            "total_flows": int(len(scored)),
            "total_sessions": int(len(sessions)),
            "counts": counts,
            "sessions": sessions,
            "skipped": False,
            "missing_features": [],
            "warnings": [
                "Simulation only — no real packets are blocked.",
                "production_readiness=false; do not deploy as-is.",
                *(
                    ["Comparison model only — not deployment-approved."]
                    if self.is_comparison_only
                    else []
                ),
            ],
        }

    def _skipped_result(self, missing: List[str]) -> Dict[str, Any]:
        registry_entry = get_model_entry(self.model_id) or {}
        return {
            "model_id": self.model_id,
            "status": registry_entry.get("status", "policy_computed"),
            "ui_badge": registry_entry.get("ui_badge", ""),
            "ui_warning": registry_entry.get("ui_warning", ""),
            "default_firewall": self.is_default_firewall,
            "comparison_only": self.is_comparison_only,
            "action_mode": "simulation",
            "production_readiness": False,
            "probability_column": self.probability_column,
            "aggregation": self.session_aggregation,
            "thresholds": None,
            "total_flows": 0,
            "total_sessions": 0,
            "counts": {"PASS": 0, "FLAG_REVIEW": 0, "BLOCK": 0},
            "sessions": [],
            "skipped": True,
            "missing_features": missing,
            "warnings": [
                f"Skipped — CSV is missing {len(missing)} required feature(s): "
                + ", ".join(missing)
            ],
        }

    def get_feature_info(self) -> Dict[str, Any]:
        """Return feature metadata for this model."""
        return {
            "model_id": self.model_id,
            "feature_order": self.feature_order,
            "feature_count": len(self.feature_order),
        }


# --------------------------------------------------------------------------- registry

class EngineRegistry:
    """Thread-safe lazy-loaded store of RuntimeModelEngine instances."""

    def __init__(self) -> None:
        self._engines: Dict[str, RuntimeModelEngine] = {}
        self._lock = threading.Lock()

    def get(self, model_id: str) -> RuntimeModelEngine:
        if model_id not in self._engines:
            with self._lock:
                if model_id not in self._engines:
                    self._engines[model_id] = RuntimeModelEngine(model_id)
        return self._engines[model_id]

    def get_all(self) -> Dict[str, RuntimeModelEngine]:
        ids = get_allowlisted_model_ids()
        for mid in ids:
            self.get(mid)  # Trigger lazy load
        return {mid: self._engines[mid] for mid in ids if mid in self._engines}


_engine_registry = EngineRegistry()


def get_engine(model_id: str) -> RuntimeModelEngine:
    return _engine_registry.get(model_id)


def get_all_engines() -> Dict[str, RuntimeModelEngine]:
    return _engine_registry.get_all()

