#!/usr/bin/env python3
"""Full consistency audit script for AI VPN Firewall Prototype."""
import urllib.request, urllib.error, json, sys

BASE = "http://localhost:8000"

PASS_COUNT = 0
FAIL_COUNT = 0

def check(name, condition, detail=""):
    global PASS_COUNT, FAIL_COUNT
    if condition:
        print(f"  [PASS] {name}")
        PASS_COUNT += 1
    else:
        print(f"  [FAIL] {name}: {detail}")
        FAIL_COUNT += 1

def get(path):
    r = urllib.request.urlopen(BASE + path)
    return json.loads(r.read())

print("=" * 60)
print("  BACKEND AUDIT")
print("=" * 60)

# 1. Health
print("\n--- /health ---")
d = get("/health")
check("status == ok", d.get("status") == "ok", d.get("status"))

# 2. Default model
print("\n--- /models/default ---")
d = get("/models/default")
check("model_id == full_canonical__lgbm", d.get("model_id") == "full_canonical__lgbm", d.get("model_id"))
check("executable == true", d.get("executable") == True, d.get("executable"))
check("comparison_only == false", d.get("comparison_only") == False)
check("action_mode == simulation", d.get("action_mode") == "simulation", d.get("action_mode"))
check("production_ready == false", d.get("production_ready") == False, d.get("production_ready"))
check("n_features == 34", d.get("n_features") == 34, d.get("n_features"))
check("algorithm == lightgbm", d.get("algorithm") == "lightgbm", d.get("algorithm"))
check("probability_column == prob", d.get("selected_probability_column") == "prob", d.get("selected_probability_column"))
check("warning present", bool(d.get("warning")))

# 3. Runtime models – only full_canonical executable
print("\n--- /firewall/runtime-models ---")
models = get("/firewall/runtime-models")
fc = next((m for m in models if m["model_id"] == "full_canonical__lgbm"), None)
r9 = next((m for m in models if m["model_id"] == "robust9_firewall"), None)
check("full_canonical__lgbm in runtime models", fc is not None)
check("full_canonical executable == true", fc and fc.get("executable") == True)
check("full_canonical default_firewall == true", fc and fc.get("default_firewall") == True)
check("full_canonical comparison_only == false", fc and fc.get("comparison_only") == False)
check("full_canonical feature_count == 34", fc and fc.get("feature_count") == 34)
check("robust9 executable == false", r9 and r9.get("executable") == False)
check("robust9 comparison_only == true", r9 and r9.get("comparison_only") == True)
check("robust9 default_firewall == false", r9 and r9.get("default_firewall") == False)

# 4. Required features
print("\n--- /firewall/required-features ---")
d = get("/firewall/required-features")
feats = d.get("required_features", [])
check("34 features returned", len(feats) == 34, f"got {len(feats)}")
check("sz_coef_variation present", "sz_coef_variation" in feats)
check("iat_all_mean present", "iat_all_mean" in feats)
check("sz_cv present", "sz_cv" in feats)
check("model_id == full_canonical__lgbm", d.get("model_id") == "full_canonical__lgbm")

# 5. Firewall demo output
print("\n--- /firewall/demo ---")
d = get("/firewall/demo")
check("model_id == full_canonical__lgbm", d.get("model_id") == "full_canonical__lgbm")
check("action_mode == simulation", d.get("action_mode") == "simulation")
check("production_readiness == false", d.get("production_readiness") == False)
check("counts present", isinstance(d.get("counts"), dict))
counts = d.get("counts", {})
check("counts has PASS", "PASS" in counts)
check("counts has FLAG_REVIEW", "FLAG_REVIEW" in counts)
check("counts has BLOCK", "BLOCK" in counts)
if d.get("sessions"):
    s = d["sessions"][0]
    check("session has score", "session_score" in s or "score" in s)
    check("session has action", "action" in s)
    check("action is valid", s.get("action") in ("PASS", "FLAG_REVIEW", "BLOCK"))
    check("simulated flag present", "simulated" in s)

# 6. Live replay state
print("\n--- /firewall/live-replay/state ---")
d = get("/firewall/live-replay/state")
check("model_id == full_canonical__lgbm", d.get("model_id") == "full_canonical__lgbm")
check("executable == true", d.get("executable") == True)
check("comparison_only == false", d.get("comparison_only") == False)
check("action_mode == simulation", d.get("action_mode") == "simulation")

# 7. Live ingest state
print("\n--- /firewall/live-ingest/state ---")
d = get("/firewall/live-ingest/state")
check("recommended_model == full_canonical__lgbm", d.get("recommended_model") == "full_canonical__lgbm")
check("model_note present", bool(d.get("model_note")))
check("action_mode == simulation", d.get("action_mode") == "simulation")

# 8. Reject robust9 inference (selected_model_ids as query param)
print("\n--- /firewall/analyze-csv-multimodel with robust9_firewall (expect 400) ---")
csv_bytes = b"capture_id,sz_all_mean\n1,100\n"
body = (
    b"------testboundary\r\n"
    b'Content-Disposition: form-data; name="file"; filename="test.csv"\r\n'
    b"Content-Type: text/csv\r\n\r\n"
    + csv_bytes +
    b"\r\n------testboundary--\r\n"
)
req = urllib.request.Request(
    BASE + "/firewall/analyze-csv-multimodel?selected_model_ids=robust9_firewall",
    data=body,
    headers={"Content-Type": "multipart/form-data; boundary=----testboundary"},
    method="POST"
)
try:
    resp = urllib.request.urlopen(req)
    check("robust9 inference rejected (400)", False, f"Got 200: {resp.read()[:100]}")
except urllib.error.HTTPError as e:
    check("robust9 inference rejected (400)", e.code == 400, f"Got {e.code}")
    err = json.loads(e.read())
    check("rejection message mentions comparison-only", "comparison" in err.get("detail","").lower())

# 9. Comparison summary (read-only, should succeed)
print("\n--- /comparison/summary ---")
d = get("/comparison/summary")
check("comparison summary is list", isinstance(d, list))
check("has entries", len(d) > 0)

# 10. Full canonical policy
print("\n--- /models/full_canonical__lgbm/policy ---")
d = get("/models/full_canonical__lgbm/policy")
th = d.get("thresholds", {})
check("review_threshold == 0.02709", abs(th.get("review_threshold", 0) - 0.02709) < 1e-6)
check("block_threshold == 0.165365", abs(th.get("block_threshold", 0) - 0.165365) < 1e-6)
check("probability_column == prob", th.get("probability_column") == "prob")
check("simulation_only == true", th.get("simulation_only") == True)
check("production_ready == false", th.get("production_ready") == False)

print("\n" + "=" * 60)
print(f"  RESULT: {PASS_COUNT} passed, {FAIL_COUNT} failed")
print("=" * 60)
if FAIL_COUNT > 0:
    sys.exit(1)



