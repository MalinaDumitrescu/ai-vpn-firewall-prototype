#!/usr/bin/env python3
"""
audit_live_pcap_full_canonical.py
==================================
Audits the latest live-generated PCAP feature CSV against the
full_canonical__lgbm feature_order.json schema.

Usage:
    python tools/audit_live_pcap_full_canonical.py

Optionally specify a CSV explicitly:
    python tools/audit_live_pcap_full_canonical.py --csv captures/vm_basic_benign_features.csv

Saves audit report to:
    artifacts/runtime_schema_audit/live_pcap_full_canonical_audit.md

IMPORTANT:
    This script audits the live-generated PCAP feature CSV — NOT demo_flows_full_canonical.csv.
    demo_flows_full_canonical.csv is a reference schema only, not evidence that the live
    pipeline works.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
except Exception:
    pass

try:
    import pandas as pd
except ImportError:
    print("[ERROR] Missing dependency: pandas. Install: pip install pandas")
    sys.exit(1)


_THIS_FILE   = Path(__file__).resolve()
PROJECT_ROOT = _THIS_FILE.parent.parent
CAPTURES_DIR = PROJECT_ROOT / "captures"
BUNDLE_ROOT  = PROJECT_ROOT / "backend" / "runtime_bundle" / "app_runtime_bundle"
FEATURE_ORDER_PATH = BUNDLE_ROOT / "runtime_models" / "full_canonical__lgbm" / "feature_order.json"
REPORT_DIR   = PROJECT_ROOT / "artifacts" / "runtime_schema_audit"

META_COLS = {"session_id", "flow_id", "capture_id", "dataset", "label",
             "timestamp", "src_ip", "dst_ip", "protocol", "dst_port", "scenario"}

CANDIDATE_CSVS = [
    "vm_basic_benign_features.csv",
    "vm_vpnlike_features.csv",
    "vm_warp_features.csv",
    "vm_openvpn_lab_auto_features.csv",
    "vm_openvpn_lab_varied_sample_features.csv",
    "vm_openvpn_lab_sample_features.csv",
    "vm_openvpn_lab_features.csv",
]

ROBUST9_FEATURES = {
    "sz_all_mean", "sz_cv", "sz_all_p25", "sz_all_median",
    "sz_all_p75", "sz_mean_max", "sz_mean_min", "sz_std_max", "sz_std_min",
}


def _load_feature_order() -> List[str]:
    if not FEATURE_ORDER_PATH.exists():
        print(f"[ERROR] feature_order.json not found: {FEATURE_ORDER_PATH}")
        sys.exit(1)
    with FEATURE_ORDER_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)["feature_order"]


def _find_latest_live_csv(explicit: Optional[str]) -> Path:
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        if not p.exists():
            print(f"[ERROR] Specified CSV not found: {p}")
            sys.exit(1)
        return p

    found = []
    for name in CANDIDATE_CSVS:
        p = CAPTURES_DIR / name
        if p.exists():
            found.append(p)

    if not found:
        found = sorted(CAPTURES_DIR.glob("*_features.csv"),
                       key=lambda f: f.stat().st_mtime, reverse=True)

    if not found:
        print(f"[ERROR] No *_features.csv files found in {CAPTURES_DIR}")
        print("       Run one of the VM PCAP demos first, or pass --csv explicitly.")
        sys.exit(1)

    best = max(found, key=lambda f: f.stat().st_mtime)
    return best


def _check_robust9_only(columns: List[str]) -> bool:
    """Return True if the CSV contains only the 9 legacy robust9 features (no IAT etc.)."""
    model_cols = [c for c in columns if c not in META_COLS]
    return set(model_cols) == ROBUST9_FEATURES or set(model_cols) <= ROBUST9_FEATURES


def _numeric_stats(df: pd.DataFrame, feat: str) -> Dict[str, Any]:
    if feat not in df.columns:
        return {"present": False}
    col = pd.to_numeric(df[feat], errors="coerce")
    nan_count = int(col.isna().sum())
    inf_count = int((col == float("inf")).sum() + (col == float("-inf")).sum())
    valid = col.dropna()
    valid = valid[~valid.isin([float("inf"), float("-inf")])]
    return {
        "present":   True,
        "nan_count": nan_count,
        "inf_count": inf_count,
        "min":       round(float(valid.min()), 6) if len(valid) else None,
        "mean":      round(float(valid.mean()), 6) if len(valid) else None,
        "max":       round(float(valid.max()), 6) if len(valid) else None,
    }


def _dry_inference(df: pd.DataFrame, feature_order: List[str]) -> Tuple[bool, str]:
    """Try a dry inference: select features, convert to float, check shape."""
    missing = [f for f in feature_order if f not in df.columns]
    if missing:
        return False, f"Missing {len(missing)} feature(s): {missing[:8]}{'...' if len(missing) > 8 else ''}"
    try:
        X = df[feature_order].to_numpy(dtype=float)
        if X.shape[1] != len(feature_order):
            return False, f"Shape mismatch: got {X.shape[1]} columns, expected {len(feature_order)}"
        nan_count = int(pd.isna(X).sum())
        if nan_count > 0:
            return False, f"NaN values in feature matrix: {nan_count}"
        return True, f"OK — shape {X.shape}, all finite"
    except Exception as exc:
        return False, f"Exception during dry inference: {exc}"


def run_audit(csv_path: Path, feature_order: List[str]) -> Dict[str, Any]:
    """Run the full schema audit and return a structured result dict."""
    print(f"[*] Auditing CSV: {csv_path}")
    df = pd.read_csv(csv_path)

    columns = list(df.columns)
    n_rows, n_cols = df.shape

    generated_model_cols = [c for c in columns if c not in META_COLS]
    generated_meta_cols  = [c for c in columns if c in META_COLS]

    required_set  = set(feature_order)
    generated_set = set(generated_model_cols)

    missing = [f for f in feature_order if f not in generated_set]
    extra   = sorted(generated_set - required_set)

    is_robust9_only = _check_robust9_only(columns)

    feat_stats: Dict[str, Any] = {}
    for feat in feature_order:
        feat_stats[feat] = _numeric_stats(df, feat)

    total_nan = sum(v["nan_count"] for v in feat_stats.values() if v.get("present"))
    total_inf = sum(v["inf_count"] for v in feat_stats.values() if v.get("present"))

    dry_ok, dry_msg = _dry_inference(df, feature_order)

    if is_robust9_only and missing:
        verdict = "D — Live PCAP pipeline still uses robust9/legacy assumptions. Fix required."
        verdict_code = "D"
    elif missing:
        verdict = f"C — Live PCAP pipeline not compatible. {len(missing)} feature(s) missing: {missing}"
        verdict_code = "C"
    elif total_nan > 0 or total_inf > 0:
        verdict = f"B — Schema-compatible but {total_nan} NaN / {total_inf} Inf values found. Review feature formulas."
        verdict_code = "B"
    elif not dry_ok:
        verdict = f"B — Schema-compatible but dry inference failed: {dry_msg}"
        verdict_code = "B"
    else:
        verdict = "A — Live PCAP pipeline fully compatible with full_canonical__lgbm."
        verdict_code = "A"

    return {
        "csv_path":              str(csv_path.resolve()),
        "n_rows":                n_rows,
        "n_cols":                n_cols,
        "generated_columns":     columns,
        "generated_model_cols":  generated_model_cols,
        "generated_meta_cols":   generated_meta_cols,
        "required_features":     feature_order,
        "missing_features":      missing,
        "extra_features":        extra,
        "is_robust9_only":       is_robust9_only,
        "total_nan_in_features": total_nan,
        "total_inf_in_features": total_inf,
        "feature_stats":         feat_stats,
        "dry_inference_ok":      dry_ok,
        "dry_inference_msg":     dry_msg,
        "verdict":               verdict,
        "verdict_code":          verdict_code,
    }


def _write_report(result: Dict[str, Any], report_path: Path) -> None:
    """Write a Markdown audit report."""
    ts = datetime.now(timezone.utc).isoformat()
    lines: List[str] = [
        "# Live PCAP Full-Canonical Audit Report",
        "",
        f"**Generated:** {ts}  ",
        f"**Model:** `full_canonical__lgbm`  ",
        f"**Feature schema:** `full_canonical_34` (34 features)  ",
        "",
        "---",
        "",
        "## Input",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Generated CSV path | `{result['csv_path']}` |",
        f"| Row count | {result['n_rows']} |",
        f"| Column count | {result['n_cols']} |",
        f"| Model columns found | {len(result['generated_model_cols'])} |",
        f"| Metadata columns found | {len(result['generated_meta_cols'])} |",
        "",
        "---",
        "",
        "## Schema Comparison",
        "",
        f"| | |",
        f"|--|--|",
        f"| Required features | {len(result['required_features'])} |",
        f"| Present features | {len(result['required_features']) - len(result['missing_features'])} |",
        f"| Missing features | **{len(result['missing_features'])}** |",
        f"| Extra (non-model) columns | {len(result['extra_features'])} |",
        f"| Is robust9-only schema | {'**YES — legacy pipeline**' if result['is_robust9_only'] else 'No'} |",
        "",
    ]

    if result["missing_features"]:
        lines += [
            "### Missing Features",
            "",
            "```",
        ]
        for f in result["missing_features"]:
            lines.append(f"  {f}")
        lines += ["```", ""]

    if result["extra_features"]:
        lines += [
            "### Extra Columns (not model features)",
            "",
            "```",
        ]
        for f in result["extra_features"]:
            lines.append(f"  {f}")
        lines += ["```", ""]

    lines += [
        "---",
        "",
        "## Numeric Validity",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total NaN in features | {result['total_nan_in_features']} |",
        f"| Total Inf in features | {result['total_inf_in_features']} |",
        "",
        "### Feature Statistics (min / mean / max)",
        "",
        "| Feature | Present | NaN | Inf | Min | Mean | Max |",
        "|---------|---------|-----|-----|-----|------|-----|",
    ]
    for feat in result["required_features"]:
        s = result["feature_stats"].get(feat, {})
        if not s.get("present"):
            lines.append(f"| `{feat}` | ❌ | — | — | — | — | — |")
        else:
            lines.append(
                f"| `{feat}` | ✓ | {s['nan_count']} | {s['inf_count']} "
                f"| {s['min']} | {s['mean']} | {s['max']} |"
            )

    lines += [
        "",
        "---",
        "",
        "## Dry Inference",
        "",
        f"| Result | Details |",
        f"|--------|---------|",
        f"| Dry inference | {'✓ PASSED' if result['dry_inference_ok'] else '❌ FAILED'} |",
        f"| Message | {result['dry_inference_msg']} |",
        "",
        "---",
        "",
        "## Verdict",
        "",
        f"**{result['verdict']}**",
        "",
        "| Code | Meaning |",
        "|------|---------|",
        "| A | Fully compatible with full_canonical__lgbm |",
        "| B | Schema-compatible but feature definitions may differ from training; document risks |",
        "| C | Not compatible; missing features listed, fix required |",
        "| D | Still uses robust9/legacy assumptions |",
        "",
        "---",
        "",
        "## Notes",
        "",
        "- `demo_flows_full_canonical.csv` is a **reference schema only** and was NOT used as evidence here.",
        "- The audited CSV was generated from a real PCAP capture (or the most recently modified `*_features.csv`).",
        "- Packet size in the extractor uses **IP total length** (`ip_layer.len`), not Ethernet frame length.",
        "- IAT features require ≥ 2 packets per flow; single-packet flows produce IAT = 0.",
        "",
    ]

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"[*] Report saved to: {report_path.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the latest live-generated PCAP feature CSV against "
            "full_canonical__lgbm/feature_order.json.\n"
            "NOTE: Does NOT use demo_flows_full_canonical.csv."
        )
    )
    parser.add_argument(
        "--csv",
        default=None,
        metavar="PATH",
        help="Explicit path to a live-generated *_features.csv (default: auto-detect latest).",
    )
    parser.add_argument(
        "--report",
        default=str(REPORT_DIR / "live_pcap_full_canonical_audit.md"),
        metavar="PATH",
        help="Output path for the Markdown report.",
    )
    args = parser.parse_args()

    feature_order = _load_feature_order()
    print(f"[*] Loaded feature_order.json: {len(feature_order)} features")
    print(f"[*] Model: full_canonical__lgbm")

    csv_path = _find_latest_live_csv(args.csv)
    print(f"[*] Target CSV (live-generated): {csv_path}")
    print(f"    (This is NOT demo_flows_full_canonical.csv)")

    result = run_audit(csv_path, feature_order)

    print()
    print("=" * 65)
    print("  AUDIT SUMMARY")
    print("=" * 65)
    print(f"  CSV path          : {result['csv_path']}")
    print(f"  Rows              : {result['n_rows']}")
    print(f"  Columns           : {result['n_cols']}")
    print(f"  Required features : {len(result['required_features'])}")
    print(f"  Missing features  : {len(result['missing_features'])}")
    if result["missing_features"]:
        for f in result["missing_features"][:10]:
            print(f"    - {f}")
        if len(result["missing_features"]) > 10:
            print(f"    ... and {len(result['missing_features']) - 10} more")
    print(f"  Is robust9-only   : {result['is_robust9_only']}")
    print(f"  NaN in features   : {result['total_nan_in_features']}")
    print(f"  Inf in features   : {result['total_inf_in_features']}")
    print(f"  Dry inference     : {'PASSED' if result['dry_inference_ok'] else 'FAILED'}")
    print(f"  Dry msg           : {result['dry_inference_msg']}")
    print()
    print(f"  VERDICT [{result['verdict_code']}]: {result['verdict']}")
    print("=" * 65)

    report_path = Path(args.report)
    _write_report(result, report_path)

    if result["verdict_code"] in ("C", "D"):
        sys.exit(1)


if __name__ == "__main__":
    main()

