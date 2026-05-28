# App Runtime Bundle — Summary

- Generated: 2026-05-26T09:27:58.267098+00:00
- Bundle path: `exports/app_runtime_bundle`

## Pre-export validation

```
Validation: PASS  (errors=0, warnings=0)
```

## Model files included (default robust9_firewall ONLY)

- `runtime_models/robust9_firewall/isotonic_calibrator.pkl`
- `runtime_models/robust9_firewall/model_cat_bag0.pkl`
- `runtime_models/robust9_firewall/model_cat_bag1.pkl`
- `runtime_models/robust9_firewall/model_cat_bag2.pkl`
- `runtime_models/robust9_firewall/model_lgbm_bag0.pkl`
- `runtime_models/robust9_firewall/model_lgbm_bag1.pkl`
- `runtime_models/robust9_firewall/model_lgbm_bag2.pkl`
- `runtime_models/robust9_firewall/model_xgb_bag0.pkl`
- `runtime_models/robust9_firewall/model_xgb_bag1.pkl`
- `runtime_models/robust9_firewall/model_xgb_bag2.pkl`
- `runtime_models/robust9_firewall/platt_calibrator.pkl`

- `runtime_loader_config.json` written with rewritten paths (rewrote_paths=True): `runtime_models/robust9_firewall/runtime_loader_config.json`

## Demo CSV

- Path: `demo_data/demo_flows.csv`
- Flows: 16
- Sessions: 2
- Source: `data/processed/usbvpn/flows.parquet`
- Synthetic fallback used: **False**

## Files copied

- Total files: **124**
- Total size: **8,650,449 bytes**

## Excluded (by policy)

- `notebooks/`
- raw datasets (`data/raw/`)
- training data and `artifacts/` (beyond robust9)
- old logs / evaluation dumps
- model binaries for non-default registry entries

## Verification

- `app_model_registry/reports/model_registry_validation_report.md` shows the PASS gate.
- `RUNTIME_README.md` documents safety posture, install steps, and LODO disclaimer.
