#!/usr/bin/env python3
"""Test new benchmark and permissions endpoints."""
import urllib.request, urllib.error, json

BASE = "http://localhost:8000"

def get(path):
    r = urllib.request.urlopen(BASE + path)
    return json.loads(r.read())

# 1. /models/permissions
print("=== /models/permissions ===")
perms = get("/models/permissions")
for mid in ["full_canonical__lgbm", "robust9_firewall", "balanced_bagging_baseline",
            "balanced_bagging_xgb_baseline", "robust13_comparison", "lodo_hold_iscx"]:
    p = perms.get(mid, {})
    print(f"  {mid}:")
    print(f"    executable={p.get('executable')}, benchmark_compatible={p.get('benchmark_compatible')}, selectable_in_benchmark={p.get('selectable_in_benchmark')}")
    if p.get("reason_not_selectable"):
        print(f"    reason: {p.get('reason_not_selectable')}")
print(f"  total: {len(perms)} models")

# 2. /benchmark/compatible-csv/info
print("\n=== /benchmark/compatible-csv/info ===")
info = get("/benchmark/compatible-csv/info")
print(f"  compatible: {info.get('compatible_models')}")
print(f"  incompatible: {info.get('incompatible_models')}")
print(f"  firewall_model: {info.get('firewall_model')}")
print(f"  model_roles: {list(info.get('model_roles', {}).keys())}")

# 3. /benchmark/compatible-csv/bundled
print("\n=== /benchmark/compatible-csv/bundled ===")
try:
    d = get("/benchmark/compatible-csv/bundled")
    print(f"  benchmark_only: {d.get('benchmark_only')}")
    print(f"  models_run: {d.get('models_run')}")
    print(f"  models_skipped: {d.get('models_skipped')}")
    for m in d.get("per_model_results", []):
        print(f"  {m['model_id']}: exec={m.get('executable')}, bench_compat={m.get('benchmark_compatible')}, skipped={m.get('skipped')}")
        if not m.get("skipped"):
            counts = m.get("action_counts", {})
            print(f"    counts: {counts}")
except urllib.error.HTTPError as e:
    print(f"  HTTP {e.code}: {e.read()[:300].decode()}")

# 4. existing firewall endpoints still work
print("\n=== /firewall/demo (still full_canonical only) ===")
d = get("/firewall/demo")
print(f"  model_id: {d.get('model_id')}")
print(f"  counts: {d.get('counts')}")
print(f"  action_mode: {d.get('action_mode')}")

print("\nDONE")

