"""Run dry inference on all three live test CSVs and collect results for report."""
import sys
sys.path.insert(0, "backend")

import pandas as pd
from app.runtime_model_inference import get_engine

MODEL_ID = "unified_relative_shape_v2__lgbm"
engine = get_engine(MODEL_ID)

scenarios = [
    ("basic_benign",  "captures/test_unified_live.csv"),
    ("warp",          "captures/test_unified_warp.csv"),
    ("openvpn_lab",   "captures/test_unified_openvpn.csv"),
]

results = []
for name, csv_path in scenarios:
    df = pd.read_csv(csv_path)
    result = engine.run(df)
    scores = []
    for s in result["sessions"]:
        scores.append(s["session_score"])
    print(f"\n--- {name} ---")
    print(f"  CSV: {csv_path}")
    print(f"  rows extracted   : {result['total_flows']}")
    print(f"  sessions         : {result['total_sessions']}")
    print(f"  schema_valid     : {not result['skipped']}")
    print(f"  counts           : {result['counts']}")
    print(f"  session_scores   : {[round(s, 4) for s in scores]}")
    results.append((name, csv_path, result, scores))

print("\n=== SUMMARY ===")
for name, _, r, scores in results:
    print(f"  {name:20s}: flows={r['total_flows']:3d}  sessions={r['total_sessions']}  "
          f"PASS={r['counts']['PASS']} FLAG={r['counts']['FLAG_REVIEW']} BLOCK={r['counts']['BLOCK']}  "
          f"scores={[round(s,3) for s in scores]}")

