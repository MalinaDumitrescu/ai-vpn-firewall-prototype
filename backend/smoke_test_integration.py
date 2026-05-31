"""Integration smoke test for unified_feature_contract_v2 bundle."""
from app.registry_loader import (
    EXECUTABLE_FIREWALL_MODEL_ID,
    get_default_firewall_model_id,
    is_executable,
    list_models,
    DEMO_FLOWS_UNIFIED_PATH,
    RUNTIME_MODELS_DIR,
    load_inference_allowlist,
)
from app.runtime_model_inference import RuntimeModelEngine
import pandas as pd

print("=== Integration Smoke Test: unified_feature_contract_v2 ===\n")

# 1. Constants
assert EXECUTABLE_FIREWALL_MODEL_ID == "unified_relative_shape_v2__lgbm", \
    f"Expected unified model, got {EXECUTABLE_FIREWALL_MODEL_ID}"
print(f"[OK] EXECUTABLE_FIREWALL_MODEL_ID = {EXECUTABLE_FIREWALL_MODEL_ID}")

# 2. Default firewall selector
default = get_default_firewall_model_id()
assert default == "unified_relative_shape_v2__lgbm", f"Default model wrong: {default}"
print(f"[OK] get_default_firewall_model_id() = {default}")

# 3. Executable check
assert is_executable("unified_relative_shape_v2__lgbm") is True
assert is_executable("full_canonical__lgbm") is False
assert is_executable("robust9_firewall") is False
print("[OK] is_executable() guards correct")

# 4. Demo CSV
assert DEMO_FLOWS_UNIFIED_PATH.exists(), f"Demo CSV missing: {DEMO_FLOWS_UNIFIED_PATH}"
print(f"[OK] unified_model_demo_flows.csv exists ({DEMO_FLOWS_UNIFIED_PATH})")

# 5. Model files
model_dir = RUNTIME_MODELS_DIR / "unified_relative_shape_v2__lgbm"
required_files = [
    "model.pkl", "calibrator.pkl", "feature_order.json",
    "thresholds.json", "runtime_loader_config.json",
    "extractor_config.json", "feature_contract.json", "feature_family.json",
]
for f in required_files:
    assert (model_dir / f).exists(), f"Missing: {model_dir / f}"
print(f"[OK] All {len(required_files)} model files present")

# 6. Registry entries
models = list_models()
unified = models["unified_relative_shape_v2__lgbm"]
assert unified["executable"] is True
assert unified["default"] is True
assert unified["comparison_only"] is False
assert unified["deployment_eligible"] is True
print("[OK] Registry: unified model marked executable=True, default=True")

fc = models["full_canonical__lgbm"]
assert fc["executable"] is False
assert fc["default"] is False
assert fc["comparison_only"] is True
print("[OK] Registry: full_canonical__lgbm marked legacy/non-executable")

# 7. Allowlist
alist = load_inference_allowlist()
assert alist["default_firewall"] == "unified_relative_shape_v2__lgbm"
unified_alist = alist["allowlist"]["unified_relative_shape_v2__lgbm"]
assert unified_alist["inference_permitted"] is True
assert unified_alist["executable"] is True
fc_alist = alist["allowlist"]["full_canonical__lgbm"]
assert fc_alist["inference_permitted"] is False
assert fc_alist["executable"] is False
print("[OK] Allowlist: unified model is inference_permitted, full_canonical is not")

# 8. Engine loads and runs
print("\n[...] Loading RuntimeModelEngine for unified_relative_shape_v2__lgbm ...")
engine = RuntimeModelEngine("unified_relative_shape_v2__lgbm")
assert engine.is_default_firewall is True
assert engine.is_executable is True
assert engine.is_comparison_only is False
assert len(engine.feature_order) == 12, f"Expected 12 features, got {len(engine.feature_order)}"
print(f"[OK] Engine loaded: {len(engine.feature_order)} features, prob_col={engine.probability_column}")

# 9. Inference on demo CSV
print("\n[...] Running inference on unified_model_demo_flows.csv ...")
df = pd.read_csv(DEMO_FLOWS_UNIFIED_PATH)
result = engine.run(df)
assert result["skipped"] is False, f"Inference skipped! Missing: {result.get('missing_features')}"
assert result["model_id"] == "unified_relative_shape_v2__lgbm"
assert result["default_firewall"] is True
assert result["comparison_only"] is False
assert result["total_flows"] > 0
assert result["total_sessions"] > 0
print(f"[OK] Inference complete: {result['total_flows']} flows, {result['total_sessions']} sessions")
print(f"     Counts: {result['counts']}")
print(f"     Action mode: {result['action_mode']}")

print("\n=== ALL CHECKS PASSED ===")
print(f"unified_relative_shape_v2__lgbm is now the active executable firewall model.")

