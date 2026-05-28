# AI-VPN-Firewall — Standalone Runtime Bundle

Generated: 2026-05-26T09:27:58.267098+00:00

## What this is

A self-contained bundle that lets a colleague run the FastAPI + React demo on another
machine without re-training anything and without needing the original dataset.
It contains:

- `app_model_registry/` — validated metadata registry (Task 7 output)
- `runtime_models/robust9_firewall/` — real model + calibrator binaries for the default firewall
- `demo_data/demo_flows.csv` — tiny sample CSV compatible with the robust9 feature order
- `requirements_runtime.txt` — runtime-only dependencies

## Inference scope

- **Only `robust9_firewall` supports real inference** in this bundle. Its 11 binary files
  (3 XGB bags + 3 LGBM bags + 3 CatBoost bags + isotonic + platt) live under
  `runtime_models/robust9_firewall/`.
- All other registry entries (balanced_bagging_3ds_*, clean_pooled_benchmark,
  single_model_fallback, twentyone_feature_experimental, lodo_hold_*) are
  **metadata / comparison-only**: they have no binaries in this bundle and must
  not be invoked for live scoring. The Model Comparison Lab can still show their
  recorded metrics from `app_model_registry/`.

## Safety & deployment posture

- **Blocking is simulation-only by default.** The backend must NEVER drop real
  packets unless an operator explicitly toggles live mode AND the active model
  has `supports_live_mode == true`. No entry in this bundle sets that flag.
- **No production readiness is claimed.** Every model card has
  `production_readiness: false`.
- **LODO failure:** the three `lodo_hold_*` negative-control entries collapse on
  their held-out dataset (session AUC ≈ 0.18–0.81). This is documented evidence
  that the project has not solved unseen-domain robustness. LODO models are
  registered as negative controls only and must never be deployable choices.

## Path rewriting

- `runtime_models/robust9_firewall/runtime_loader_config.json` contains paths
  rewritten to be **relative to this bundle root**. The backend should resolve
  model paths from that file. `rewrote_paths = True`.

## Demo data

- `demo_data/demo_flows.csv` — 16 flows across 2 sessions.
- Source: `data/processed/usbvpn/flows.parquet` (sz_cv derived as sz_all_std / sz_all_mean to match src/features/extract.py)
- Columns: `session_id, flow_id, dataset, label, sz_all_mean, sz_cv, sz_all_p25, sz_all_median, sz_all_p75, sz_mean_max, sz_mean_min, sz_std_max, sz_std_min`.
- Use it to verify end-to-end scoring before connecting to real traffic.

## How to install this bundle into the new app

Assume your new app repo is `ai-vpn-firewall-prototype/`. From this bundle root:

```
# 1) Copy the bundle into the backend folder of the new app
cp -r app_model_registry  ../ai-vpn-firewall-prototype/backend/
cp -r runtime_models      ../ai-vpn-firewall-prototype/backend/
cp -r demo_data           ../ai-vpn-firewall-prototype/backend/
cp requirements_runtime.txt ../ai-vpn-firewall-prototype/backend/

# 2) Install runtime dependencies in the new app environment
cd ../ai-vpn-firewall-prototype/backend
python -m venv .venv && . .venv/bin/activate     # or .venv\Scripts\Activate.ps1 on Windows
pip install -r requirements_runtime.txt

# 3) Point the FastAPI loader at the runtime config
#    backend/runtime_models/robust9_firewall/runtime_loader_config.json

# 4) Smoke-test by scoring demo_data/demo_flows.csv
```

## Files not included (by design)

- `notebooks/`
- `data/raw/` (PCAPs) and any training data
- `artifacts/` heavyweight contents other than the robust9 default model
- `_logs/`, evaluation dumps, ablations, leave-two-out, window-sensitivity, etc.
- Model binaries for non-default registry entries
