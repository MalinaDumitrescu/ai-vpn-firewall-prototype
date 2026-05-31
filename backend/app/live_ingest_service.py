"""Live ingest service for PCAP-derived flow batches.

Receives batches of unified_relative_shape_v2 flow rows posted by
tools/pcap_to_live_stream.py, runs unified_relative_shape_v2__lgbm inference,
and maintains a rolling session state for the frontend Live VM Monitor.

Feature schema: unified_relative_shape_v2__lgbm/feature_order.json (12 features)
Feature family: unified_relative_shape_v2
Packet size: IP total length (ip.len)
IAT units: seconds

SAFETY CONSTRAINTS (enforced in this module):
  - No packet capture.
  - No shell commands.
  - No OS firewall modification.
  - All decisions are simulated=True, action_mode="simulation".
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from .runtime_model_inference import get_engine, _aggregate as _agg_fn
from .policy_service import decide_action
from .registry_loader import RUNTIME_MODELS_DIR

# ─── constants ────────────────────────────────────────────────────────────────

MODEL_ID    = "unified_relative_shape_v2__lgbm"
FEATURE_SCHEMA = "unified_relative_shape_v2"
ACTION_MODE = "simulation"
MAX_EVENTS  = 200   # ring-buffer limit

LABEL_MAP = {
    "PASS":        "BENIGN_LIKE",
    "FLAG_REVIEW": "FLAGGED_FOR_REVIEW",
    "BLOCK":       "VPN_LIKE_SIMULATED_BLOCK",
}

OPTIONAL_META_COLS = [
    "flow_id", "timestamp", "src_ip", "dst_ip",
    "protocol", "dst_port", "scenario",
]

WARNINGS = [
    "Simulation only — no real packets are blocked.",
    "Live ingest consumes PCAP-derived flow features, not raw packets.",
    "unified_relative_shape_v2__lgbm is used for inference.",
    "Feature schema: unified_relative_shape_v2 (12 features). Packet size: IP total length (ip.len). IAT: seconds.",
]


def _load_feature_order() -> List[str]:
    """Load the canonical feature order from unified_relative_shape_v2__lgbm/feature_order.json."""
    path = RUNTIME_MODELS_DIR / MODEL_ID / "feature_order.json"
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            # feature_order.json uses "features" key for unified model
            return data.get("features") or data.get("feature_order") or []
    except Exception:
        # Fallback — hard-coded from unified_relative_shape_v2 feature family
        return [
            "sz_cv", "sz_iqr", "sz_qratio", "sz_median_to_mean",
            "sz_p25_median_ratio", "sz_p75_median_ratio", "sz_iqr_norm_median",
            "iat_cv", "iat_iqr",
            "direction_balance_bytes", "direction_balance_packets", "dispersion_symmetry",
        ]


REQUIRED_FEATURES: List[str] = _load_feature_order()


# ─── state ────────────────────────────────────────────────────────────────────

class LiveIngestState:
    """Singleton in-memory state for the /firewall/live-ingest endpoint."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset_internal()

    # ── reset ─────────────────────────────────────────────────────────────

    def _reset_internal(self) -> None:
        self.total_batches:  int              = 0
        self.total_flows:    int              = 0
        self.latest_counts:  Dict[str, int]   = {"PASS": 0, "FLAG_REVIEW": 0, "BLOCK": 0}
        self.active_sessions: Dict[str, Any]  = {}
        self.recent_events:  List[Dict]       = []
        self._all_rows: Optional[pd.DataFrame] = None
        self.started_at:  Optional[str]       = None
        self.updated_at:  Optional[str]       = None

    def reset(self) -> None:
        with self._lock:
            self._reset_internal()

    # ── ingest ────────────────────────────────────────────────────────────

    def ingest_batch(
        self,
        source: str,
        batch_id: str,
        flows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Accept a batch of unified_relative_shape_v2 flow-feature dicts, score them, return summary."""
        if not flows:
            with self._lock:
                return self._build_response(batch_id, source, received=0)

        try:
            batch_df = pd.DataFrame(flows)
        except Exception as exc:
            raise ValueError(f"Cannot convert flows to DataFrame: {exc}") from exc

        # Validate required unified_relative_shape_v2 features
        missing = [c for c in REQUIRED_FEATURES if c not in batch_df.columns]
        if missing:
            raise ValueError(
                f"Live PCAP features are not valid for {MODEL_ID}. "
                f"Batch '{batch_id}' is missing {len(missing)} required feature(s): {missing}. "
                f"Ensure pcap_to_live_stream.py uses --model-id {MODEL_ID} (unified_relative_shape_v2 schema)."
            )

        with self._lock:
            if self.started_at is None:
                self.started_at = _now()

            # Accumulate rows
            if self._all_rows is None:
                self._all_rows = batch_df.copy()
            else:
                self._all_rows = pd.concat(
                    [self._all_rows, batch_df], ignore_index=True
                )

            self.total_batches += 1
            self.total_flows   += len(flows)

            # Score and update session state
            self._recompute_sessions(batch_df, batch_index=self.total_batches)
            self.updated_at = _now()

            return self._build_response(batch_id, source, received=len(flows))

    # ── scoring ───────────────────────────────────────────────────────────

    def _recompute_sessions(
        self,
        new_batch: pd.DataFrame,
        batch_index: int,
    ) -> None:
        """Score the accumulated dataset; update active_sessions and events.

        Called inside lock.
        """
        df = self._all_rows
        if df is None or len(df) == 0:
            return

        try:
            engine = get_engine(MODEL_ID)
        except Exception:
            return  # model not loaded yet; skip silently

        # Enforce feature order — use only the 34 required features
        feature_cols = [c for c in engine.feature_order if c in df.columns]
        if len(feature_cols) < len(engine.feature_order):
            return  # not enough features; skip

        try:
            X   = df[feature_cols].to_numpy(dtype=float)
            raw = engine._ensemble_raw(X)
            cal = engine._calibrate(raw)
        except Exception:
            return

        df = df.copy()
        df["_prob"] = cal
        df["_raw"]  = raw

        # Group by session_id if present, else treat each row as its own session
        session_col = "session_id" if "session_id" in df.columns else None

        counts: Dict[str, int]  = {"PASS": 0, "FLAG_REVIEW": 0, "BLOCK": 0}
        new_sessions: Dict[str, Any] = {}
        new_events:   List[Dict]     = []

        groups = (
            df.groupby(session_col, sort=False)
            if session_col
            else [(str(i), df.iloc[[i]]) for i in range(len(df))]
        )

        for sid, grp in groups:
            scores     = grp["_prob"].to_numpy()
            sess_score = _agg_fn(scores, engine.session_aggregation)
            action, strict_trig, bal_trig = decide_action(sess_score, engine.thresholds)
            label = LABEL_MAP.get(action, action)
            counts[action] = counts.get(action, 0) + 1

            session_entry: Dict[str, Any] = {
                "session_id":       str(sid),
                "n_flows":          int(len(grp)),
                "session_score":    round(float(sess_score), 4),
                "aggregation":      engine.session_aggregation,
                "strict_trigger":   bool(strict_trig),
                "balanced_trigger": bool(bal_trig),
                "action":           action,
                "label":            label,
                "simulated":        True,
                "action_mode":      ACTION_MODE,
                "model_id":         MODEL_ID,
                "feature_schema":   FEATURE_SCHEMA,
            }

            # Attach optional metadata from most-recent row in this session
            last_row = grp.iloc[-1]
            for col in OPTIONAL_META_COLS:
                if col in grp.columns:
                    val = last_row.get(col)
                    if val is not None and str(val) not in ("nan", ""):
                        session_entry[col] = (
                            str(val) if not isinstance(val, (int, float)) else val
                        )

            new_sessions[str(sid)] = session_entry

            # Emit one event per session per batch
            event: Dict[str, Any] = {
                "event_time":       _now(),
                "batch_index":      batch_index,
                "session_id":       str(sid),
                "session_score":    round(float(sess_score), 4),
                "strict_trigger":   bool(strict_trig),
                "balanced_trigger": bool(bal_trig),
                "action":           action,
                "action_label":     label,
                "simulated":        True,
                "model_id":         MODEL_ID,
            }
            for col in OPTIONAL_META_COLS:
                if col in grp.columns:
                    val = last_row.get(col)
                    if val is not None and str(val) not in ("nan", ""):
                        event[col] = (
                            str(val) if not isinstance(val, (int, float)) else val
                        )
            new_events.append(event)

        self.active_sessions = new_sessions
        self.latest_counts   = counts
        self.recent_events   = (self.recent_events + new_events)[-MAX_EVENTS:]

    # ── response builder ──────────────────────────────────────────────────

    def _build_response(
        self, batch_id: str, source: str, received: int
    ) -> Dict[str, Any]:
        """Build the API response dict. Called inside lock."""
        labelled: Dict[str, int] = {
            "BENIGN_LIKE":              0,
            "FLAGGED_FOR_REVIEW":       0,
            "VPN_LIKE_SIMULATED_BLOCK": 0,
        }
        for action, cnt in self.latest_counts.items():
            lbl = LABEL_MAP.get(action, action)
            labelled[lbl] = labelled.get(lbl, 0) + cnt

        return {
            "batch_id":          batch_id,
            "source":            source,
            "received_flows":    received,
            "total_batches":     self.total_batches,
            "total_flows":       self.total_flows,
            "total_sessions":    len(self.active_sessions),
            "counts":            dict(self.latest_counts),
            "labelled_counts":   labelled,
            "active_sessions":   list(self.active_sessions.values()),
            "recent_events":     list(self.recent_events[-20:]),  # last 20 for response
            "model_id":          MODEL_ID,
            "feature_schema":    FEATURE_SCHEMA,
            "feature_count":     len(REQUIRED_FEATURES),
            "recommended_model": MODEL_ID,
            "action_mode":       ACTION_MODE,
            "production_readiness": False,
            "warnings":          WARNINGS,
            "started_at":        self.started_at,
            "updated_at":        self.updated_at,
        }

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return self._build_response(
                batch_id="<state_query>",
                source="state",
                received=0,
            )


# ─── module-level singleton ───────────────────────────────────────────────────

_ingest_state = LiveIngestState()


def get_ingest_state() -> LiveIngestState:
    return _ingest_state


# ─── helpers ─────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

