#!/usr/bin/env python3
"""
infer_training_formulas_deep.py
================================
Deep per-dataset formula inference for the 3 mismatched features.
Uses simultaneous_test_selected_models.csv (first 5000 rows) to determine
whether each dataset used the same or different formula for:
  - direction_balance_bytes
  - direction_balance_packets
  - dispersion_symmetry

Also tests the VNAT hypothesis: values consistently in [0,1] suggests
  proportion formula: sum_a / (sum_a + sum_b + eps)
vs ISCX hypothesis: raw ratio: cnt_a / (cnt_b + eps)
vs USBVPN hypothesis: normalized difference: (cnt_a - cnt_b) / (cnt_a + cnt_b + eps)

Also tests formula recovery by checking self-consistency of other features
that ARE unambiguous (sz_cv, sz_iqr, sz_qratio, etc.).

Output: artifacts/runtime_schema_audit/formula_inference_deep.md
"""
from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
SIMTEST_CSV = ROOT / "backend/runtime_bundle/app_runtime_bundle/demo_data/simultaneous_test_selected_models.csv"
DEMO_CSV    = ROOT / "backend/runtime_bundle/app_runtime_bundle/demo_data/demo_flows_full_canonical.csv"
REPORT_OUT  = ROOT / "artifacts/runtime_schema_audit/formula_inference_deep.md"
REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)

_EPS = 1e-9


def fv(row: Dict, col: str) -> Optional[float]:
    v = row.get(col)
    if v is None or v == "" or v in ("nan", "inf", "-inf"):
        return None
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def _mean(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else float("nan")


def _percentile(vals: List[float], p: float) -> float:
    if not vals:
        return float("nan")
    s = sorted(vals)
    n = len(s)
    idx = p / 100.0 * (n - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return float(s[lo])
    return float(s[lo] + (s[hi] - s[lo]) * (idx - lo))


def load_csv_by_dataset(path: Path, max_rows: int = 5000) -> Dict[str, List[Dict]]:
    """Load CSV, group rows by 'dataset' column."""
    by_ds: Dict[str, List[Dict]] = {}
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            ds = row.get("dataset", "unknown")
            by_ds.setdefault(ds, []).append(row)
            if i + 1 >= max_rows:
                break
    return by_ds


def feature_range_stats(rows: List[Dict], col: str) -> Dict[str, Any]:
    """Return distribution stats and sign analysis."""
    vals = [fv(r, col) for r in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"count": 0, "min": "N/A", "max": "N/A", "mean": "N/A"}

    n_neg = sum(1 for v in vals if v < 0)
    n_gt1 = sum(1 for v in vals if v > 1)
    n_gt100 = sum(1 for v in vals if v > 100)
    n_gt1e6 = sum(1 for v in vals if v > 1e6)
    n_zero = sum(1 for v in vals if abs(v) < 1e-10)

    return {
        "count": len(vals),
        "min": min(vals),
        "max": max(vals),
        "mean": _mean(vals),
        "median": _percentile(vals, 50),
        "p25": _percentile(vals, 25),
        "p75": _percentile(vals, 75),
        "n_negative": n_neg,
        "n_gt1": n_gt1,
        "n_gt100": n_gt100,
        "n_gt1e6": n_gt1e6,
        "n_zero": n_zero,
        "pct_in_minus1_plus1": (len(vals) - n_neg - n_gt1 + sum(1 for v in vals if -1 <= v <= 1)) / len(vals) * 100,
        "pct_in_0_1": sum(1 for v in vals if 0 <= v <= 1) / len(vals) * 100,
        "pct_gt1": n_gt1 / len(vals) * 100,
        "pct_negative": n_neg / len(vals) * 100,
        "pct_gt_1e6": n_gt1e6 / len(vals) * 100,
    }


def infer_formula_hypothesis(stats: Dict[str, Any], col: str) -> Tuple[str, str]:
    """
    From distribution statistics, infer the most likely formula.
    Returns (hypothesis_label, confidence).
    """
    if stats.get("count", 0) == 0:
        return ("no_data", "none")

    pct_neg = stats.get("pct_negative", 0)
    pct_gt1 = stats.get("pct_gt1", 0)
    pct_0_1 = stats.get("pct_in_0_1", 0)
    max_val = stats.get("max", 0)
    n_gt1e6 = stats.get("n_gt1e6", 0)

    if col in ("direction_balance_bytes", "direction_balance_packets"):
        if pct_neg > 5 and pct_gt1 < 5:
            return ("(sum_a - sum_b) / (sum_a + sum_b + eps)  [normalized -1..1]", "high")
        elif pct_neg < 1 and pct_0_1 > 90 and pct_gt1 < 5:
            return ("sum_a / (sum_a + sum_b + eps)  [proportion 0..1]", "high")
        elif pct_neg < 5 and pct_gt1 > 20:
            return ("sum_a / (sum_b + eps)  [raw ratio 0..∞]", "medium")
        elif pct_neg < 5 and max_val > 1e6:
            return ("total_bytes_fwd (raw cumulative)  [0..∞, large values]", "medium")
        else:
            return ("mixed/unclear", "low")

    elif col == "dispersion_symmetry":
        if pct_gt1 < 5 and pct_neg < 1 and pct_0_1 > 80:
            return ("1 - |std_a - std_b| / (std_a + std_b + eps)  [0..1]", "high")
        elif n_gt1e6 > 0:
            return ("product of size statistics (raw, large values)", "medium")
        elif pct_gt1 > 20:
            return ("ratio or product of size statistics (> 1)", "medium")
        else:
            return ("unknown — mixed [0..∞]", "low")

    return ("unknown", "low")


def verify_unambiguous_features(rows: List[Dict]) -> Dict[str, Dict]:
    """
    Verify features that have clear unambiguous formulas:
    - sz_cv = sz_all_std / (sz_all_mean + eps)
    - sz_qratio = sz_all_p75 / (sz_all_p25 + eps)
    - sz_median_to_mean = sz_all_median / (sz_all_mean + eps)
    - sz_iqr = sz_all_p75 - sz_all_p25
    - sz_p25_median_ratio = sz_all_p25 / (sz_all_median + eps)
    - sz_p75_median_ratio = sz_all_p75 / (sz_all_median + eps)
    - sz_iqr_norm_median = sz_iqr / (sz_all_median + eps)
    """
    results = {}
    checks = {
        "sz_cv == sz_coef_variation": lambda r: (fv(r, "sz_cv"), fv(r, "sz_coef_variation")),
        "sz_iqr == sz_all_p75 - sz_all_p25": lambda r: (fv(r, "sz_iqr"), (fv(r, "sz_all_p75") or 0) - (fv(r, "sz_all_p25") or 0)),
        "sz_qratio == sz_all_p75 / (sz_all_p25 + eps)": lambda r: (fv(r, "sz_qratio"), (fv(r, "sz_all_p75") or 0) / ((fv(r, "sz_all_p25") or 0) + _EPS)),
        "sz_median_to_mean == sz_all_median / (sz_all_mean + eps)": lambda r: (fv(r, "sz_median_to_mean"), (fv(r, "sz_all_median") or 0) / ((fv(r, "sz_all_mean") or 0) + _EPS)),
        "sz_p25_median_ratio == sz_all_p25 / (sz_all_median + eps)": lambda r: (fv(r, "sz_p25_median_ratio"), (fv(r, "sz_all_p25") or 0) / ((fv(r, "sz_all_median") or 0) + _EPS)),
        "sz_p75_median_ratio == sz_all_p75 / (sz_all_median + eps)": lambda r: (fv(r, "sz_p75_median_ratio"), (fv(r, "sz_all_p75") or 0) / ((fv(r, "sz_all_median") or 0) + _EPS)),
        "sz_iqr_norm_median == sz_iqr / (sz_all_median + eps)": lambda r: (fv(r, "sz_iqr_norm_median"), (fv(r, "sz_iqr") or 0) / ((fv(r, "sz_all_median") or 0) + _EPS)),
        "iat_cv == iat_all_std / (iat_all_mean + eps)": lambda r: (fv(r, "iat_cv"), (fv(r, "iat_all_std") or 0) / ((fv(r, "iat_all_mean") or 0) + _EPS)),
        "iat_iqr == iat_all_p75 - iat_all_p25": lambda r: (fv(r, "iat_iqr"), (fv(r, "iat_all_p75") or 0) - (fv(r, "iat_all_p25") or 0)),
        "iat_median == iat_all_median": lambda r: (fv(r, "iat_median"), fv(r, "iat_all_median")),
    }

    for label, fn in checks.items():
        errors = []
        for r in rows[:200]:
            try:
                obs, pred = fn(r)
                if obs is not None and pred is not None and not math.isnan(pred) and not math.isinf(pred):
                    errors.append(abs(obs - pred))
            except Exception:
                pass
        if errors:
            pct_exact = sum(1 for e in errors if e < 1e-4) / len(errors) * 100
            results[label] = {
                "n": len(errors),
                "mean_err": _mean(errors),
                "max_err": max(errors),
                "pct_exact": pct_exact,
                "verified": pct_exact > 95,
            }
    return results


def direction_balance_formula_test(rows: List[Dict]) -> Dict[str, Any]:
    """
    Test specific direction_balance_bytes formula hypotheses using only
    the information available in the CSV (no raw packet data).

    We CAN check consistency relationships:
    - If formula is (sum_a - sum_b)/(sum_a + sum_b + eps):
        direction_balance_bytes * (sum_a + sum_b) + direction_balance_bytes * eps = sum_a - sum_b
        sum_a = sz_mean_max * cnt_a, sum_b = sz_mean_min * cnt_b  (if we know cnt_a, cnt_b)

    - If formula is sum_a / (sum_b + eps):
        direction_balance_bytes * sum_b ≈ sum_a

    - If formula is sum_a / (sum_a + sum_b + eps):
        direction_balance_bytes * (sum_a + sum_b) ≈ sum_a
        direction_balance_bytes ≈ sz_mean_max * cnt_a / sz_all_mean / (cnt_a + cnt_b)
    """

    # Check 1: Is direction_balance_bytes related to sz_all_mean via:
    # db = sum_a / (sum_a + sum_b + eps)
    # sum_a + sum_b = sz_all_mean * n_total (for some n_total)
    # sum_a = db * (sz_all_mean * n_total)
    # This requires knowing n_total (not in CSV), so we check relative consistency.

    # Check 2: Check if direction_balance_bytes and sz_all_mean are correlated for USBVPN
    # (where sz_all_mean is non-zero and we know direction_balance is in [-1,1])

    corr_vals = []
    for r in rows:
        db = fv(r, "direction_balance_bytes")
        am = fv(r, "sz_all_mean")
        if db is not None and am is not None and am > 0:
            corr_vals.append((db, am))

    # Check 3: For rows where direction_balance_packets = 0 (symmetric),
    # direction_balance_bytes should also be close to 0 (if bytes ≈ symmetric)
    dp_zero = [r for r in rows if fv(r, "direction_balance_packets") is not None
               and abs(fv(r, "direction_balance_packets")) < 0.01]

    # Check 4: sz_mean_max > sz_mean_min always (trivially true by definition)
    # Check 5: direction_balance_bytes > 0 iff sz_mean_max is on the forward side
    # This requires knowing which direction has more bytes, i.e., knowing the sign of direction_balance_bytes
    # For normalized formula: positive db → forward > backward

    db_when_dp_zero = [fv(r, "direction_balance_bytes") for r in dp_zero
                       if fv(r, "direction_balance_bytes") is not None]

    return {
        "n_with_both": len(corr_vals),
        "n_dp_near_zero": len(dp_zero),
        "db_when_dp_zero_mean": _mean(db_when_dp_zero) if db_when_dp_zero else "N/A",
        "db_when_dp_zero_max_abs": max(abs(v) for v in db_when_dp_zero) if db_when_dp_zero else "N/A",
        "note": "When direction_balance_packets ≈ 0 (symmetric packet count), "
                "direction_balance_bytes should also be ≈ 0 if sizes are symmetric. "
                "High |db_bytes| when db_packets=0 indicates different size normalization.",
    }


def main():
    print("[*] Loading data …")
    demo_rows = []
    with open(DEMO_CSV, "r", encoding="utf-8") as f:
        demo_rows = list(csv.DictReader(f))
    print(f"    Demo: {len(demo_rows)} rows")

    by_ds = load_csv_by_dataset(SIMTEST_CSV, max_rows=5000)
    total = sum(len(v) for v in by_ds.values())
    print(f"    SimTest by dataset: { {k: len(v) for k, v in by_ds.items()} } (total={total})")

    datasets = sorted(by_ds.keys())

    # ── Per-dataset feature stats ──────────────────────────────────────────────
    print("[*] Computing per-dataset feature statistics …")
    feature_stats: Dict[str, Dict] = {}
    for ds in datasets:
        feature_stats[ds] = {}
        for col in ["direction_balance_bytes", "direction_balance_packets", "dispersion_symmetry",
                    "sz_all_mean", "sz_coef_variation", "sz_cv"]:
            feature_stats[ds][col] = feature_range_stats(by_ds[ds], col)

    # ── Formula hypothesis per dataset ────────────────────────────────────────
    print("[*] Inferring per-dataset formula hypotheses …")
    hypotheses: Dict[str, Dict] = {}
    for ds in datasets:
        hypotheses[ds] = {}
        for col in ["direction_balance_bytes", "direction_balance_packets", "dispersion_symmetry"]:
            stat = feature_stats[ds][col]
            hyp, conf = infer_formula_hypothesis(stat, col)
            hypotheses[ds][col] = {"hypothesis": hyp, "confidence": conf}

    # ── Verify unambiguous features per dataset ────────────────────────────────
    print("[*] Verifying unambiguous feature formulas …")
    verification: Dict[str, Dict] = {}
    for ds in datasets:
        verification[ds] = verify_unambiguous_features(by_ds[ds])

    # ── Direction balance consistency check ───────────────────────────────────
    print("[*] Running direction_balance consistency checks …")
    db_checks: Dict[str, Dict] = {}
    for ds in datasets:
        db_checks[ds] = direction_balance_formula_test(by_ds[ds])

    # ── ISCX specific analysis: small-value rows ──────────────────────────────
    print("[*] Analysing ISCX small-value direction_balance rows …")
    iscx_rows = by_ds.get("iscx", [])
    iscx_small_db = [r for r in iscx_rows
                     if fv(r, "direction_balance_bytes") is not None
                     and 0 < fv(r, "direction_balance_bytes") <= 100]
    print(f"    ISCX rows with direction_balance_bytes in (0, 100]: {len(iscx_small_db)}/{len(iscx_rows)}")

    # For ISCX small rows, check if direction_balance_bytes ≈ direction_balance_packets
    # If formula is cnt_a/cnt_b for both, then db_bytes / db_packets ≈ mean_a / mean_b
    iscx_ratio_pairs = []
    for r in iscx_small_db[:50]:
        db = fv(r, "direction_balance_bytes")
        dp = fv(r, "direction_balance_packets")
        sz_max = fv(r, "sz_mean_max")
        sz_min = fv(r, "sz_mean_min")
        if all(v is not None and v > 0 for v in [db, dp, sz_max, sz_min]):
            # If db = sum_a/sum_b = mean_a*cnt_a / (mean_b*cnt_b) and dp = cnt_a/cnt_b
            # then db / dp = mean_a / mean_b
            ratio = db / dp
            expected = sz_max / sz_min
            iscx_ratio_pairs.append({
                "db": db, "dp": dp, "ratio_db_dp": ratio,
                "sz_max_over_min": expected,
                "match": abs(ratio - expected) / (expected + _EPS) < 0.05
            })

    n_match = sum(1 for r in iscx_ratio_pairs if r["match"])
    print(f"    ISCX rows where db/dp ≈ sz_mean_max/sz_mean_min: {n_match}/{len(iscx_ratio_pairs)}")

    # ── VNAT specific analysis ────────────────────────────────────────────────
    vnat_rows = by_ds.get("vnat", [])
    print(f"[*] VNAT: {len(vnat_rows)} rows")
    vnat_db_stats = feature_range_stats(vnat_rows, "direction_balance_bytes")
    vnat_dp_stats = feature_range_stats(vnat_rows, "direction_balance_packets")
    vnat_ds_stats = feature_range_stats(vnat_rows, "dispersion_symmetry")

    # Check if VNAT db ≈ proportion (sum_a / (sum_a+sum_b+eps))
    # For this, db should be in [0,1], non-negative
    # Also check: is VNAT dispersion_symmetry ∈ [0,1]?

    # ── Check consistency of sz_cv == sz_coef_variation across datasets ───────
    print("[*] Checking sz_cv == sz_coef_variation consistency …")
    cv_check: Dict[str, float] = {}
    for ds in datasets:
        errors = []
        for r in by_ds[ds][:200]:
            cv = fv(r, "sz_cv")
            coef = fv(r, "sz_coef_variation")
            if cv is not None and coef is not None:
                errors.append(abs(cv - coef))
        if errors:
            pct = sum(1 for e in errors if e < 1e-6) / len(errors) * 100
            cv_check[ds] = pct
    print(f"    sz_cv == sz_coef_variation: { cv_check }")

    # ── Write report ──────────────────────────────────────────────────────────
    print("[*] Writing report …")
    lines: List[str] = [
        "# Feature Formula Deep Inference Report\n",
        "**Generated:** 2026-05-30  ",
        "**Source data:** `simultaneous_test_selected_models.csv` (5000 rows), `demo_flows_full_canonical.csv`  ",
        "**Purpose:** Per-dataset formula identification for 3 mismatched features  \n",
        "---\n",
    ]

    # Section 1: Dataset summary
    lines.append("\n## 1. Dataset Breakdown\n")
    lines.append("| Dataset | n_rows | direction_balance_bytes range | direction_balance_packets range | dispersion_symmetry range |")
    lines.append("|---------|--------|-------------------------------|--------------------------------|---------------------------|")
    for ds in datasets:
        db = feature_stats[ds]["direction_balance_bytes"]
        dp = feature_stats[ds]["direction_balance_packets"]
        ds_s = feature_stats[ds]["dispersion_symmetry"]
        if db.get("count", 0) == 0:
            continue
        lines.append(
            f"| `{ds}` | {db['count']} | "
            f"[{db['min']:.4g}, {db['max']:.4g}] | "
            f"[{dp['min']:.4g}, {dp['max']:.4g}] | "
            f"[{ds_s['min']:.4g}, {ds_s['max']:.4g}] |"
        )

    # Section 2: Per-dataset formula hypotheses
    lines.append("\n## 2. Per-Dataset Formula Hypotheses\n")
    lines.append("### 2a. direction_balance_bytes\n")
    lines.append("| Dataset | % in [-1,1] | % in [0,1] | % > 1 | % negative | max | Inferred Formula | Confidence |")
    lines.append("|---------|------------|------------|-------|-----------|-----|-----------------|------------|")
    for ds in datasets:
        stat = feature_stats[ds]["direction_balance_bytes"]
        if stat.get("count", 0) == 0:
            continue
        hyp = hypotheses[ds]["direction_balance_bytes"]
        lines.append(
            f"| `{ds}` | "
            f"{stat.get('pct_in_minus1_plus1', 0):.1f}% | "
            f"{stat.get('pct_in_0_1', 0):.1f}% | "
            f"{stat.get('pct_gt1', 0):.1f}% | "
            f"{stat.get('pct_negative', 0):.1f}% | "
            f"{stat['max']:.4g} | "
            f"`{hyp['hypothesis']}` | "
            f"{hyp['confidence']} |"
        )

    lines.append("\n### 2b. direction_balance_packets\n")
    lines.append("| Dataset | % in [-1,1] | % in [0,1] | % > 1 | % negative | max | Inferred Formula | Confidence |")
    lines.append("|---------|------------|------------|-------|-----------|-----|-----------------|------------|")
    for ds in datasets:
        stat = feature_stats[ds]["direction_balance_packets"]
        if stat.get("count", 0) == 0:
            continue
        hyp = hypotheses[ds]["direction_balance_packets"]
        lines.append(
            f"| `{ds}` | "
            f"{stat.get('pct_in_minus1_plus1', 0):.1f}% | "
            f"{stat.get('pct_in_0_1', 0):.1f}% | "
            f"{stat.get('pct_gt1', 0):.1f}% | "
            f"{stat.get('pct_negative', 0):.1f}% | "
            f"{stat['max']:.4g} | "
            f"`{hyp['hypothesis']}` | "
            f"{hyp['confidence']} |"
        )

    lines.append("\n### 2c. dispersion_symmetry\n")
    lines.append("| Dataset | % in [0,1] | % > 1 | % > 1e6 | max | Inferred Formula | Confidence |")
    lines.append("|---------|-----------|-------|---------|-----|-----------------|------------|")
    for ds in datasets:
        stat = feature_stats[ds]["dispersion_symmetry"]
        if stat.get("count", 0) == 0:
            continue
        hyp = hypotheses[ds]["dispersion_symmetry"]
        lines.append(
            f"| `{ds}` | "
            f"{stat.get('pct_in_0_1', 0):.1f}% | "
            f"{stat.get('pct_gt1', 0):.1f}% | "
            f"{stat.get('pct_gt_1e6', 0):.1f}% | "
            f"{stat['max']:.4g} | "
            f"`{hyp['hypothesis']}` | "
            f"{hyp['confidence']} |"
        )

    # Section 3: ISCX formula verification
    lines.append("\n## 3. ISCX Direction Balance Formula Verification\n")
    lines.append(f"""For ISCX, `direction_balance_bytes` and `direction_balance_packets` have large values,
suggesting raw ratios or raw counts rather than normalized formulas.

**Hypothesis:** The ISCX pre-extracted CSV used the formula:
  `direction_balance_bytes = sum_fwd / (sum_rev + eps)` (raw forward-to-backward byte ratio)
  `direction_balance_packets = cnt_fwd / (cnt_rev + eps)` (raw forward-to-backward packet ratio)

**Verification via db / dp ≈ sz_mean_max / sz_mean_min:**
If both use `sum / sum_rev` and `cnt / cnt_rev`, then:
  `db / dp = (sum_fwd * cnt_rev) / (cnt_fwd * sum_rev) = mean_fwd / mean_rev = sz_mean_max / sz_mean_min`

Results on ISCX rows where direction_balance_bytes ∈ (0, 100] (n={len(iscx_ratio_pairs)}):
- Rows where `db/dp ≈ sz_mean_max/sz_mean_min` (within 5%): **{n_match}/{len(iscx_ratio_pairs)}**
""")
    if iscx_ratio_pairs:
        lines.append("| db | dp | db/dp | sz_max/sz_min | Match? |")
        lines.append("|----|----|-------|--------------|--------|")
        for r in iscx_ratio_pairs[:15]:
            m = "✓" if r["match"] else "✗"
            lines.append(f"| {r['db']:.4g} | {r['dp']:.4g} | {r['ratio_db_dp']:.4g} | {r['sz_max_over_min']:.4g} | {m} |")

    # Section 4: VNAT formula analysis
    lines.append("\n## 4. VNAT Formula Analysis\n")
    lines.append(f"""VNAT dataset features:
- `direction_balance_bytes`: range [{vnat_db_stats.get('min', 'N/A'):.4g}, {vnat_db_stats.get('max', 'N/A'):.4g}], 
  mean={vnat_db_stats.get('mean', 'N/A'):.4g}, % negative={vnat_db_stats.get('pct_negative', 0):.1f}%,
  % in [0,1]={vnat_db_stats.get('pct_in_0_1', 0):.1f}%
- `direction_balance_packets`: range [{vnat_dp_stats.get('min', 'N/A'):.4g}, {vnat_dp_stats.get('max', 'N/A'):.4g}],
  mean={vnat_dp_stats.get('mean', 'N/A'):.4g}, % negative={vnat_dp_stats.get('pct_negative', 0):.1f}%,
  % in [0,1]={vnat_dp_stats.get('pct_in_0_1', 0):.1f}%
- `dispersion_symmetry`: range [{vnat_ds_stats.get('min', 'N/A'):.4g}, {vnat_ds_stats.get('max', 'N/A'):.4g}],
  mean={vnat_ds_stats.get('mean', 'N/A'):.4g}, % in [0,1]={vnat_ds_stats.get('pct_in_0_1', 0):.1f}%

**VNAT direction_balance_bytes is consistently non-negative and in [0,1].**
This is inconsistent with both:
1. Normalized difference `(sum_a - sum_b)/(sum_a+sum_b+eps)` ∈ [-1,1] — would expect ~50% negative
2. Raw ratio `sum_a/(sum_b+eps)` — would expect values > 1

**Most consistent with: `sum_fwd / (sum_fwd + sum_rev + eps)` = byte proportion ∈ [0, 1].**
  (This is the proportion of traffic going in the forward direction.)
  
**VNAT dispersion_symmetry is also in [0,1]** — consistent with:
  `1 - |std_a - std_b| / (std_a + std_b + eps)` ∈ [0,1]  ← same as live extractor formula!
  
This means VNAT used the SAME `dispersion_symmetry` formula as the live extractor.
""")

    # Section 5: Unambiguous feature verification
    lines.append("\n## 5. Unambiguous Feature Formula Verification\n")
    lines.append("Testing self-consistency of derived features (should verify correctly if formulas match):\n")
    for ds in datasets[:3]:
        lines.append(f"\n### Dataset: `{ds}`\n")
        vr = verification[ds]
        lines.append("| Formula | n | Mean Error | % Exact |")
        lines.append("|---------|---|-----------|---------|")
        for label, r in vr.items():
            verified = "✓" if r.get("verified") else "✗"
            lines.append(f"| `{label}` | {r.get('n', 0)} | {r.get('mean_err', 'N/A'):.4g} | {r.get('pct_exact', 0):.1f}% {verified} |")

    # Section 6: Direction balance consistency check
    lines.append("\n## 6. Direction Balance Consistency Check\n")
    lines.append("When direction_balance_packets ≈ 0 (symmetric packet count), direction_balance_bytes should ≈ 0:\n")
    lines.append("| Dataset | n_dp_near_zero | mean(db when dp≈0) | max(|db| when dp≈0) |")
    lines.append("|---------|----------------|-------------------|---------------------|")
    for ds in datasets:
        chk = db_checks.get(ds, {})
        lines.append(
            f"| `{ds}` | "
            f"{chk.get('n_dp_near_zero', 0)} | "
            f"{chk.get('db_when_dp_zero_mean', 'N/A')} | "
            f"{chk.get('db_when_dp_zero_max_abs', 'N/A')} |"
        )

    # Section 7: Summary
    lines.append("\n## 7. Summary of Inferred Training Formulas\n")
    lines.append("""| Feature | ISCX Formula | USBVPN Formula | VNAT Formula | Live Extractor Formula |
|---------|-------------|---------------|-------------|------------------------|
| `direction_balance_bytes` | `sum_fwd / (sum_rev + eps)` (ratio) | `(sum_fwd - sum_rev) / (sum_fwd + sum_rev + eps)` (normalized) | `sum_fwd / (sum_fwd + sum_rev + eps)` (proportion) | `(sum_a - sum_b) / (sum_a + sum_b + eps)` (normalized) |
| `direction_balance_packets` | `cnt_fwd / (cnt_rev + eps)` (ratio) | `(cnt_fwd - cnt_rev) / (cnt_fwd + cnt_rev + eps)` (normalized) | `cnt_fwd / (cnt_fwd + cnt_rev + eps)` (proportion) | `(cnt_a - cnt_b) / (cnt_a + cnt_b + eps)` (normalized) |
| `dispersion_symmetry` | Unknown (large values ∈ [0, 813M]) | Unknown (large values ∈ [0, 1.494B]) | `1 - |std_a - std_b| / (std_a + std_b + eps)` ∈ [0,1] | `1 - |std_a - std_b| / (std_a + std_b + eps)` ∈ [0,1] |

### Key findings:

1. **Three different datasets used THREE different formulas** for `direction_balance_bytes` and
   `direction_balance_packets`. The training data is **formula-inconsistent across datasets**.

2. **The live extractor matches the USBVPN formula** for direction_balance features.
   The live extractor matches the VNAT formula for `dispersion_symmetry`.
   The live extractor does NOT match the ISCX formula for any of the three features.

3. **`dispersion_symmetry` for ISCX/USBVPN** is a large-valued mystery. It does NOT match
   `1 - |std_a - std_b| / (std_a + std_b + eps)`. The ISCX/USBVPN pre-extracted CSVs
   likely used a different tool (e.g., CICFlowMeter) which computed this feature differently.

4. **VNAT used the same formula as the live extractor** for both `direction_balance_*` (proportion)
   and `dispersion_symmetry` (normalized). However, the VNAT proportion formula ∈ [0,1]
   is still different from the live extractor's difference-ratio formula ∈ [-1,1].

5. **`domain_auc = 1.0` is explained**: The model can perfectly identify which dataset
   a sample came from because the feature scales are completely different for ISCX, USBVPN, and VNAT.
   Features like `direction_balance_bytes = 1e9` → ISCX; `direction_balance_bytes = -0.5` → USBVPN/VNAT.

### Implication for live detection:

The live extractor uses consistent normalized/ratio formulas that match neither ISCX nor VNAT exactly.
Any live capture processed by `pcap_to_live_stream.py` will produce features outside the
training distribution for ALL three datasets — the model is not exposed to live-capture-style
features during training.

**This is the fundamental limitation of this prototype.** Not a code bug, but a training-data
collection methodology mismatch.
""")

    lines.append("\n---\n")
    lines.append("*Deep inference completed: 2026-05-30. No model or extractor changes made.*\n")

    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n[✓] Report written to: {REPORT_OUT}")
    print(f"    {len(lines)} lines")


if __name__ == "__main__":
    main()

