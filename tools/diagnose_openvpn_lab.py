"""
Diagnostic script: OpenVPN lab PCAP classification analysis.
Produces artifacts/runtime_schema_audit/openvpn_lab_*.{md,csv}
"""

import pandas as pd
import numpy as np
import joblib
import json
import pathlib
import sys
import os
import textwrap
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = pathlib.Path(__file__).parent.parent
MODEL_BASE = PROJECT_ROOT / "backend/runtime_bundle/app_runtime_bundle/runtime_models/full_canonical__lgbm"
FEATURES_CSV = PROJECT_ROOT / "captures/vm_openvpn_lab_auto_features.csv"
OUT_DIR = PROJECT_ROOT / "artifacts/runtime_schema_audit"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Training reference distributions (if available)
DEMO_DATA_DIR = PROJECT_ROOT / "backend/runtime_bundle/app_runtime_bundle/demo_data"
# Also check for any existing captures for comparison
ALT_CAPTURES = [
    PROJECT_ROOT / "captures/vm_warp_features.csv",
    PROJECT_ROOT / "captures/vm_basic_benign_features.csv",
    PROJECT_ROOT / "captures/vm_vpnlike_features.csv",
    PROJECT_ROOT / "captures/vm_openvpn_lab_features.csv",
    PROJECT_ROOT / "captures/vm_openvpn_lab_sample_features.csv",
    PROJECT_ROOT / "captures/vm_openvpn_lab_varied_sample_features.csv",
    PROJECT_ROOT / "captures/live_generated_full_canonical_test.csv",
]

# ---------------------------------------------------------------------------
# Load model config
# ---------------------------------------------------------------------------
feat_order = json.loads((MODEL_BASE / "feature_order.json").read_text())["feature_order"]
thresholds = json.loads((MODEL_BASE / "thresholds.json").read_text())
rlc = json.loads((MODEL_BASE / "runtime_loader_config.json").read_text())
review_thr = thresholds["review_threshold"]
block_thr = thresholds["block_threshold"]
agg_method = rlc.get("session_aggregation", "mean")
session_col = rlc.get("session_grouping_column", "capture_id")

print(f"[config] review_threshold={review_thr}, block_threshold={block_thr}")
print(f"[config] aggregation={agg_method}, session_grouping_column={session_col}")

# ---------------------------------------------------------------------------
# Load model
# ---------------------------------------------------------------------------
print("[load] Loading model.pkl ...")
model = joblib.load(MODEL_BASE / "model.pkl")
print(f"[load] Model type: {type(model).__name__}")

# Try calibrator
calibrator = None
try:
    calibrator = joblib.load(MODEL_BASE / "calibrator.pkl")
    print(f"[load] Calibrator type: {type(calibrator).__name__}")
except Exception as e:
    print(f"[load] calibrator.pkl not loadable: {e}")

# ---------------------------------------------------------------------------
# Load features
# ---------------------------------------------------------------------------
print(f"[load] Loading features from {FEATURES_CSV} ...")
df = pd.read_csv(FEATURES_CSV)
print(f"[load] {len(df)} rows, {len(df.columns)} columns")

missing_feats = [c for c in feat_order if c not in df.columns]
extra_meta = [c for c in df.columns if c not in feat_order]
print(f"[check] Missing model features: {missing_feats}")
print(f"[check] Metadata columns: {extra_meta}")

# ---------------------------------------------------------------------------
# Run model
# ---------------------------------------------------------------------------
X = df[feat_order].values
nan_count = np.isnan(X).sum()
inf_count = np.isinf(X).sum()
print(f"[check] NaN in feature matrix: {nan_count}")
print(f"[check] Inf in feature matrix: {inf_count}")

# Replace any NaN/Inf with 0 for scoring (flag separately)
X_clean = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

raw_probs = model.predict_proba(X_clean)[:, 1]

# Calibrated if available
cal_probs = None
if calibrator is not None:
    try:
        cal_probs = calibrator.predict(raw_probs.reshape(-1, 1))
        print("[score] Calibrator applied successfully.")
    except Exception as e:
        try:
            cal_probs = calibrator.transform(raw_probs)
            print("[score] Calibrator (transform) applied.")
        except:
            print(f"[score] Calibrator failed: {e}")


def action(p):
    if p >= block_thr:
        return "SIMULATED_BLOCK"
    if p >= review_thr:
        return "FLAG_REVIEW"
    return "PASS"


# ---------------------------------------------------------------------------
# Flow scores table
# ---------------------------------------------------------------------------
meta_cols = [c for c in ["flow_id", "session_id", "src_ip", "dst_ip", "protocol", "dst_port"] if c in df.columns]
flow_df = df[meta_cols].copy()
flow_df["prob_raw"] = raw_probs
if cal_probs is not None:
    flow_df["prob_calibrated"] = cal_probs
flow_df["action"] = flow_df["prob_raw"].apply(action)
flow_df["review_threshold"] = review_thr
flow_df["block_threshold"] = block_thr

print("\n=== PER-FLOW SCORES ===")
print(flow_df.to_string(index=False))

flow_scores_path = OUT_DIR / "openvpn_lab_flow_scores.csv"
flow_df.to_csv(flow_scores_path, index=False)
print(f"\n[saved] {flow_scores_path}")

# ---------------------------------------------------------------------------
# Score distribution summary
# ---------------------------------------------------------------------------
print("\n=== SCORE DISTRIBUTION ===")
p_arr = raw_probs
print(f"  min  = {p_arr.min():.6f}")
print(f"  p10  = {np.percentile(p_arr,10):.6f}")
print(f"  p25  = {np.percentile(p_arr,25):.6f}")
print(f"  mean = {p_arr.mean():.6f}")
print(f"  p50  = {np.percentile(p_arr,50):.6f}")
print(f"  p75  = {np.percentile(p_arr,75):.6f}")
print(f"  p90  = {np.percentile(p_arr,90):.6f}")
print(f"  p95  = {np.percentile(p_arr,95):.6f}")
print(f"  max  = {p_arr.max():.6f}")
print(f"  PASS ({p_arr.min():.4f} < {review_thr}): {(p_arr < review_thr).sum()} / {len(p_arr)}")
print(f"  FLAG_REVIEW: {((p_arr >= review_thr) & (p_arr < block_thr)).sum()} / {len(p_arr)}")
print(f"  SIMULATED_BLOCK: {(p_arr >= block_thr).sum()} / {len(p_arr)}")

# ---------------------------------------------------------------------------
# Session aggregation (mimic live-ingest)
# ---------------------------------------------------------------------------
print("\n=== SESSION AGGREGATION ===")
# The config says session_grouping_column = "capture_id" but our CSV has "session_id"
# The live-ingest service falls back to session_id
grp_col = session_col if session_col in df.columns else ("session_id" if "session_id" in df.columns else None)
print(f"  Using grouping column: {grp_col} (config says '{session_col}')")

sess_records = []
if grp_col:
    for sess, g in df.groupby(grp_col):
        scores = raw_probs[g.index]
        m = np.mean(scores)
        mx = np.max(scores)
        p80 = float(np.percentile(scores, 80))
        if agg_method == "mean":
            agg_score = m
        elif agg_method == "max":
            agg_score = mx
        elif agg_method == "p80":
            agg_score = p80
        else:
            agg_score = m
        sess_records.append({
            "session_id": sess,
            "n_flows": len(g),
            "mean_score": float(m),
            "max_score": float(mx),
            "p80_score": float(p80),
            "agg_score": float(agg_score),
            "agg_method": agg_method,
            "review_threshold": review_thr,
            "block_threshold": block_thr,
            "action": action(agg_score),
        })
    sess_df = pd.DataFrame(sess_records)
    print(sess_df.to_string(index=False))
    sess_path = OUT_DIR / "openvpn_lab_session_scores.csv"
    sess_df.to_csv(sess_path, index=False)
    print(f"\n[saved] {sess_path}")
else:
    print("  No grouping column found; skipping session aggregation.")
    sess_df = pd.DataFrame()

# ---------------------------------------------------------------------------
# IP address / traffic breakdown
# ---------------------------------------------------------------------------
print("\n=== TRAFFIC BREAKDOWN BY IP PAIR ===")
if "src_ip" in df.columns and "dst_ip" in df.columns:
    df2_tmp = df[["src_ip", "dst_ip", "protocol", "flow_id", "sz_all_mean", "iat_all_mean"]].copy()
    df2_tmp["prob"] = raw_probs
    grp_list = []
    for (sip, dip, proto), g in df2_tmp.groupby(["src_ip", "dst_ip", "protocol"]):
        grp_list.append({
            "src_ip": sip, "dst_ip": dip, "protocol": proto,
            "n_flows": len(g),
            "mean_prob": float(g["prob"].mean()),
            "max_prob": float(g["prob"].max()),
            "mean_sz_bytes": float(g["sz_all_mean"].mean()),
            "mean_iat_s": float(g["iat_all_mean"].mean()),
        })
    grp = pd.DataFrame(grp_list).sort_values("n_flows", ascending=False)
    print(grp.to_string(index=False))

# ---------------------------------------------------------------------------
# Feature distribution comparison vs training val stats (if available)
# ---------------------------------------------------------------------------
print("\n=== FEATURE STATISTICS FOR OPENVPN LAB ===")
feat_stats = df[feat_order].describe().T
feat_stats.columns = ["count","mean","std","min","p25","p50","p75","max"]
print(feat_stats[["mean","std","min","p50","max"]].round(4).to_string())

# Look for any reference training CSV in demo_data
ref_dfs = {}
for ref_path in DEMO_DATA_DIR.glob("**/*.csv") if DEMO_DATA_DIR.exists() else []:
    try:
        r = pd.read_csv(ref_path)
        if all(c in r.columns for c in feat_order[:5]):  # check first 5 features
            ref_dfs[ref_path.name] = r
    except:
        pass

# Also check ALT_CAPTURES
for p in ALT_CAPTURES:
    if p.exists():
        try:
            r = pd.read_csv(p)
            if all(c in r.columns for c in feat_order[:5]):
                ref_dfs[p.name] = r
                print(f"[ref] Loaded alt capture: {p.name} ({len(r)} rows)")
        except:
            pass

# ---------------------------------------------------------------------------
# Distribution shift analysis
# ---------------------------------------------------------------------------
shift_records = []
openvpn_stats = df[feat_order].describe().T

for feat in feat_order:
    rec = {
        "feature": feat,
        "live_mean": float(df[feat].mean()),
        "live_std": float(df[feat].std()),
        "live_min": float(df[feat].min()),
        "live_max": float(df[feat].max()),
        "live_median": float(df[feat].median()),
    }
    # Compare against each ref capture
    for ref_name, ref_df in ref_dfs.items():
        if feat in ref_df.columns:
            rec[f"ref_{ref_name[:20]}_mean"] = float(ref_df[feat].mean())
    shift_records.append(rec)

shift_df = pd.DataFrame(shift_records)
shift_path = OUT_DIR / "openvpn_lab_distribution_shift.csv"
shift_df.to_csv(shift_path, index=False)
print(f"\n[saved] {shift_path}")

# ---------------------------------------------------------------------------
# Feature inspection markdown
# ---------------------------------------------------------------------------
now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
inspection_md = f"""# OpenVPN Lab Feature Inspection
Generated: {now_str}

## Summary
- **CSV**: `captures/vm_openvpn_lab_auto_features.csv`
- **Row count**: {len(df)}
- **Column count**: {len(df.columns)}
- **Missing model features**: {missing_feats or 'none'}
- **NaN in feature matrix**: {nan_count}
- **Inf in feature matrix**: {inf_count}

## Model Configuration
| Parameter | Value |
|-----------|-------|
| model_id | full_canonical__lgbm |
| review_threshold | {review_thr} |
| block_threshold | {block_thr} |
| session_aggregation | {agg_method} |
| session_grouping_column | {session_col} |
| probability_column | prob (raw LightGBM) |

## Flow Score Distribution
| Statistic | Value |
|-----------|-------|
| min | {p_arr.min():.6f} |
| p25 | {np.percentile(p_arr,25):.6f} |
| mean | {p_arr.mean():.6f} |
| p50 | {np.percentile(p_arr,50):.6f} |
| p75 | {np.percentile(p_arr,75):.6f} |
| p90 | {np.percentile(p_arr,90):.6f} |
| p95 | {np.percentile(p_arr,95):.6f} |
| max | {p_arr.max():.6f} |

## Action Counts (per flow)
| Action | Count | % |
|--------|-------|---|
| PASS | {(p_arr < review_thr).sum()} | {(p_arr < review_thr).mean()*100:.1f}% |
| FLAG_REVIEW | {((p_arr >= review_thr) & (p_arr < block_thr)).sum()} | {((p_arr >= review_thr) & (p_arr < block_thr)).mean()*100:.1f}% |
| SIMULATED_BLOCK | {(p_arr >= block_thr).sum()} | {(p_arr >= block_thr).mean()*100:.1f}% |

## Unique IP Addresses
"""
if "src_ip" in df.columns:
    all_ips = sorted(set(df["src_ip"].tolist()) | set(df["dst_ip"].tolist()))
    for ip in all_ips:
        inspection_md += f"- `{ip}`\n"

inspection_md += f"""
## Unique Protocols
{df['protocol'].value_counts().to_string() if 'protocol' in df.columns else 'N/A'}

## Column List
```
{chr(10).join(df.columns.tolist())}
```

## First 10 Rows (feature columns only)
```
{df[feat_order].head(10).round(4).to_string()}
```

## Feature Summary Statistics
```
{df[feat_order].describe().round(4).to_string()}
```
"""

insp_path = OUT_DIR / "openvpn_lab_feature_inspection.md"
insp_path.write_text(inspection_md, encoding="utf-8")
print(f"[saved] {insp_path}")

# ---------------------------------------------------------------------------
# Compare against val_stats from thresholds.json
# ---------------------------------------------------------------------------
val_stats = thresholds.get("val_stats", {})
print("\n=== COMPARISON vs VALIDATION SET STATISTICS ===")
print(f"  val benign p90 score:  {val_stats.get('benign_p90_score','N/A')}")
print(f"  val benign p95 score:  {val_stats.get('benign_p95_score','N/A')} <- review_threshold")
print(f"  val benign max score:  {val_stats.get('benign_max_score','N/A')} <- block_threshold")
print(f"  val vpn min score:     {val_stats.get('vpn_min_score','N/A')}")
print(f"  OpenVPN lab max score: {p_arr.max():.6f}")
print(f"  OpenVPN lab mean score:{p_arr.mean():.6f}")
print()
print("  Interpretation:")
if p_arr.max() < review_thr:
    print("  >> ALL flows score BELOW review_threshold.")
    print("  >> Model sees OpenVPN lab as MORE BENIGN than 95% of benign val sessions.")
    print("  >> This is a strong signal of OOD / domain shift / benign-like features.")
elif p_arr.max() < block_thr:
    print("  >> Some flows reach FLAG_REVIEW band.")
    print("  >> Model sees some signal but not enough for block.")
else:
    print("  >> Some flows reach SIMULATED_BLOCK. Thresholds may be applied correctly.")

# ---------------------------------------------------------------------------
# Feature importance (if model has it)
# ---------------------------------------------------------------------------
try:
    fi = model.feature_importances_
    fi_df = pd.DataFrame({"feature": feat_order, "importance": fi})
    fi_df = fi_df.sort_values("importance", ascending=False)
    print("\n=== TOP 10 FEATURE IMPORTANCES ===")
    print(fi_df.head(10).to_string(index=False))
    print()
    # For each top-10 feature, show live value vs what we'd expect for VPN
    print("=== LIVE VALUES FOR TOP FEATURES ===")
    for _, row in fi_df.head(10).iterrows():
        feat = row["feature"]
        live_vals = df[feat]
        print(f"  {feat:35s}: live mean={live_vals.mean():.4f} std={live_vals.std():.4f} "
              f"min={live_vals.min():.4f} max={live_vals.max():.4f}")
except Exception as e:
    print(f"[warn] Could not extract feature importances: {e}")

print("\n[done] All diagnostics complete.")
print(f"[done] Output directory: {OUT_DIR}")




