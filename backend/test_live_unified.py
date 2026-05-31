"""End-to-end test: live ingest, live replay, and CSV validation with unified model."""
import pandas as pd
import sys
sys.path.insert(0, ".")

# 1. Test live_ingest_service
from app.live_ingest_service import get_ingest_state, MODEL_ID, FEATURE_SCHEMA, REQUIRED_FEATURES

demo_df = pd.read_csv("runtime_bundle/app_runtime_bundle/demo_data/unified_model_demo_flows.csv")
state = get_ingest_state()
state.reset()

batch = demo_df.head(5).to_dict(orient="records")
result = state.ingest_batch(source="test", batch_id="batch_0001", flows=batch)

print("[live_ingest_service.ingest_batch]")
print(f"  model_id       = {result['model_id']}")
print(f"  feature_schema = {result['feature_schema']}")
print(f"  feature_count  = {result['feature_count']}")
print(f"  total_flows    = {result['total_flows']}")
print(f"  counts         = {result['counts']}")
assert result["model_id"] == "unified_relative_shape_v2__lgbm"
assert result["feature_schema"] == "unified_relative_shape_v2"
assert result["feature_count"] == 12
assert result["total_flows"] == 5
print("  [OK]")

# 2. Test that old-schema batch is rejected with clear error
try:
    old_batch = [{"sz_coef_variation": 0.1, "sz_mean_max": 500.0}]
    state.ingest_batch(source="test", batch_id="old_batch", flows=old_batch)
    print("  [FAIL] Should have raised ValueError for missing features")
    sys.exit(1)
except ValueError as e:
    msg = str(e)
    assert "unified_relative_shape_v2__lgbm" in msg, f"Expected model name in error: {msg}"
    assert "Missing" in msg or "missing" in msg
    print(f"  [OK] Old schema correctly rejected: {msg[:100]}")

# 3. Test live_replay_service
from app.live_replay_service import get_replay_state, TEMPLATE_HEADER, _UNIFIED_FEATURES

replay = get_replay_state()
csv_bytes = demo_df.to_csv(index=False).encode("utf-8")
meta = replay.load_csv(csv_bytes, "unified_demo.csv")
print(f"\n[live_replay_service.load_csv]")
print(f"  model_id       = {meta['model_id']}")
print(f"  total_rows     = {meta['total_rows']}")
assert meta["model_id"] == "unified_relative_shape_v2__lgbm"
assert meta["total_rows"] == len(demo_df)
print("  [OK]")

# Verify template header contains unified features
for feat in _UNIFIED_FEATURES:
    assert feat in TEMPLATE_HEADER, f"Missing feature in template: {feat}"
assert "sz_coef_variation" not in TEMPLATE_HEADER
assert "iat_all_mean" not in TEMPLATE_HEADER
print(f"  [OK] TEMPLATE_HEADER contains all 12 unified features, no old full_canonical extras")

# 4. Step replay
step_result = replay.step(batch_size=10)
print(f"\n[live_replay_service.step]")
print(f"  model_id       = {step_result['model_id']}")
print(f"  total_flows    = {step_result['total_flows_processed']}")
print(f"  counts         = {step_result['counts']}")
assert step_result["model_id"] == "unified_relative_shape_v2__lgbm"
print("  [OK]")

# 5. Validate the demo CSV with the validator
print("\n[validate_unified_model_csv]")
sys.path.insert(0, "../tools")
from validate_unified_model_csv import validate_csv
valid = validate_csv(
    "runtime_bundle/app_runtime_bundle/demo_data/unified_model_demo_flows.csv",
    model_id="unified_relative_shape_v2__lgbm",
    dry_inference=False,
)
assert valid is True
print("  [OK]")

print("\n=== ALL LIVE VM TESTS PASSED ===")

