#!/usr/bin/env python
"""
Smoke test for the unified_feature_contract_v2 runtime export candidate.
Usage:
    python runtime_export/scripts/smoke_test_unified_model.py
Validates:
- All model artifact files load correctly
- feature_order.json contains expected 12 features
- thresholds.json contains review + block thresholds
- Zero-vector inference runs without error
- production_ready = False
- action_mode = simulation
- Demo CSV (unified_model_demo_flows.csv) scored with confusion output
"""
import sys
import json
import joblib
import numpy as np
from pathlib import Path
SCRIPT_DIR = Path(__file__).resolve().parent
BASE       = SCRIPT_DIR.parent / "runtime_models" / "unified_relative_shape_v2__lgbm"
DEMO_DIR   = SCRIPT_DIR.parent / "demo_data"
REGISTRY   = SCRIPT_DIR.parent / "app_model_registry" / "unified_firewall_candidate.json"
N_FEATURES_EXPECTED = 12
MODEL_ID   = "unified_relative_shape_v2__lgbm"
PASS_MARK = "[smoke_test]"
errors = []
def check(condition, msg):
    if not condition:
        errors.append(f"  FAIL: {msg}")
    return condition
# ── 1. Load artifacts ─────────────────────────────────────────────────────
print(f"{PASS_MARK} Loading artifacts from: {BASE}")
clf = None
try:
    clf = joblib.load(BASE / "model.pkl")
    print(f"{PASS_MARK} model.pkl            OK  (type={type(clf).__name__})")
except Exception as e:
    errors.append(f"  FAIL: model.pkl: {e}")
iso = None
try:
    iso = joblib.load(BASE / "calibrator.pkl")
    print(f"{PASS_MARK} calibrator.pkl       OK  (type={type(iso).__name__})")
except Exception as e:
    errors.append(f"  FAIL: calibrator.pkl: {e}")
features = []
try:
    feat_data = json.load(open(BASE / "feature_order.json"))
    features  = feat_data["features"]
    print(f"{PASS_MARK} feature_order.json   OK  ({len(features)} features)")
    check(len(features) == N_FEATURES_EXPECTED,
          f"expected {N_FEATURES_EXPECTED} features, got {len(features)}")
except Exception as e:
    errors.append(f"  FAIL: feature_order.json: {e}")
review_thr, block_thr = 0.05, 0.5
try:
    thr = json.load(open(BASE / "thresholds.json"))
    review_thr = thr["review_threshold"]
    block_thr  = thr["block_threshold"]
    print(f"{PASS_MARK} thresholds.json      OK  (review={review_thr:.4f}, block={block_thr:.4f})")
except Exception as e:
    errors.append(f"  FAIL: thresholds.json: {e}")
try:
    ext_cfg = json.load(open(BASE / "extractor_config.json"))
    print(f"{PASS_MARK} extractor_config.json OK (version={ext_cfg['extractor_version']})")
except Exception as e:
    errors.append(f"  FAIL: extractor_config.json: {e}")
# ── 2. Registry metadata ──────────────────────────────────────────────────
try:
    reg = json.load(open(REGISTRY))
    prod_ready  = reg["production_ready"]
    action_mode = reg["action_mode"]
    check(not prod_ready,              "production_ready should be False")
    check(action_mode == "simulation", "action_mode should be simulation")
    print(f"{PASS_MARK} production_ready     = {prod_ready}")
    print(f"{PASS_MARK} action_mode          = {action_mode}")
except Exception as e:
    errors.append(f"  FAIL: registry JSON: {e}")
# ── 3. Zero-vector inference ──────────────────────────────────────────────
if clf is not None and iso is not None and features:
    try:
        import pandas as pd
        X_zero = pd.DataFrame(np.zeros((1, len(features))), columns=features)
        p_raw  = clf.predict_proba(X_zero)[0, 1]
        p_cal  = float(iso.predict([p_raw])[0])
        if   p_cal >= block_thr:  act = "SIMULATED_BLOCK"
        elif p_cal >= review_thr: act = "FLAG_REVIEW"
        else:                     act = "PASS"
        print(f"{PASS_MARK} Zero-vector inference: raw={p_raw:.4f}  calibrated={p_cal:.4f}  action={act}")
    except Exception as e:
        errors.append(f"  FAIL: zero-vector inference: {e}")
# ── 4. Feature list ────────────────────────────────────────────────────────
if features:
    print(f"{PASS_MARK} Required features ({len(features)}):")
    for f in features:
        print(f"    {f}")
# ── 5. Demo CSV ────────────────────────────────────────────────────────────
preferred  = DEMO_DIR / "unified_model_demo_flows.csv"
demo_csvs  = [preferred] if preferred.exists() else sorted(DEMO_DIR.glob("*.csv"))
if demo_csvs:
    try:
        import pandas as pd
        from collections import Counter
        demo_path = demo_csvs[0]
        df = pd.read_csv(demo_path)
        print(f"\n{PASS_MARK} Demo CSV: {demo_path.name}  ({len(df)} rows)")
        missing = [f for f in features if f not in df.columns]
        if missing:
            errors.append(f"  FAIL: demo CSV missing columns: {missing}")
        else:
            X_demo = df[features].values
            p_raw  = clf.predict_proba(X_demo)[:, 1]
            p_cal  = iso.predict(p_raw)
            actions = []
            for p in p_cal:
                if   p >= block_thr:  actions.append("SIMULATED_BLOCK")
                elif p >= review_thr: actions.append("FLAG_REVIEW")
                else:                 actions.append("PASS")
            cnt = Counter(actions)
            print(f"{PASS_MARK} Inference results ({len(df)} rows):")
            for act, n in sorted(cnt.items()):
                print(f"    {act}: {n} flows")
            # Label-aware confusion
            if "label" in df.columns:
                df2 = df.copy()
                df2["_decision"] = actions
                vpn = df2[df2["label"] == 1]
                ben = df2[df2["label"] == 0]
                TP = int((vpn["_decision"] == "SIMULATED_BLOCK").sum())
                FN = int(len(vpn) - TP)
                TN = int((ben["_decision"] == "PASS").sum())
                FP = int(len(ben) - TN)
                print(f"{PASS_MARK} Confusion (label-aware):")
                print(f"    TP={TP}  FN={FN}  TN={TN}  FP={FP}")
                if len(vpn) > 0:
                    print(f"    VPN recall @ block threshold: {TP/len(vpn):.3f}  ({len(vpn)} VPN flows)")
                if len(ben) > 0:
                    print(f"    Benign FPR:                   {FP/len(ben):.3f}  ({len(ben)} benign flows)")
    except Exception as e:
        errors.append(f"  FAIL: demo CSV inference: {e}")
else:
    print(f"\n{PASS_MARK} No demo CSV in demo_data/ - skipping demo inference.")
    print(f"{PASS_MARK} Demo CSV should be generated in the next phase.")
# ── 6. Final verdict ──────────────────────────────────────────────────────
print()
if errors:
    print(f"{PASS_MARK} *** SMOKE TEST FAILED ***")
    for err in errors:
        print(err)
    sys.exit(1)
else:
    print(f"{PASS_MARK} PASSED - all artifact checks OK")
    print(f"{PASS_MARK} production_ready = False   action_mode = simulation")
    print(f"{PASS_MARK} Model: {MODEL_ID}")
    print(f"{PASS_MARK} Features: {len(features)}   review_thr={review_thr:.4f}   block_thr={block_thr:.4f}")
