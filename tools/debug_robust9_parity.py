"""Robust9 inference pipeline parity check.

Verifies that the runtime inference path (backend/app/robust9_inference.py)
matches what the notebook produced, by independently:

  1. Printing the runtime artifact metadata (model id, feature order,
     calibrator, threshold, aggregation, classes_ of each base learner).
  2. Running the engine on the bundled demo CSV and any user-supplied CSV.
  3. Logging for each row: raw ensemble proba, calibrated prob_iso, session
     p80 score, the threshold comparison, and the final action.
  4. Comparing label vs predicted action for sanity.

Run from project root:
  python tools/debug_robust9_parity.py
  python tools/debug_robust9_parity.py --csv captures\\my_eval.csv
  python tools/debug_robust9_parity.py --csv mycsv.csv --rows 5 --pick-vpn
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.robust9_inference import (  # noqa: E402
    ROBUST9_DIR,
    REQUIRED_FEATURES,
    Robust9Engine,
)
from app.registry_loader import BUNDLE_ROOT, DEMO_FLOWS_PATH  # noqa: E402


def banner(t: str) -> None:
    print()
    print("=" * 78)
    print(f"  {t}")
    print("=" * 78)


def dump_artifact_metadata(eng: Robust9Engine) -> None:
    banner("1. Runtime artifact metadata")
    print(f"  ROBUST9_DIR              = {ROBUST9_DIR}")
    print(f"  BUNDLE_ROOT              = {BUNDLE_ROOT}")
    print(f"  probability_column       = {eng.probability_column}")
    print(f"  session_aggregation      = {eng.session_aggregation}")
    print(f"  session_grouping_column  = {eng.session_grouping_column}")
    print(f"  feature_order            = {eng.feature_order}")
    print(f"  REQUIRED_FEATURES (code) = {REQUIRED_FEATURES}")
    if eng.feature_order != REQUIRED_FEATURES:
        print("  !! WARNING: feature_order.json and REQUIRED_FEATURES disagree.")

    print()
    print("  Base learners loaded:")
    for fam, models in eng.models.items():
        for i, m in enumerate(models):
            cls = getattr(m, "classes_", None)
            print(f"    {fam}[{i}]  type={type(m).__name__}  classes_={cls}")

    print()
    print(f"  isotonic = {type(eng.isotonic).__name__ if eng.isotonic is not None else None}")
    print(f"  platt    = {type(eng.platt).__name__    if eng.platt is not None    else None}")

    print()
    print("  Thresholds:")
    print(json.dumps(eng.thresholds, indent=2))

    # Model card / session metrics for cross-checking with notebook values.
    for name in ("model_card.json", "session_metrics.json", "policy_report.json"):
        p = ROBUST9_DIR / name
        if p.exists():
            print()
            print(f"--- {name} (head) ---")
            data = json.loads(p.read_text(encoding="utf-8"))
            # Print a compact selection
            keys_of_interest = (
                "model_id",
                "created_utc",
                "selected_probability_column",
                "selected_aggregation",
                "session_grouping_column",
                "production_readiness",
                "test_metrics",
                "n_test_sessions",
                "session_auc_test",
                "strict",
                "balanced",
            )
            subset = {k: data[k] for k in keys_of_interest if k in data}
            print(json.dumps(subset, indent=2)[:1200])


def per_row_trace(eng: Robust9Engine, df: pd.DataFrame, max_rows: int = 8) -> None:
    """Run the engine and print per-row raw vs calibrated probabilities."""
    banner("2. Per-flow trace (raw -> calibrated)")

    missing = [c for c in eng.feature_order if c not in df.columns]
    if missing:
        print(f"  CSV is missing required columns: {missing}")
        return

    X = df.loc[:, eng.feature_order].to_numpy(dtype=float)
    raw_per_family = {}
    for fam in ("xgb", "lgbm", "cat"):
        members = eng.models.get(fam, [])
        if not members:
            continue
        stacked = np.vstack([eng._proba(m, X) for m in members])
        raw_per_family[fam] = stacked.mean(axis=0)

    raw = np.mean(np.vstack(list(raw_per_family.values())), axis=0)
    iso = eng._apply_calibration(raw)

    head = df.head(max_rows).copy()
    head["raw_xgb"]  = raw_per_family.get("xgb", [np.nan]*len(df))[: len(head)]
    head["raw_lgbm"] = raw_per_family.get("lgbm", [np.nan]*len(df))[: len(head)]
    head["raw_cat"]  = raw_per_family.get("cat", [np.nan]*len(df))[: len(head)]
    head["prob_raw"] = raw[: len(head)]
    head["prob_iso"] = iso[: len(head)]

    show_cols = []
    for c in ("session_id", "capture_id", "flow_id", "dataset", "label"):
        if c in head.columns:
            show_cols.append(c)
    show_cols += ["raw_xgb", "raw_lgbm", "raw_cat", "prob_raw", "prob_iso"]
    with pd.option_context("display.max_columns", None, "display.width", 200,
                           "display.float_format", lambda v: f"{v:.4f}"):
        print(head[show_cols].to_string(index=False))


def session_decisions(eng: Robust9Engine, df: pd.DataFrame) -> None:
    banner("3. Session-level decisions (engine.run)")
    out = eng.run(df)
    print(f"  total_flows    = {out['total_flows']}")
    print(f"  total_sessions = {out['total_sessions']}")
    print(f"  counts         = {out['counts']}")
    print(f"  thresholds     = {out['thresholds']}")
    print()

    sessions = pd.DataFrame(out["sessions"])
    if "label" in df.columns and "session_id" in df.columns:
        # Aggregate label per session (majority label, or any 1 ==> 1).
        per_sess = (
            df.groupby("session_id")["label"].max().reset_index().rename(
                columns={"label": "session_label"}
            )
        )
        sessions = sessions.merge(per_sess, left_on="session_id", right_on="session_id", how="left")

    with pd.option_context("display.max_columns", None, "display.width", 220,
                           "display.float_format", lambda v: f"{v:.4f}"):
        print(sessions.to_string(index=False))

    # If we have labels, show the parity table.
    if "session_label" in sessions.columns:
        banner("4. Label vs predicted action")
        tbl = sessions.groupby(["session_label", "action"]).size().unstack(fill_value=0)
        print(tbl.to_string())
        thr = float(eng.thresholds.get("strict", {}).get("threshold", float("nan")))
        print()
        print(f"  strict threshold = {thr}")
        print(f"  prob col compared against threshold = {eng.probability_column} "
              f"(aggregated by {eng.session_aggregation})")
        # Highlight the rows that should be VPN (label=1) but are PASS.
        vpn = sessions[sessions.get("session_label") == 1]
        if len(vpn):
            print()
            print(f"  VPN sessions: {len(vpn)} total, "
                  f"BLOCK={int((vpn['action']=='BLOCK').sum())}, "
                  f"FLAG_REVIEW={int((vpn['action']=='FLAG_REVIEW').sum())}, "
                  f"PASS={int((vpn['action']=='PASS').sum())}")
            below = vpn[vpn["session_score"] < thr]
            if len(below):
                print(f"  -> VPN sessions BELOW threshold (PASSED incorrectly): {len(below)}")
                print(below[["session_id", "n_flows", "session_score", "action"]].to_string(index=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=str, default=None,
                    help="CSV to evaluate. Defaults to the bundled demo flows CSV.")
    ap.add_argument("--rows", type=int, default=8,
                    help="How many rows to show in the per-flow trace.")
    ap.add_argument("--pick-vpn", action="store_true",
                    help="If label column exists, show only label==1 rows in trace.")
    args = ap.parse_args()

    eng = Robust9Engine.get()
    dump_artifact_metadata(eng)

    csv_path = Path(args.csv) if args.csv else Path(DEMO_FLOWS_PATH)
    print()
    print(f"[*] Loading CSV: {csv_path}")
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"    rows={len(df)}  cols={len(df.columns)}")

    trace_df = df
    if args.pick_vpn and "label" in df.columns:
        trace_df = df[df["label"] == 1]
        if not len(trace_df):
            trace_df = df

    per_row_trace(eng, trace_df, max_rows=args.rows)
    session_decisions(eng, df)


if __name__ == "__main__":
    main()

