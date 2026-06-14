"""Final API smoke-test for the AI VPN Firewall Prototype backend."""
import urllib.request
import json
import sys

BASE = "http://localhost:8000"


def get(path):
    url = BASE + path
    try:
        r = urllib.request.urlopen(url, timeout=10)
        return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "reason": e.reason}, e.code
    except Exception as e:
        return {"error": str(e)}, 0


def section(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


failures = []

section("/health")
data, status = get("/health")
print(json.dumps(data, indent=2))
assert status == 200 and data.get("status") == "ok", "FAIL: health"
print("PASS")
section("/models  (all registered models)")
data, status = get("/models")
assert status == 200, f"FAIL: /models returned {status}"
# response is a dict keyed by model_id
if isinstance(data, dict):
    for mid, info in data.items():
        family = info.get("feature_family", info.get("family", "?"))
        eligible = info.get("deployment_eligible", "?")
        print(f"  {mid:35s}  deployment_eligible={eligible}  family={family}")
    print(f"\n  Total: {len(data)} model(s) registered")
else:
    for m in data:
        print(f"  {m}")
    print(f"\n  Total: {len(data)} model(s)")
print("PASS")

section("/models/default")
data, status = get("/models/default")
assert status == 200, f"FAIL: /models/default returned {status}"
print(json.dumps(data, indent=2))
print("PASS")

section("/models/robust9_firewall/policy")
data, status = get("/models/robust9_firewall/policy")
assert status == 200, f"FAIL: policy returned {status}"
print(json.dumps(data, indent=2))
print("PASS")

section("/models/full_canonical__lgbm/policy")
data, status = get("/models/full_canonical__lgbm/policy")
if status == 200:
    print(json.dumps(data, indent=2))
    print("PASS")
else:
    print(f"  WARNING: returned {status} – {data}")
    failures.append("full_canonical__lgbm policy")

section("/firewall/runtime-models")
data, status = get("/firewall/runtime-models")
assert status == 200, f"FAIL: runtime-models returned {status}"
print(json.dumps(data, indent=2))
print("PASS")

section("/firewall/live-ingest/state")
data, status = get("/firewall/live-ingest/state")
assert status == 200, f"FAIL: live-ingest/state returned {status}"
print(json.dumps(data, indent=2))
print("PASS")

section("/firewall/live-replay/state")
data, status = get("/firewall/live-replay/state")
assert status == 200, f"FAIL: live-replay/state returned {status}"
print(json.dumps(data, indent=2))
print("PASS")

section("/demo/allowed")
data, status = get("/demo/allowed")
assert status == 200, f"FAIL: demo/allowed returned {status}"
print(json.dumps(data, indent=2))
print("PASS")

section("/comparison/summary")
data, status = get("/comparison/summary")
assert status == 200, f"FAIL: comparison/summary returned {status}"
print(json.dumps(data, indent=2)[:800], "...")
print("PASS")

section("SUMMARY")
if failures:
    print(f"  {len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
else:
    print("  All API checks PASSED ✓")


