"""Dry-run integration test for POST /firewall/live-ingest with full_canonical_34 features.

Usage (backend must be running on 127.0.0.1:8765):
    python tools/test_live_ingest_full_canonical.py

Optional args:
    --host  http://127.0.0.1:8765   backend base URL
    --csv   captures/vm_basic_benign_features.csv  path to flow CSV
    --rows  4                       number of rows to POST (0 = all)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

try:
    import requests
except ImportError:
    sys.exit("requests not installed. Run: pip install requests")

try:
    import pandas as pd
except ImportError:
    sys.exit("pandas not installed. Run: pip install pandas")



DEFAULT_HOST = "http://127.0.0.1:8765"
DEFAULT_CSV  = REPO_ROOT / "captures" / "vm_basic_benign_features.csv"
INGEST_URL   = "{host}/firewall/live-ingest"
STATE_URL    = "{host}/firewall/live-ingest/state"
RESET_URL    = "{host}/firewall/live-ingest/reset"

REQUIRED_FEATURES = [
    "sz_coef_variation", "sz_p25_median_ratio", "sz_p75_median_ratio",
    "sz_iqr_norm_median", "dispersion_symmetry",
    "direction_balance_bytes", "direction_balance_packets",
    "sz_mean_max", "sz_mean_min", "sz_std_max", "sz_std_min",
    "iat_all_mean", "iat_all_std", "iat_all_p25", "iat_all_median",
    "iat_all_p75", "iat_mean_max", "iat_mean_min", "iat_std_max",
    "iat_std_min", "sz_all_mean", "sz_all_std", "sz_all_median",
    "sz_all_p25", "sz_all_p75", "sz_cv", "sz_iqr", "sz_qratio",
    "sz_median_to_mean", "iat_iqr", "iat_cv", "iat_median",
    "iat_p25", "iat_p75",
]


def _pretty(obj: dict) -> str:
    return json.dumps(obj, indent=2, default=str)


def run_test(host: str, csv_path: Path, n_rows: int) -> int:
    """Run the test. Returns 0 on success, 1 on failure."""
    print(f"\n{'='*60}")
    print(f"  Live Ingest Full-Canonical Test")
    print(f"  Backend : {host}")
    print(f"  CSV     : {csv_path}")
    print(f"  Rows    : {'all' if n_rows == 0 else n_rows}")
    print(f"{'='*60}\n")

    try:
        r = requests.get(f"{host}/health", timeout=5)
        r.raise_for_status()
        print(f"[OK] Backend /health → {r.json()}")
    except Exception as exc:
        print(f"[FAIL] Backend not reachable at {host}: {exc}")
        return 1

    if not csv_path.exists():
        print(f"[FAIL] CSV not found: {csv_path}")
        return 1

    df = pd.read_csv(csv_path)
    print(f"[OK] Loaded CSV: {len(df)} rows × {len(df.columns)} columns")

    missing = [f for f in REQUIRED_FEATURES if f not in df.columns]
    if missing:
        print(f"[FAIL] CSV is missing {len(missing)} required features: {missing}")
        return 1
    print(f"[OK] All 34 full_canonical features present in CSV")

    if n_rows > 0:
        df = df.head(n_rows)
    print(f"[INFO] Using {len(df)} rows for POST")

    flows = []
    for _, row in df.iterrows():
        flow = {}
        for col in df.columns:
            val = row[col]
            try:
                val = val.item()
            except AttributeError:
                pass
            flow[col] = val
        flows.append(flow)

    print(f"[INFO] First row keys (first 8): {list(flows[0].keys())[:8]}")

    r = requests.post(RESET_URL.format(host=host), timeout=10)
    print(f"[INFO] Reset response: {r.status_code} {r.json().get('message','')}")

    payload = {
        "source": "test_live_ingest_full_canonical",
        "batch_id": "test_batch_0001",
        "feature_schema": "full_canonical_34",
        "flows": flows,
    }

    print(f"\n[POST] {INGEST_URL.format(host=host)}")
    try:
        r = requests.post(
            INGEST_URL.format(host=host),
            json=payload,
            timeout=30,
        )
    except Exception as exc:
        print(f"[FAIL] POST failed: {exc}")
        return 1

    print(f"[INFO] HTTP status: {r.status_code}")
    try:
        resp = r.json()
    except Exception:
        print(f"[FAIL] Could not parse response JSON. Raw: {r.text[:500]}")
        return 1

    if r.status_code != 200:
        print(f"[FAIL] Expected 200, got {r.status_code}")
        print(_pretty(resp))
        return 1

    print(f"\n[OK] POST /firewall/live-ingest → 200")
    print(f"\n--- Response summary ---")
    for key in [
        "received_flows", "total_flows", "total_sessions",
        "model_id", "feature_schema", "feature_count",
        "counts", "labelled_counts",
    ]:
        print(f"  {key}: {resp.get(key)}")

    failures = []

    if resp.get("model_id") != "full_canonical__lgbm":
        failures.append(f"model_id expected 'full_canonical__lgbm', got '{resp.get('model_id')}'")

    if resp.get("feature_schema") != "full_canonical_34":
        failures.append(f"feature_schema expected 'full_canonical_34', got '{resp.get('feature_schema')}'")

    if resp.get("received_flows") != len(flows):
        failures.append(f"received_flows expected {len(flows)}, got {resp.get('received_flows')}")

    if resp.get("total_flows") != len(flows):
        failures.append(f"total_flows expected {len(flows)}, got {resp.get('total_flows')}")

    if resp.get("total_sessions", 0) < 1:
        failures.append(f"total_sessions expected >= 1, got {resp.get('total_sessions')}")

    sessions = resp.get("active_sessions", [])
    if sessions:
        print(f"\n--- Active sessions ({len(sessions)}) ---")
        for s in sessions:
            print(
                f"  session={s.get('session_id')} "
                f"n_flows={s.get('n_flows')} "
                f"score={s.get('session_score')} "
                f"action={s.get('action')} "
                f"label={s.get('label')}"
            )
    else:
        failures.append("active_sessions is empty — sessions should have been created")

    r2 = requests.get(STATE_URL.format(host=host), timeout=10)
    state = r2.json()
    print(f"\n--- /live-ingest/state ---")
    for key in ["total_flows", "total_sessions", "model_id", "feature_schema"]:
        print(f"  {key}: {state.get(key)}")

    print()
    if failures:
        print(f"[FAIL] {len(failures)} assertion(s) failed:")
        for f in failures:
            print(f"  ✗ {f}")
        return 1
    else:
        print("[PASS] All assertions passed ✓")
        print()
        print("Acceptance criteria met:")
        print(f"  ✓ POST /firewall/live-ingest returned 200")
        print(f"  ✓ received_flows = {resp.get('received_flows')}")
        print(f"  ✓ total_flows = {resp.get('total_flows')}")
        print(f"  ✓ total_sessions = {resp.get('total_sessions')}")
        print(f"  ✓ model_id = {resp.get('model_id')}")
        print(f"  ✓ feature_schema = {resp.get('feature_schema')}")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Test /firewall/live-ingest with full_canonical_34 CSV")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Backend base URL")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Path to flow CSV")
    parser.add_argument("--rows", type=int, default=0, help="Number of rows to send (0=all)")
    args = parser.parse_args()

    code = run_test(host=args.host, csv_path=Path(args.csv), n_rows=args.rows)
    sys.exit(code)


if __name__ == "__main__":
    main()

