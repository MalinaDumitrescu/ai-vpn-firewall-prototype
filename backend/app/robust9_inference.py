"""Real inference for the robust9_firewall ensemble.

This is the ONLY model in the runtime bundle that ships binaries. All other
registry entries are metadata/comparison-only and must not be invoked here.
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
from .registry_loader import BUNDLE_ROOT, RUNTIME_MODELS_DIR

ROBUST9_MODEL_ID = "robust9_firewall"
ROBUST9_DIR = RUNTIME_MODELS_DIR / ROBUST9_MODEL_ID
LOADER_CONFIG_PATH = ROBUST9_DIR / "runtime_loader_config.json"
FEATURE_ORDER_PATH = ROBUST9_DIR / "feature_order.json"
THRESHOLDS_PATH = ROBUST9_DIR / "thresholds.json"

REQUIRED_FEATURES = [
    "sz_all_mean",
    "sz_cv",
    "sz_all_p25",
    "sz_all_median",
    "sz_all_p75",
    "sz_mean_max",
    "sz_mean_min",
    "sz_std_max",
    "sz_std_min",
]


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


class Robust9Engine:
    """Lazy-loaded singleton for the robust9_firewall ensemble."""

    _instance: Optional["Robust9Engine"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.loader_config: Dict[str, Any] = _read_json(LOADER_CONFIG_PATH)
        self.feature_order: List[str] = _read_json(FEATURE_ORDER_PATH)["feature_order"]
        self.thresholds: Dict[str, Any] = _read_json(THRESHOLDS_PATH)

        self.probability_column: str = self.loader_config.get("probability_column", "prob_iso")
        self.session_aggregation: str = self.loader_config.get("session_aggregation", "p80")
        self.session_grouping_column: str = self.loader_config.get(
            "session_grouping_column", "capture_id"
        )

        families = self.loader_config.get("model_files", {})
        self.models: Dict[str, List[Any]] = {}
        for family in ("xgb", "lgbm", "cat"):
            paths = families.get(family, [])
            self.models[family] = [joblib.load(BUNDLE_ROOT / p) for p in paths]

        cal = self.loader_config.get("calibrators", {})
        iso_path = cal.get("isotonic")
        platt_path = cal.get("platt")
        self.isotonic = joblib.load(BUNDLE_ROOT / iso_path) if iso_path else None
        self.platt = joblib.load(BUNDLE_ROOT / platt_path) if platt_path else None

    @classmethod
    def get(cls) -> "Robust9Engine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance


    @staticmethod
    def _proba(model: Any, X: np.ndarray) -> np.ndarray:
        """Return P(class=1) from a sklearn-like classifier."""
        proba = model.predict_proba(X)
        proba = np.asarray(proba)
        if proba.ndim == 1:
            return proba
        return proba[:, -1]

    def _ensemble_raw(self, X: np.ndarray) -> np.ndarray:
        """Average within each family, then average across families equally."""
        family_means: List[np.ndarray] = []
        for family in ("xgb", "lgbm", "cat"):
            members = self.models.get(family, [])
            if not members:
                continue
            stacked = np.vstack([self._proba(m, X) for m in members])
            family_means.append(stacked.mean(axis=0))
        if not family_means:
            raise RuntimeError("No models loaded for robust9_firewall.")
        return np.mean(np.vstack(family_means), axis=0)

    def _apply_calibration(self, raw: np.ndarray) -> np.ndarray:
        col = self.probability_column
        if col == "prob_iso" and self.isotonic is not None:
            return np.asarray(self.isotonic.transform(raw))
        if col == "prob_platt" and self.platt is not None:
            try:
                return self.platt.predict_proba(raw.reshape(-1, 1))[:, 1]
            except Exception:
                return np.asarray(self.platt.transform(raw))
        return raw

    @staticmethod
    def _aggregate(scores: np.ndarray, method: str) -> float:
        if len(scores) == 0:
            return 0.0
        if method == "p80":
            return float(np.percentile(scores, 80))
        if method == "mean":
            return float(np.mean(scores))
        if method == "max":
            return float(np.max(scores))
        return float(np.percentile(scores, 80))


    def score_dataframe(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, str]:
        """Score every flow in ``df`` and attach a per-flow probability column.

        Returns (df_with_scores, session_column_used).
        """
        missing = [f for f in REQUIRED_FEATURES if f not in df.columns]
        if missing:
            raise ValueError(f"Missing required robust9 features: {missing}")

        X = df.loc[:, self.feature_order].to_numpy(dtype=float)
        raw = self._ensemble_raw(X)
        calibrated = self._apply_calibration(raw)

        out = df.copy()
        out["prob_raw"] = raw
        out[self.probability_column] = calibrated

        session_col = self.session_grouping_column
        if session_col not in out.columns:
            for alt in ("session_id", "capture_id"):
                if alt in out.columns:
                    session_col = alt
                    break
            else:
                out["_session"] = np.arange(len(out)).astype(str)
                session_col = "_session"
        return out, session_col

    def build_session_decisions(self, scored: pd.DataFrame, session_col: str) -> List[Dict[str, Any]]:
        sessions: List[Dict[str, Any]] = []
        prob_col = self.probability_column
        for sid, group in scored.groupby(session_col, sort=False):
            flow_scores = group[prob_col].to_numpy(dtype=float)
            session_score = self._aggregate(flow_scores, self.session_aggregation)
            action, strict_trig, bal_trig = decide_action(session_score, self.thresholds)
            sessions.append(
                {
                    "session_id": str(sid),
                    "n_flows": int(len(group)),
                    "flow_score_mean": float(np.mean(flow_scores)),
                    "flow_score_max": float(np.max(flow_scores)),
                    "session_score": float(session_score),
                    "aggregation": self.session_aggregation,
                    "strict_trigger": bool(strict_trig),
                    "balanced_trigger": bool(bal_trig),
                    "action": action,
                    "simulated": True,
                }
            )
        return sessions

    def run(self, df: pd.DataFrame) -> Dict[str, Any]:
        scored, session_col = self.score_dataframe(df)
        sessions = self.build_session_decisions(scored, session_col)
        counts = {"PASS": 0, "FLAG_REVIEW": 0, "BLOCK": 0}
        for s in sessions:
            counts[s["action"]] = counts.get(s["action"], 0) + 1
        return {
            "model_id": ROBUST9_MODEL_ID,
            "action_mode": "simulation",
            "production_readiness": bool(self.loader_config.get("production_readiness", False)),
            "probability_column": self.probability_column,
            "aggregation": self.session_aggregation,
            "thresholds": {
                "strict": float(self.thresholds.get("strict", {}).get("threshold", float("nan"))),
                "balanced": float(self.thresholds.get("balanced", {}).get("threshold", float("nan"))),
            },
            "total_flows": int(len(scored)),
            "total_sessions": int(len(sessions)),
            "counts": counts,
            "sessions": sessions,
            "warnings": [
                "Simulation only - no real packets are blocked.",
                "production_readiness=false; do not deploy as-is.",
            ],
        }

