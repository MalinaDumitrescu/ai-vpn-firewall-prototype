from app.registry_loader import EXECUTABLE_FIREWALL_MODEL_ID, get_default_firewall_model_id, list_models, get_allowlisted_model_ids, load_inference_allowlist
print("=== Registry Loader Check ===")
print("EXECUTABLE_FIREWALL_MODEL_ID:", EXECUTABLE_FIREWALL_MODEL_ID)
print("get_default_firewall_model_id():", get_default_firewall_model_id())
print()
print("=== Models in registry ===")
models = list_models()
for mid, entry in models.items():
    print("  {}: role={} executable={} default={}".format(
        mid, entry.get("role","?"), entry.get("executable","?"), entry.get("default","?")))
print()
print("=== Allowlist ===")
alist = load_inference_allowlist()
print("default_firewall:", alist.get("default_firewall"))
for mid, info in alist.get("allowlist", {}).items():
    print("  {}: executable={}".format(mid, info.get("executable","?")))
print()
print("=== Engine load test ===")
from app.runtime_model_inference import get_engine
engine = get_engine(EXECUTABLE_FIREWALL_MODEL_ID)
print("Engine loaded:", engine.model_id)
print("Feature order:", engine.feature_order)
print("Thresholds:", engine.thresholds)
print("is_executable:", engine.is_executable)
print("is_default_firewall:", engine.is_default_firewall)
print()
print("=== Demo CSV inference ===")
from app.csv_service import load_demo_flows
df = load_demo_flows()
print("Demo CSV shape:", df.shape)
result = engine.run(df)
print("action_mode:", result["action_mode"])
print("production_readiness:", result["production_readiness"])
print("total_flows:", result["total_flows"])
print("total_sessions:", result["total_sessions"])
print("counts:", result["counts"])
print()
print("=== ALL CHECKS PASSED ===")

