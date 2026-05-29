"""Live replay simulation service — CSV-row-based only.

Consumes a user-uploaded flow-feature CSV and replays rows in batches,
labelling sessions with robust9_firewall in simulation mode.

NOTE: Live replay uses the legacy robust9_firewall ensemble (9 sz_* features)
for feature-set compatibility with PCAP-derived CSV uploads. The recommended
default firewall model is full_canonical__lgbm (34 features), available via
/firewall/demo and the multi-model endpoints.

SAFETY CONSTRAINTS (enforced in this module):
  - No packet capture.
  - No shell commands.
  - No OS firewall modification.
  - All decisions are simulated=True, action_mode="simulation".
  - Only robust9_firewall is used for replay inference.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import io
import pandas as pd

from .robust9_inference import REQUIRED_FEATURES, Robust9Engine
from .policy_service import decide_action

# ─── constants ────────────────────────────────────────────────────────────────

MODEL_ID       = "robust9_firewall"
ACTION_MODE    = "simulation"
MAX_EVENTS     = 200        # ring buffer limit

OPTIONAL_COLS  = [
    "flow_id", "timestamp", "src_ip", "dst_ip",
    "protocol", "dst_port", "scenario", "dataset", "label",
]

LABEL_MAP = {
    "PASS":        "BENIGN_LIKE",
    "FLAG_REVIEW": "FLAGGED_FOR_REVIEW",
    "BLOCK":       "VPN_LIKE_SIMULATED_BLOCK",
}

TEMPLATE_HEADER = (
    "session_id,flow_id,timestamp,src_ip,dst_ip,protocol,dst_port,scenario,"
    "sz_all_mean,sz_cv,sz_all_p25,sz_all_median,sz_all_p75,"
    "sz_mean_max,sz_mean_min,sz_std_max,sz_std_min"
)

WARNINGS = [
    "Simulation only — no real packets are blocked.",
    "Live replay consumes uploaded flow-feature CSV rows, not raw packets.",
    "robust9_firewall (legacy baseline) is used for replay; full_canonical__lgbm is the recommended model.",
]

# ─── state ────────────────────────────────────────────────────────────────────

class LiveReplayState:
    """Single shared in-memory replay state (one active replay at a time)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset_internal()

    # ------------------------------------------------------------------ reset

    def _reset_internal(self) -> None:
        """Called inside lock or during __init__."""
        self.loaded: bool                     = False
        self.running: bool                    = False
        self.finished: bool                   = False
        self.mode: str                        = "uploaded_csv_replay"
        self.model_id: str                    = MODEL_ID
        self.uploaded_filename: str           = ""
        self.total_rows: int                  = 0
        self.replay_pointer: int              = 0
        self.batch_size_default: int          = 5
        self.started_at: Optional[str]        = None
        self.updated_at: Optional[str]        = None
        self.total_batches_processed: int     = 0
        self.total_flows_processed: int       = 0
        self.total_sessions_seen: int         = 0
        self.latest_counts: Dict[str,int]     = {"PASS": 0, "FLAG_REVIEW": 0, "BLOCK": 0}
        self.recent_events: List[Dict]        = []
        self.active_sessions: Dict[str, Any]  = {}
        # Raw data storage.
        self._all_rows: Optional[pd.DataFrame]      = None
        self._processed_rows: Optional[pd.DataFrame] = None
        self._optional_cols_present: List[str]       = []

    def reset(self) -> None:
        with self._lock:
            self._reset_internal()

    # ------------------------------------------------------------------ load

    def load_csv(self, raw_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Parse, validate, and store uploaded CSV. Returns metadata."""
        try:
            df = pd.read_csv(io.BytesIO(raw_bytes))
        except Exception as exc:
            raise ValueError(f"Cannot parse CSV: {exc}") from exc

        missing = [c for c in REQUIRED_FEATURES if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        if "session_id" not in df.columns:
            raise ValueError("Missing required column: session_id")

        optional_present = [c for c in OPTIONAL_COLS if c in df.columns]
        detected_sessions = int(df["session_id"].nunique())

        with self._lock:
            self._reset_internal()
            self.loaded            = True
            self.running           = False
            self.finished          = False
            self.uploaded_filename = filename
            self.total_rows        = len(df)
            self._all_rows         = df
            self._processed_rows   = pd.DataFrame(columns=df.columns)
            self._optional_cols_present = optional_present
            self.updated_at        = _now()

        return {
            "loaded": True,
            "uploaded_filename": filename,
            "total_rows": len(df),
            "detected_sessions": detected_sessions,
            "required_columns_present": True,
            "optional_columns_detected": optional_present,
            "message": (
                f"Loaded {len(df)} rows across {detected_sessions} sessions. "
                "Call /firewall/live-replay/step to begin replay."
            ),
        }

    # ------------------------------------------------------------------ step

    def step(self, batch_size: int = 5) -> Dict[str, Any]:
        """Advance the replay pointer by batch_size rows and recompute state."""
        with self._lock:
            if not self.loaded or self._all_rows is None:
                raise ValueError("No CSV loaded. POST to /firewall/live-replay/upload first.")

            if self.finished:
                return self._snapshot()

            # Mark running on first step.
            if not self.running:
                self.running    = True
                self.started_at = _now()

            start = self.replay_pointer
            end   = min(start + batch_size, self.total_rows)
            batch = self._all_rows.iloc[start:end].copy()

            if len(batch) == 0:
                self.running  = False
                self.finished = True
                self.updated_at = _now()
                return self._snapshot()

            # Append batch to processed rows.
            self._processed_rows = pd.concat(
                [self._processed_rows, batch], ignore_index=True
            )
            self.replay_pointer              = end
            self.total_batches_processed    += 1
            self.total_flows_processed      += len(batch)

            # Recompute full decision state on all processed rows.
            self._recompute_sessions(batch_index=self.total_batches_processed)

            if self.replay_pointer >= self.total_rows:
                self.running  = False
                self.finished = True

            self.updated_at = _now()
            return self._snapshot()

    # ------------------------------------------------------------------ score

    def _recompute_sessions(self, batch_index: int) -> None:
        """Score all processed rows and update active_sessions + recent_events.

        Called inside lock.
        """
        engine = Robust9Engine.get()
        df     = self._processed_rows

        # Score flows.
        feature_cols = [c for c in engine.feature_order if c in df.columns]
        try:
            X      = df[feature_cols].to_numpy(dtype=float)
            raw    = engine._ensemble_raw(X)
            cal    = engine._apply_calibration(raw)
            prob   = cal
        except Exception:
            return

        df = df.copy()
        df["_prob"] = prob
        df["_raw"]  = raw

        # Determine grouping column.
        session_col = "session_id"

        new_sessions: Dict[str, Any] = {}
        counts: Dict[str, int]       = {"PASS": 0, "FLAG_REVIEW": 0, "BLOCK": 0}
        new_events: List[Dict]        = []

        for sid, grp in df.groupby(session_col, sort=False):
            scores       = grp["_prob"].to_numpy()
            sess_score   = engine._aggregate(scores, engine.session_aggregation)
            action, strict_trig, bal_trig = decide_action(
                sess_score, engine.thresholds
            )
            label = LABEL_MAP.get(action, action)
            counts[action] = counts.get(action, 0) + 1

            session_entry = {
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
            }
            new_sessions[str(sid)] = session_entry

            # One event per (session × batch) that touches this session.
            # Only emit if this session appears in the current batch.
            last_row   = grp.iloc[-1]
            event_time = _now()
            event      = {
                "event_time":  event_time,
                "batch_index": batch_index,
                "session_id":  str(sid),
                "session_score":    round(float(sess_score), 4),
                "strict_trigger":   bool(strict_trig),
                "balanced_trigger": bool(bal_trig),
                "action":      action,
                "action_label": label,          # mapped label (BENIGN_LIKE etc.)
                "simulated":   True,
            }
            for opt in self._optional_cols_present:
                if opt == "label":
                    # Rename CSV ground-truth label to avoid collision with action_label.
                    val = last_row.get(opt)
                    if val is not None and str(val) not in ("nan", ""):
                        event["ground_truth_label"] = val
                    continue
                val = last_row.get(opt)
                if val is not None and str(val) not in ("nan", ""):
                    event[opt] = str(val) if not isinstance(val, (int, float)) else val
            new_events.append(event)

        # Update state.
        self.active_sessions     = new_sessions
        self.total_sessions_seen = len(new_sessions)
        self.latest_counts       = counts

        # Ring-buffer events (keep only the most recent MAX_EVENTS).
        self.recent_events = (self.recent_events + new_events)[-MAX_EVENTS:]

    # ------------------------------------------------------------------ snapshot

    def _snapshot(self) -> Dict[str, Any]:
        """Build the full state dict. Called inside lock."""
        total_rows    = self.total_rows or 1  # avoid div-by-zero
        progress_pct  = round(self.replay_pointer / total_rows * 100, 1)
        labelled: Dict[str, int] = {
            "BENIGN_LIKE":              0,
            "FLAGGED_FOR_REVIEW":       0,
            "VPN_LIKE_SIMULATED_BLOCK": 0,
        }
        for action, cnt in self.latest_counts.items():
            lbl = LABEL_MAP.get(action, action)
            labelled[lbl] = labelled.get(lbl, 0) + cnt

        return {
            "loaded":                   self.loaded,
            "running":                  self.running,
            "finished":                 self.finished,
            "model_id":                 self.model_id,
            "action_mode":              ACTION_MODE,
            "production_readiness":     False,
            "uploaded_filename":        self.uploaded_filename,
            "total_rows":               self.total_rows,
            "replay_pointer":           self.replay_pointer,
            "progress_percent":         progress_pct,
            "total_batches_processed":  self.total_batches_processed,
            "total_flows_processed":    self.total_flows_processed,
            "total_sessions_seen":      self.total_sessions_seen,
            "counts":                   dict(self.latest_counts),
            "labelled_counts":          labelled,
            "active_sessions":          list(self.active_sessions.values()),
            "recent_events":            list(self.recent_events),
            "warnings":                 WARNINGS,
            "started_at":               self.started_at,
            "updated_at":               self.updated_at,
        }

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return self._snapshot()


# ─── module-level singleton ───────────────────────────────────────────────────

_replay_state = LiveReplayState()


def get_replay_state() -> LiveReplayState:
    return _replay_state


# ─── helpers ─────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

