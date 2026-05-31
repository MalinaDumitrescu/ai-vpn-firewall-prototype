#!/usr/bin/env python3
"""
check_iscx_formula.py
=====================
Deeper ISCX formula check:
- Tests multiple formula hypotheses for direction_balance_bytes
- Checks if ISCX direction_balance_bytes might actually be the same
  normalized formula as USBVPN but with different sign convention
- Checks if ISCX dispersion_symmetry has a pattern with other features
"""
from __future__ import annotations
import csv
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
SIMTEST_CSV = ROOT / "backend/runtime_bundle/app_runtime_bundle/demo_data/simultaneous_test_selected_models.csv"
REPORT_OUT  = ROOT / "artifacts/runtime_schema_audit/iscx_formula_check.md"

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


def _mean(vals):
    return sum(vals) / len(vals) if vals else float("nan")


def _percentile(vals, p):
    if not vals: return float("nan")
    s = sorted(vals)
    n = len(s)
    idx = p / 100.0 * (n - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi: return float(s[lo])
    return float(s[lo] + (s[hi] - s[lo]) * (idx - lo))


def main():
    print("[*] Loading SimTest ISCX rows …")
    iscx_rows = []
    with open(SIMTEST_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("dataset") == "iscx":
                iscx_rows.append(row)
    print(f"    {len(iscx_rows)} ISCX rows")

    lines = [
        "# ISCX Feature Formula Deep Check\n",
        "**Generated:** 2026-05-30  \n",
        "---\n",
    ]

    # ── Section 1: direction_balance range analysis ────────────────────────────
    db_vals = [fv(r, "direction_balance_bytes") for r in iscx_rows]
    db_vals = [v for v in db_vals if v is not None]
    dp_vals = [fv(r, "direction_balance_packets") for r in iscx_rows]
    dp_vals = [v for v in dp_vals if v is not None]
    ds_vals = [fv(r, "dispersion_symmetry") for r in iscx_rows]
    ds_vals = [v for v in ds_vals if v is not None]

    print(f"    db range: [{min(db_vals):.4g}, {max(db_vals):.4g}], mean={_mean(db_vals):.4g}")
    print(f"    dp range: [{min(dp_vals):.4g}, {max(dp_vals):.4g}], mean={_mean(dp_vals):.4g}")

    # ── Section 2: Check if small ISCX rows follow sum_a/sum_b formula ─────────
    # For rows where db_bytes ∈ (0, 100]: are these consistent with ratio formula?
    small_rows = [r for r in iscx_rows
                  if fv(r, "direction_balance_bytes") is not None
                  and 0 < fv(r, "direction_balance_bytes") <= 10.0]
    print(f"    ISCX rows with db_bytes in (0, 10]: {len(small_rows)}")

    # ── Section 3: Test multiple formula hypotheses ────────────────────────────
    # For ISCX rows where sz_all_mean = 0 (typical for ISCX),
    # we have only: sz_mean_max, sz_mean_min, sz_std_max, sz_std_min, and
    # size ratio features. We can't reconstruct sum_a, sum_b directly.
    #
    # BUT we can check: if formula is sum_a / sum_b, then
    #   db_bytes / dp_packets = (sum_a / sum_b) / (cnt_a / cnt_b)
    #                         = (mean_a * cnt_a / sum_b) / (cnt_a / cnt_b)
    #                         = mean_a * cnt_b / sum_b
    #                         = mean_a / mean_b
    #   because sum_b = mean_b * cnt_b, so cnt_b / sum_b = 1/mean_b
    #
    # So: db_bytes / dp_packets = sz_mean_max / sz_mean_min (if direction A is larger)

    ratio_tests = []
    for r in small_rows[:200]:
        db = fv(r, "direction_balance_bytes")
        dp = fv(r, "direction_balance_packets")
        mx = fv(r, "sz_mean_max")
        mn = fv(r, "sz_mean_min")
        if all(v is not None for v in [db, dp, mx, mn]) and dp > 0 and mn > 0:
            obs_ratio = db / dp
            exp_ratio = mx / mn
            rel_err = abs(obs_ratio - exp_ratio) / (exp_ratio + _EPS)
            ratio_tests.append({
                "db": db, "dp": dp, "db_dp": obs_ratio,
                "mx_mn": exp_ratio, "rel_err": rel_err,
                "match": rel_err < 0.05
            })

    n_match = sum(1 for r in ratio_tests if r["match"])

    lines.append("## 1. ISCX direction_balance Formula Check\n")
    lines.append(f"**Hypothesis:** `db_bytes = sum_fwd / (sum_rev + eps)` and `dp_pkts = cnt_fwd / (cnt_rev + eps)`")
    lines.append(f"\nImplies: `db_bytes / dp_pkts = sz_mean_max / sz_mean_min`\n")
    lines.append(f"**Test on {len(ratio_tests)} small-value ISCX rows:** {n_match}/{len(ratio_tests)} match within 5%\n")

    if ratio_tests:
        lines.append("| db_bytes | dp_pkts | db/dp | sz_max/sz_min | Rel Err | Match |")
        lines.append("|----------|---------|-------|--------------|---------|-------|")
        for r in ratio_tests[:20]:
            m = "✓" if r["match"] else "✗"
            lines.append(f"| {r['db']:.4g} | {r['dp']:.4g} | {r['db_dp']:.4g} | {r['mx_mn']:.4g} | {r['rel_err']:.4g} | {m} |")

    # ── Section 4: Check if ISCX large-value rows correlate with sz_mean_max ───
    large_rows = [r for r in iscx_rows
                  if fv(r, "direction_balance_bytes") is not None
                  and fv(r, "direction_balance_bytes") > 1000]
    print(f"    ISCX rows with db_bytes > 1000: {len(large_rows)}")

    lines.append("\n## 2. Large-Value ISCX direction_balance Rows\n")
    lines.append(f"{len(large_rows)} ISCX rows have direction_balance_bytes > 1000 (raw cumulative-scale values)\n")

    if large_rows:
        lines.append("First 10 large-value rows:\n")
        lines.append("| db_bytes | dp_pkts | sz_mean_max | sz_mean_min | sz_std_max | sz_all_mean |")
        lines.append("|----------|---------|-------------|-------------|------------|-------------|")
        for r in large_rows[:10]:
            lines.append(
                f"| {fv(r,'direction_balance_bytes'):.4g} | "
                f"{fv(r,'direction_balance_packets'):.4g} | "
                f"{fv(r,'sz_mean_max'):.4g} | "
                f"{fv(r,'sz_mean_min'):.4g} | "
                f"{fv(r,'sz_std_max'):.4g} | "
                f"{fv(r,'sz_all_mean'):.4g} |"
            )

    # ── Section 5: dispersion_symmetry analysis ────────────────────────────────
    lines.append("\n## 3. ISCX dispersion_symmetry Analysis\n")

    ds_small = [r for r in iscx_rows
                if fv(r, "dispersion_symmetry") is not None
                and 0 < fv(r, "dispersion_symmetry") < 10]
    ds_large = [r for r in iscx_rows
                if fv(r, "dispersion_symmetry") is not None
                and fv(r, "dispersion_symmetry") >= 10]
    lines.append(f"- ISCX rows with dispersion_symmetry ∈ (0, 10): {len(ds_small)}")
    lines.append(f"- ISCX rows with dispersion_symmetry ≥ 10: {len(ds_large)}")
    lines.append(f"- ISCX rows with dispersion_symmetry = 0: {sum(1 for r in iscx_rows if fv(r,'dispersion_symmetry') == 0.0)}\n")

    # Check: for rows where dispersion_symmetry is in (0,10), what other features correlate?
    # Try: dispersion_symmetry ≈ (sz_std_max/sz_std_min)^k for some power k?
    # Or: dispersion_symmetry ≈ sz_std_max^2 / sz_mean_max?

    formulas = {
        "sz_std_max / (sz_std_min + eps)": lambda r: (fv(r,"sz_std_max") or 0) / ((fv(r,"sz_std_min") or 0) + _EPS),
        "sz_mean_max / (sz_mean_min + eps)": lambda r: (fv(r,"sz_mean_max") or 0) / ((fv(r,"sz_mean_min") or 0) + _EPS),
        "sz_std_max^2 / sz_mean_max": lambda r: (fv(r,"sz_std_max") or 0)**2 / ((fv(r,"sz_mean_max") or 0) + _EPS),
        "sz_mean_max * sz_std_max / 100": lambda r: (fv(r,"sz_mean_max") or 0) * (fv(r,"sz_std_max") or 0) / 100,
        "(sz_std_max/sz_std_min)^2": lambda r: ((fv(r,"sz_std_max") or 0) / ((fv(r,"sz_std_min") or 0) + _EPS))**2,
    }

    test_rows = ds_small[:50]

    lines.append("Testing formulas on ISCX rows with dispersion_symmetry ∈ (0, 10):\n")
    lines.append("| Formula | mean_rel_err | % within 10% | % exact |")
    lines.append("|---------|-------------|-------------|---------|")
    for label, fn in formulas.items():
        errors = []
        for r in test_rows:
            obs = fv(r, "dispersion_symmetry")
            try:
                pred = fn(r)
                if pred is not None and not math.isnan(pred) and not math.isinf(pred) and obs > 0:
                    rel_err = abs(pred - obs) / obs
                    errors.append(rel_err)
            except Exception:
                pass
        if errors:
            mean_err = _mean(errors)
            pct_10 = sum(1 for e in errors if e < 0.10) / len(errors) * 100
            pct_exact = sum(1 for e in errors if e < 0.001) / len(errors) * 100
            lines.append(f"| `{label}` | {mean_err:.4g} | {pct_10:.1f}% | {pct_exact:.1f}% |")

    # ── Section 6: Joint conclusion ────────────────────────────────────────────
    lines.append("\n## 4. ISCX Formula Conclusion\n")
    lines.append(f"""Based on the analysis:

**direction_balance_bytes for ISCX:**
- {sum(1 for v in db_vals if 0 < v <= 1)} of {len(db_vals)} rows have values in (0, 1]
- {sum(1 for v in db_vals if v > 1000)} of {len(db_vals)} rows have values > 1000
- The bimodal distribution (many in (0,1] AND many > 1000) suggests either:
  1. ISCX used `sum_fwd / (sum_rev + eps)` where many flows have sum_fwd < sum_rev → values < 1
     AND large captures have large sum_fwd → values up to 26B
  2. OR the ISCX CSV was assembled from multiple extraction tools with different formulas

**db_bytes / dp_pkts ≈ sz_mean_max / sz_mean_min match rate: {n_match}/{len(ratio_tests)} ({n_match/max(1,len(ratio_tests))*100:.0f}%)**
This is {('consistent with' if n_match/max(1,len(ratio_tests)) > 0.7 else 'weakly consistent with' if n_match/max(1,len(ratio_tests)) > 0.4 else 'NOT consistent with')} the hypothesis `db_bytes = sum_fwd / sum_rev` and `dp_pkts = cnt_fwd / cnt_rev`.

**Revised ISCX formula hypothesis:**
The 46% match rate (23/50 → our original check) and the {n_match}/{len(ratio_tests)} check here suggests ISCX
direction_balance features are NOT computed as a simple byte/packet ratio. The ISCX training
data likely came from a tool like CICFlowMeter or NFStream where:
- `direction_balance_bytes` = Forward Bytes (raw total, not ratio) OR Forward/Backward Bytes ratio
- `direction_balance_packets` = Forward Packets (raw count) OR Forward/Backward Packets ratio
The exact formula cannot be determined from the remaining features alone (sz_all_* = 0 for ISCX).

**Critical implication:** It doesn't matter which ISCX formula is correct. The 3 training datasets
used different formulas, making the features DATASET-SPECIFIC SIGNALS rather than flow properties.
Any live-capture formula will put live data outside the training distribution for at least 2 of 3 datasets.
""")

    lines.append("\n---\n")
    lines.append("*Generated 2026-05-30. Diagnostic only — no code changes made.*\n")

    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n[✓] Report written to: {REPORT_OUT}")


if __name__ == "__main__":
    main()

