"""Score each capture-point CSV with unified_relative_shape_v2__lgbm and write report.

Read-only relative to model. No retraining. Uses the same RuntimeModelEngine as
the FastAPI backend, so the numbers match what /firewall/multimodel-demo would
return for each PCAP if streamed via pcap_to_live_stream.py.
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.registry_loader import EXECUTABLE_FIREWALL_MODEL_ID  # noqa: E402
from app.runtime_model_inference import get_engine  # noqa: E402

CAPTURES = ROOT / "captures"
OUT_DIR = ROOT / "artifacts" / "runtime_integration_thesis" / "thesis_exports"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SCENARIOS = [
    ("A. tcpdump -i any (broad)",
     "vm_openvpn_lab_split_any.pcap",
     "vm_openvpn_lab_split_any_features.csv"),
    ("B. tcpdump -i tun0 (inner tunnel only)",
     "vm_openvpn_lab_split_tun.pcap",
     "vm_openvpn_lab_split_tun_features.csv"),
    ("C. tcpdump udp port 1194 (outer encrypted OpenVPN transport only)",
     "vm_openvpn_lab_split_outer.pcap",
     "vm_openvpn_lab_split_outer_features.csv"),
]

ACTION_REVIEW = "FLAG_REVIEW"
ACTION_BLOCK = "SIMULATED_BLOCK"
ACTION_PASS = "PASS"


def pcap_size(name: str) -> int:
    p = CAPTURES / name
    return p.stat().st_size if p.exists() else 0


def stats(arr: np.ndarray) -> Dict[str, float]:
    if len(arr) == 0:
        return {k: 0.0 for k in ("min", "p25", "median", "mean", "p75", "max")}
    return {
        "min": float(arr.min()),
        "p25": float(np.percentile(arr, 25)),
        "median": float(np.percentile(arr, 50)),
        "mean": float(arr.mean()),
        "p75": float(np.percentile(arr, 75)),
        "max": float(arr.max()),
    }


def fmt(x: float) -> str:
    if abs(x) >= 0.01 or x == 0:
        return f"{x:.4f}"
    return f"{x:.3e}"


def main() -> None:
    print(f"[*] Loading model: {EXECUTABLE_FIREWALL_MODEL_ID}")
    engine = get_engine(EXECUTABLE_FIREWALL_MODEL_ID)
    thresholds = engine.thresholds
    # Locate numeric thresholds (nested or flat).
    review_thr = (
        thresholds.get("balanced", {}).get("threshold")
        if isinstance(thresholds.get("balanced"), dict)
        else thresholds.get("review_threshold")
    )
    block_thr = (
        thresholds.get("strict", {}).get("threshold")
        if isinstance(thresholds.get("strict"), dict)
        else thresholds.get("block_threshold")
    )
    if review_thr is None:
        review_thr = thresholds.get("review_threshold", 0.5)
    if block_thr is None:
        block_thr = thresholds.get("block_threshold", 0.9)
    review_thr = float(review_thr)
    block_thr = float(block_thr)
    print(f"[*] Thresholds: review={review_thr}, block={block_thr}")

    md: List[str] = []
    md.append("# OpenVPN Capture-Interface Comparison")
    md.append("")
    md.append(f"**Generated:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    md.append(f"**Active runtime model:** `{EXECUTABLE_FIREWALL_MODEL_ID}`")
    md.append(f"**Feature schema:** `unified_relative_shape_v2` (12 features)")
    md.append(f"**Thresholds:** review = {review_thr}, block = {block_thr}  ")
    md.append(f"**Aggregation:** {engine.session_aggregation} per `{engine.session_grouping_column}`")
    md.append("")
    md.append("## Method")
    md.append("")
    md.append(
        "The original `vm_openvpn_lab_auto.pcap` was captured inside the client VM with "
        "`sudo tcpdump -i any -w …`. Because re-running the two-VM lab from this host "
        "environment is not possible, the same source PCAP was split offline into three "
        "subsets that mimic the packets a real interface-restricted `tcpdump` would have "
        "recorded. This is a fair comparison for the unified model because the unified "
        "extractor is interface-agnostic: it operates on the IP-layer packets, not on the "
        "link-layer metadata. The three subsets are:"
    )
    md.append("")
    md.append("| Scenario | Filter applied | Equivalent live command |")
    md.append("|---|---|---|")
    md.append("| A | (none — full original PCAP) | `tcpdump -i any -w …` |")
    md.append("| B | only packets with both src and dst in `10.8.0.0/24` | `tcpdump -i tun0 -w …` |")
    md.append("| C | only packets with UDP/TCP port 1194 in the 5-tuple | `tcpdump -i ens3 udp port 1194 -w …` |")
    md.append("")
    md.append("Each subset PCAP was passed through `tools/pcap_to_live_stream.py "
              "--dry-run --out-csv …` to produce a 12-feature `unified_relative_shape_v2` CSV. "
              "Each CSV was then scored with the same `RuntimeModelEngine` instance the FastAPI "
              "backend uses (`get_engine('unified_relative_shape_v2__lgbm')`). No code paths "
              "differ from the production runtime path.")
    md.append("")
    md.append("## Schema validation")
    md.append("")
    md.append("| Scenario | PCAP bytes | CSV rows | All 12 features present | NaN | Inf |")
    md.append("|---|---:|---:|:---:|:---:|:---:|")
    csv_dfs = {}
    for label, pcap_name, csv_name in SCENARIOS:
        csv_path = CAPTURES / csv_name
        if not csv_path.exists():
            md.append(f"| {label} | — | — | ✗ (CSV missing) | — | — |")
            continue
        df = pd.read_csv(csv_path)
        feats = engine.feature_order
        present = all(f in df.columns for f in feats)
        nans = int(df[feats].isna().to_numpy().sum()) if present else -1
        infs = int(np.isinf(df[feats].to_numpy()).sum()) if present else -1
        md.append(
            f"| {label} | {pcap_size(pcap_name):,} | {len(df)} | "
            f"{'✓' if present else '✗'} | {nans} | {infs} |"
        )
        csv_dfs[label] = df
    md.append("")

    # Per-scenario scoring
    md.append("## Per-scenario scoring")
    md.append("")

    per_scn_summary = []
    for label, _pcap_name, _csv_name in SCENARIOS:
        if label not in csv_dfs:
            continue
        df = csv_dfs[label]
        scored, session_col, missing = engine.score_dataframe(df)
        md.append(f"### {label}")
        md.append("")
        if missing:
            md.append(f"Missing features: {missing}. Scenario skipped.")
            md.append("")
            continue
        # Flow-level scores
        prob_col = engine.probability_column
        if prob_col not in scored.columns:
            prob_col = "prob_raw"
        scores = scored[prob_col].to_numpy(dtype=float)
        s = stats(scores)
        # Per-flow actions
        actions = np.where(
            scores >= block_thr, ACTION_BLOCK,
            np.where(scores >= review_thr, ACTION_REVIEW, ACTION_PASS),
        )
        n_pass = int((actions == ACTION_PASS).sum())
        n_review = int((actions == ACTION_REVIEW).sum())
        n_block = int((actions == ACTION_BLOCK).sum())
        # Per-session aggregation (mean as per the loader config — confirmed below)
        sess_groups = scored.groupby(session_col)[prob_col].mean() if session_col else pd.Series(scores)
        sess_scores = sess_groups.to_numpy()
        sess_actions = np.where(
            sess_scores >= block_thr, ACTION_BLOCK,
            np.where(sess_scores >= review_thr, ACTION_REVIEW, ACTION_PASS),
        )
        s_pass = int((sess_actions == ACTION_PASS).sum())
        s_review = int((sess_actions == ACTION_REVIEW).sum())
        s_block = int((sess_actions == ACTION_BLOCK).sum())

        md.append(f"- **Flows scored:** {len(scores)}")
        md.append(f"- **Sessions (`{session_col}`):** {len(sess_scores)}")
        md.append(f"- **Probability column used:** `{prob_col}`")
        md.append("")
        md.append("**Flow score distribution:**  ")
        md.append(
            f"min = {fmt(s['min'])} · p25 = {fmt(s['p25'])} · median = {fmt(s['median'])} · "
            f"mean = {fmt(s['mean'])} · p75 = {fmt(s['p75'])} · max = {fmt(s['max'])}"
        )
        md.append("")
        md.append("**Flow-level action counts:**  ")
        md.append(f"PASS = {n_pass} · FLAG_REVIEW = {n_review} · SIMULATED_BLOCK = {n_block}")
        md.append("")
        md.append("**Session-level action counts (aggregation = mean):**  ")
        md.append(f"PASS = {s_pass} · FLAG_REVIEW = {s_review} · SIMULATED_BLOCK = {s_block}")
        md.append("")
        # Top flows by score
        df_top = scored.copy()
        df_top["_action"] = actions
        df_top["_score"] = scores
        cols_keep = [c for c in ["src_ip", "dst_ip", "protocol", "dst_port"] if c in df_top.columns]
        top_by_score = df_top.sort_values("_score", ascending=False).head(5)
        md.append("**Top 5 flows by score:**")
        md.append("")
        md.append("| score | action | " + " | ".join(cols_keep) + " |")
        md.append("|---:|---|" + "|".join(["---"] * len(cols_keep)) + "|")
        for _, row in top_by_score.iterrows():
            md.append(
                f"| {fmt(row['_score'])} | `{row['_action']}` | "
                + " | ".join(str(row[c]) for c in cols_keep) + " |"
            )
        md.append("")
        per_scn_summary.append({
            "label": label, "flows": len(scores), "sessions": len(sess_scores),
            "score_max": s["max"], "score_mean": s["mean"], "score_median": s["median"],
            "flow_pass": n_pass, "flow_review": n_review, "flow_block": n_block,
            "sess_pass": s_pass, "sess_review": s_review, "sess_block": s_block,
        })

    # Comparison
    md.append("## Cross-scenario comparison")
    md.append("")
    md.append(
        "| Scenario | Flows | Sessions | Score median | Score mean | Score max | "
        "Flow PASS | Flow REVIEW | Flow BLOCK | Sess PASS | Sess REVIEW | Sess BLOCK |"
    )
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in per_scn_summary:
        md.append(
            f"| {row['label']} | {row['flows']} | {row['sessions']} | "
            f"{fmt(row['score_median'])} | {fmt(row['score_mean'])} | {fmt(row['score_max'])} | "
            f"{row['flow_pass']} | {row['flow_review']} | {row['flow_block']} | "
            f"{row['sess_pass']} | {row['sess_review']} | {row['sess_block']} |"
        )
    md.append("")

    # Verdict & thesis recommendation are produced separately below

    out_md = OUT_DIR / "openvpn_capture_interface_comparison.md"
    out_md.write_text("\n".join(md), encoding="utf-8")
    print(f"[*] Wrote {out_md}")

    # Also dump the summary for the assistant to consume
    for row in per_scn_summary:
        print(row)


if __name__ == "__main__":
    main()

