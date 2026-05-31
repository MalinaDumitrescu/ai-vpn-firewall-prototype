"""Inspect the simultaneous_test_selected_models.csv training reference data."""
import pandas as pd
import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
CSV_PATH = PROJECT_ROOT / "backend/runtime_bundle/app_runtime_bundle/demo_data/simultaneous_test_selected_models.csv"
DEMO_CSV = PROJECT_ROOT / "backend/runtime_bundle/app_runtime_bundle/demo_data/demo_flows_full_canonical.csv"

print(f"Reading: {CSV_PATH}")
print(f"File size: {CSV_PATH.stat().st_size} bytes")

df = pd.read_csv(CSV_PATH, nrows=10)
print(f"\nColumns ({len(df.columns)}):")
for col in df.columns:
    print(f"  {col}")

print(f"\nShape (first 10 rows): {df.shape}")

target_feats = [
    'direction_balance_bytes', 'direction_balance_packets', 'dispersion_symmetry',
    'sz_all_mean', 'sz_all_std', 'sz_all_median', 'sz_all_p25', 'sz_all_p75',
    'iat_all_mean', 'iat_all_std', 'iat_all_p25', 'iat_all_median', 'iat_all_p75'
]

print("\n--- Feature values (first 10 rows) ---")
for feat in target_feats:
    if feat in df.columns:
        vals = df[feat].tolist()
        print(f"  {feat}: {vals}")
    else:
        print(f"  {feat}: NOT FOUND")

# Now load the full CSV and get stats
print("\n--- Loading full CSV for stats ---")
df_full = pd.read_csv(CSV_PATH)
print(f"Full shape: {df_full.shape}")

if 'label' in df_full.columns:
    print(f"Labels: {df_full['label'].value_counts().to_dict()}")

print("\n--- Feature statistics (full dataset) ---")
for feat in target_feats:
    if feat in df_full.columns:
        col = df_full[feat]
        print(f"  {feat}: min={col.min():.4g}  mean={col.mean():.4g}  max={col.max():.4g}  p50={col.median():.4g}")

if 'label' in df_full.columns:
    print("\n--- VPN (label=1) feature statistics ---")
    vpn = df_full[df_full['label'] == 1]
    benign = df_full[df_full['label'] == 0]
    print(f"VPN rows: {len(vpn)}, Benign rows: {len(benign)}")
    for feat in target_feats:
        if feat in df_full.columns:
            v = vpn[feat]
            b = benign[feat]
            print(f"  {feat}: VPN mean={v.mean():.4g} (min={v.min():.4g}, max={v.max():.4g}) | Benign mean={b.mean():.4g}")

