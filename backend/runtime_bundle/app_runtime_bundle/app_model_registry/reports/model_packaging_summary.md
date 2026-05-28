# App Model Packaging Summary (Task 4)

Read-only packaging of reference and research comparison models. No retraining performed.
**No model in this task is marked `default_firewall`** (the existing `robust9_firewall` entry from Task 3 remains the default).

- Generated: 2026-05-23T13:08:56.440600+00:00
- wt5 verified: `True` (source: `src/deployment/decision_engine.py::_wt5_agg`)

## Registry entries created/updated

| model_id | status | source_artifact | prob | agg | strict R/FPR | bal R/FPR | sess AUC | overlap |
|---|---|---|---|---|---|---|---|---|
| `balanced_bagging_3ds_reference` | policy_computed | `artifacts/balanced_bagging_firewall_tuned_ensemble` | prob_raw | wt5 | 0.4000/0.0000 | 0.4000/0.0000 | 0.9505 | False |
| `balanced_bagging_3ds_refresh` | alias | `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH` | - | - | n/a/n/a | n/a/n/a | n/a | None |
| `clean_pooled_benchmark` | policy_computed | `artifacts/clean_pipeline/models` | ensemble_score | p80 | 1.0000/0.1250 | 0.7313/0.0000 | 0.9988 | False |
| `twentyone_feature_experimental` | unsupported | `-` | - | - | n/a/n/a | n/a/n/a | n/a | None |
| `single_model_fallback` | policy_computed | `artifacts/clean_pipeline/models` | xgb_score | p80 | 1.0000/0.0417 | 0.7761/0.0000 | 1.0000 | False |

## Notes
- All thresholds for `policy_computed` entries are `threshold_source = recomputed_from_validation`.
- `balanced_bagging_3ds_refresh` is registered as an **alias** of `balanced_bagging_3ds_reference` because the source artifacts are byte-identical (Task 1 finding).
- `twentyone_feature_experimental` is registered as **unsupported** because no recoverable 21-feature artifact exists in the workspace.
- `clean_pooled_benchmark` and `single_model_fallback` are **comparison-only** and not deployment-approved.

## Per-model packaging check CSVs
- `reports/tables/balanced_bagging_3ds_reference_policy_packaging_check.csv`
- `reports/tables/clean_pooled_benchmark_policy_packaging_check.csv`
- `reports/tables/single_model_fallback_policy_packaging_check.csv`

## Outputs
- `reports/tables/app_model_registry_summary.csv`
- `reports/tables/app_model_policy_comparison.csv`
- `reports/tables/app_model_capability_matrix.csv` (augmented in place)
- `backend/model_registry/registry.json`

## Task 5 — LODO Negative Controls (non-deployable)

Generated: 2026-05-23T13:12:53.305464+00:00

LODO models are packaged as **negative controls only** to provide cross-dataset robustness evidence. They are explicitly marked `deployable=false`, `supports_firewall_actions=false`, `supports_live_mode=false`, and must NOT be exposed in the application's Firewall Mode. Any thresholds shown are recomputed from validation and provided for reporting only.

| model_id | held_out | prob | agg | strict R/FPR | bal R/FPR | sess AUC | per-dataset test AUC | overlap |
|---|---|---|---|---|---|---|---|---|
| `lodo_hold_iscx` | iscx | prob_iso | p80 | 0.0000/0.0000 | 0.0000/0.0000 | 0.5623 | `{"iscx": 0.5622965374371116}` | False |
| `lodo_hold_usbvpn` | usbvpn | prob_platt | wt5 | 0.0435/0.0000 | 0.0435/0.0000 | 0.8134 | `{"usbvpn": 0.8134321612582481}` | False |
| `lodo_hold_vnat` | vnat | prob_platt | p80 | 0.0000/0.0000 | 0.0000/0.0000 | 0.1759 | `{"vnat": 0.17590361445783131}` | False |

**Banner written into every LODO policy_report.json**: _Negative control / LODO stress-test model. Not deployable._

Outputs:
- `reports/tables/lodo_negative_control_summary.csv`
- `backend/model_registry/lodo_hold_iscx/`
- `backend/model_registry/lodo_hold_usbvpn/`
- `backend/model_registry/lodo_hold_vnat/`
- per-model packaging-check CSVs under `reports/tables/`

## Task 9B — Additional comparison models

Generated: 2026-05-26T07:57:32.235218+00:00

Read-only packaging of four additional comparison candidates approved by Task 9A. `robust9_firewall` remains the only `default_firewall`. All new entries are `policy_computed`, simulation-only, and carry the warning `"comparison-only, not deployment-approved"`.

| model_id | source_artifact | prob | agg | strict R/FPR | bal R/FPR | sess AUC | strict action |
|---|---|---|---|---|---|---|---|
| `balanced_bagging_xgb_baseline` | `artifacts/balanced_bagging_xgb` | prob_raw | wt5 | 0.0909/0.0000 | 0.6818/0.0000 | 0.9710 | `BLOCK` |
| `balanced_bagging_baseline` | `artifacts/balanced_bagging` | prob_raw | p80 | 0.2000/0.0000 | 0.2000/0.0000 | 0.9307 | `BLOCK` |
| `balanced_bagging_tuned_baseline` | `artifacts/balanced_bagging_tuned` | prob_iso | wt5 | 0.1818/0.0098 | 0.1818/0.0098 | 0.9679 | `DISABLED_DO_NOT_BLOCK` |
| `robust13_comparison` | `artifacts/ensemble/diverse_bagging_robust13` | prob_platt | wt5 | 0.0909/0.0000 | 0.7273/0.0000 | 0.9389 | `BLOCK` |

**`historical_3ds_degraded`** — alias-only documentation entry pointing to `balanced_bagging_3ds_reference`. Predictions are byte-identical to the reference. `supports_firewall_actions=false`, `supports_live_mode=false`, `deployable=false`.

### Audit-specific notes (per task spec)

- `balanced_bagging_xgb_baseline`: artifact ships only `model_xgb_bag*.pkl`. `loader_config.json` exposes XGB bags only; the `p_lgbm_raw`/`p_cat_raw` columns in `predictions.csv` are inherited from the shared schema and are **not** treated as runnable model families.
- `robust13_comparison`: Task 9A recovered **12** features from CatBoost, not 13. Package keeps `model_id = robust13_comparison` for naming continuity but records `feature_count = 12` and `feature_count_note` explaining the discrepancy. No 13th feature is invented.
- `historical_2ds_backup` and `historical_pre_3ds_promotion` are NOT packaged in this task (per spec).

### Per-combo check CSVs

- `reports/tables/balanced_bagging_xgb_baseline_policy_packaging_check.csv`
- `reports/tables/balanced_bagging_baseline_policy_packaging_check.csv`
- `reports/tables/balanced_bagging_tuned_baseline_policy_packaging_check.csv`
- `reports/tables/robust13_comparison_policy_packaging_check.csv`
