# Additional Model Packaging Plan (Task 9A — inspection only)

_This document is the result of a capability audit. No model has been packaged_
_and `backend/model_registry/registry.json` has not been modified._

`robust9_firewall` remains the only `default_firewall`. Nothing in this plan changes that.

## Summary table

| Candidate | n_features | trained_3ds | threshold_possible | real_inference | duplicate (preds) | recommended status |
|---|---:|:---:|:---:|:---:|:---|:---|
| `balanced_bagging_xgb_baseline` | 27 | True | True | True | — | `policy_computed` |
| `balanced_bagging_baseline` | 7 | True | True | True | — | `policy_computed` |
| `balanced_bagging_tuned_baseline` | 27 | True | True | True | — | `policy_computed` |
| `robust13_comparison` | 12 | True | True | True | — | `policy_computed` |
| `historical_2ds_backup` | 39 | False | True | True | — | `historical_reference` |
| `historical_3ds_degraded` | 7 | True | True | True | balanced_bagging_3ds_reference | `historical_reference` |
| `historical_pre_3ds_promotion` | 7 | True | True | True | — | `historical_reference` |

## Per-candidate findings

### `balanced_bagging_xgb_baseline`
- **Source**: `artifacts/balanced_bagging_xgb`
- **Reason**: true single-family XGBoost baseline
- **Historical-only flag**: False
- **Status (preliminary)**: `policy_computed`
- **Model files**: 3 (model_xgb_bag0.pkl, model_xgb_bag1.pkl, model_xgb_bag2.pkl)
- **Calibrators**: isotonic=True, platt=True
- **Feature order recovered**: True (n=27)
- **Probability columns**: ['prob_iso', 'prob_platt', 'prob_raw', 'prob', 'p_xgb_raw', 'p_lgbm_raw', 'p_cat_raw']
- **Splits / datasets present**: ['test', 'train', 'val'] / ['iscx', 'usbvpn', 'vnat']
- **Trained on all three datasets**: True
- **Threshold computation possible**: True
- **Real inference possible**: True
- **Duplicate of registry entry (by model bytes)**: None
- **Duplicate of registry entry (by predictions)**: None

### `balanced_bagging_baseline`
- **Source**: `artifacts/balanced_bagging`
- **Reason**: natural 3DS balanced bagging baseline
- **Historical-only flag**: False
- **Status (preliminary)**: `policy_computed`
- **Model files**: 9 (model_cat_bag0.pkl, model_cat_bag1.pkl, model_cat_bag2.pkl, model_lgbm_bag0.pkl, model_lgbm_bag1.pkl, model_lgbm_bag2.pkl, model_xgb_bag0.pkl, model_xgb_bag1.pkl, model_xgb_bag2.pkl)
- **Calibrators**: isotonic=True, platt=True
- **Feature order recovered**: True (n=7)
- **Probability columns**: ['prob_iso', 'prob_platt', 'prob_raw', 'prob', 'p_xgb_raw', 'p_lgbm_raw', 'p_cat_raw']
- **Splits / datasets present**: ['test', 'train', 'val'] / ['iscx', 'usbvpn', 'vnat']
- **Trained on all three datasets**: True
- **Threshold computation possible**: True
- **Real inference possible**: True
- **Duplicate of registry entry (by model bytes)**: None
- **Duplicate of registry entry (by predictions)**: None

### `balanced_bagging_tuned_baseline`
- **Source**: `artifacts/balanced_bagging_tuned`
- **Reason**: tuned sibling of balanced_bagging baseline
- **Historical-only flag**: False
- **Status (preliminary)**: `policy_computed`
- **Model files**: 9 (model_cat_bag0.pkl, model_cat_bag1.pkl, model_cat_bag2.pkl, model_lgbm_bag0.pkl, model_lgbm_bag1.pkl, model_lgbm_bag2.pkl, model_xgb_bag0.pkl, model_xgb_bag1.pkl, model_xgb_bag2.pkl)
- **Calibrators**: isotonic=True, platt=True
- **Feature order recovered**: True (n=27)
- **Probability columns**: ['prob_iso', 'prob_platt', 'prob_raw', 'prob', 'p_xgb_raw', 'p_lgbm_raw', 'p_cat_raw']
- **Splits / datasets present**: ['test', 'train', 'val'] / ['iscx', 'usbvpn', 'vnat']
- **Trained on all three datasets**: True
- **Threshold computation possible**: True
- **Real inference possible**: True
- **Duplicate of registry entry (by model bytes)**: None
- **Duplicate of registry entry (by predictions)**: None

### `robust13_comparison`
- **Source**: `artifacts/ensemble/diverse_bagging_robust13`
- **Reason**: direct 13-feature counterpart to robust9_firewall
- **Historical-only flag**: False
- **Status (preliminary)**: `policy_computed`
- **Model files**: 9 (model_cat_bag0.pkl, model_cat_bag1.pkl, model_cat_bag2.pkl, model_lgbm_bag0.pkl, model_lgbm_bag1.pkl, model_lgbm_bag2.pkl, model_xgb_bag0.pkl, model_xgb_bag1.pkl, model_xgb_bag2.pkl)
- **Calibrators**: isotonic=True, platt=True
- **Feature order recovered**: True (n=12)
- **Probability columns**: ['prob_iso', 'prob_platt', 'prob_raw', 'prob', 'p_xgb_raw', 'p_lgbm_raw', 'p_cat_raw']
- **Splits / datasets present**: ['test', 'train', 'val'] / ['iscx', 'usbvpn', 'vnat']
- **Trained on all three datasets**: True
- **Threshold computation possible**: True
- **Real inference possible**: True
- **Duplicate of registry entry (by model bytes)**: None
- **Duplicate of registry entry (by predictions)**: None

### `historical_2ds_backup`
- **Source**: `artifacts/balanced_bagging_firewall_tuned_ensemble_2dataset_backup`
- **Reason**: historical 2-dataset (iscx+vnat) ensemble snapshot
- **Historical-only flag**: True
- **Status (preliminary)**: `historical_reference`
- **Model files**: 9 (model_cat_bag0.pkl, model_cat_bag1.pkl, model_cat_bag2.pkl, model_lgbm_bag0.pkl, model_lgbm_bag1.pkl, model_lgbm_bag2.pkl, model_xgb_bag0.pkl, model_xgb_bag1.pkl, model_xgb_bag2.pkl)
- **Calibrators**: isotonic=True, platt=True
- **Feature order recovered**: True (n=39)
- **Probability columns**: ['prob_iso', 'prob_platt', 'prob_raw', 'prob', 'p_xgb_raw', 'p_lgbm_raw', 'p_cat_raw']
- **Splits / datasets present**: ['test', 'train', 'val'] / ['iscx', 'vnat']
- **Trained on all three datasets**: False
- **Threshold computation possible**: True
- **Real inference possible**: True
- **Duplicate of registry entry (by model bytes)**: None
- **Duplicate of registry entry (by predictions)**: None

### `historical_3ds_degraded`
- **Source**: `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_DEGRADED`
- **Reason**: historical degraded 3DS snapshot
- **Historical-only flag**: True
- **Status (preliminary)**: `historical_reference`
- **Model files**: 9 (model_cat_bag0.pkl, model_cat_bag1.pkl, model_cat_bag2.pkl, model_lgbm_bag0.pkl, model_lgbm_bag1.pkl, model_lgbm_bag2.pkl, model_xgb_bag0.pkl, model_xgb_bag1.pkl, model_xgb_bag2.pkl)
- **Calibrators**: isotonic=True, platt=True
- **Feature order recovered**: True (n=7)
- **Probability columns**: ['prob_iso', 'prob_platt', 'prob_raw', 'prob', 'p_xgb_raw', 'p_lgbm_raw', 'p_cat_raw']
- **Splits / datasets present**: ['test', 'train', 'val'] / ['iscx', 'usbvpn', 'vnat']
- **Trained on all three datasets**: True
- **Threshold computation possible**: True
- **Real inference possible**: True
- **Duplicate of registry entry (by model bytes)**: None
- **Duplicate of registry entry (by predictions)**: balanced_bagging_3ds_reference

### `historical_pre_3ds_promotion`
- **Source**: `artifacts/balanced_bagging_firewall_tuned_ensemble_PRE_3DS_PROMOTION`
- **Reason**: historical pre-promotion 3DS snapshot
- **Historical-only flag**: True
- **Status (preliminary)**: `historical_reference`
- **Model files**: 9 (model_cat_bag0.pkl, model_cat_bag1.pkl, model_cat_bag2.pkl, model_lgbm_bag0.pkl, model_lgbm_bag1.pkl, model_lgbm_bag2.pkl, model_xgb_bag0.pkl, model_xgb_bag1.pkl, model_xgb_bag2.pkl)
- **Calibrators**: isotonic=True, platt=True
- **Feature order recovered**: True (n=7)
- **Probability columns**: ['prob_iso', 'prob_platt', 'prob_raw', 'prob', 'p_xgb_raw', 'p_lgbm_raw', 'p_cat_raw']
- **Splits / datasets present**: ['test', 'train', 'val'] / ['iscx', 'usbvpn', 'vnat']
- **Trained on all three datasets**: True
- **Threshold computation possible**: True
- **Real inference possible**: True
- **Duplicate of registry entry (by model bytes)**: None
- **Duplicate of registry entry (by predictions)**: None

## Packaging plan — Task 9B

### A. Models recommended for packaging in Task 9B

Each must follow the same schema as existing registry entries
(`model_card.json`, `loader_config.json`, `feature_order.json`,
`calibration_info.json`, `thresholds.json`, `session_metrics.json`,
`policy_report.json`, `package_manifest.json`). None of these may be marked
`default_firewall`. Strict-action safety rules (R10) still apply.

- `balanced_bagging_xgb_baseline` — feature count 27, prob cols ['prob_iso', 'prob_platt', 'prob_raw', 'prob', 'p_xgb_raw', 'p_lgbm_raw', 'p_cat_raw'], datasets ['iscx', 'usbvpn', 'vnat'].
  - Status `policy_computed`, threshold_source = recomputed_from_validation, warning 'comparison-only, not deployment-approved'.
- `balanced_bagging_baseline` — feature count 7, prob cols ['prob_iso', 'prob_platt', 'prob_raw', 'prob', 'p_xgb_raw', 'p_lgbm_raw', 'p_cat_raw'], datasets ['iscx', 'usbvpn', 'vnat'].
  - Status `policy_computed`, threshold_source = recomputed_from_validation, warning 'comparison-only, not deployment-approved'.
- `balanced_bagging_tuned_baseline` — feature count 27, prob cols ['prob_iso', 'prob_platt', 'prob_raw', 'prob', 'p_xgb_raw', 'p_lgbm_raw', 'p_cat_raw'], datasets ['iscx', 'usbvpn', 'vnat'].
  - Status `policy_computed`, threshold_source = recomputed_from_validation, warning 'comparison-only, not deployment-approved'.
- `robust13_comparison` — feature count 12, prob cols ['prob_iso', 'prob_platt', 'prob_raw', 'prob', 'p_xgb_raw', 'p_lgbm_raw', 'p_cat_raw'], datasets ['iscx', 'usbvpn', 'vnat'].
  - Status `policy_computed`, threshold_source = recomputed_from_validation, warning 'comparison-only, not deployment-approved'.

### B. Models recommended for documentation-only (no package)

These are duplicates of existing registry entries (by predictions or model bytes)
or historical snapshots kept for provenance. They should be **listed in the registry**
in Task 9B as either `alias` (byte-identical / prediction-identical) or
`historical_reference` (separate binaries but no deployable role).

- `historical_2ds_backup` — historical snapshot → recommend `historical_reference` entry (no binaries copied to exports/runtime bundle)
- `historical_3ds_degraded` — prediction-identical to `balanced_bagging_3ds_reference` → recommend `alias` entry
- `historical_pre_3ds_promotion` — historical snapshot → recommend `historical_reference` entry (no binaries copied to exports/runtime bundle)

## Notes

- This script never modifies the on-disk artifacts; it only reads `.pkl` and
  `predictions.csv` files and computes SHA-256 hashes.
- Feature recovery uses the same logic as the robust9 packaging script: try
  CatBoost (`feature_names_`), then XGBoost (`get_booster().feature_names`),
  then LightGBM bag-0.
- `balanced_bagging_xgb_baseline` predictions contain `p_lgbm_raw` / `p_cat_raw`
  columns, but the artifact only ships XGB bag binaries. Real inference is
  therefore XGB-only; those extra columns must NOT be relied on in Task 9B's
  `loader_config.json`.
- Leakage / overlap checks (flow_id, capture_id split overlap) are deferred to
  Task 9B per the contract that this task is inspection-only.
