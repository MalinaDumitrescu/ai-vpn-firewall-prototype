# Model Registry Validation Report

- Generated: 2026-05-26T10:57:16.158948+00:00
- Registry: `backend/model_registry/registry.json`
- Overall status: **PASS**
- Errors: **0**
- Warnings: **0**

## Rules checked
- R1: registry.json exists and is valid JSON
- R2: every listed package_dir exists (unless alias)
- R3: every non-alias model has model_card.json + loader_config.json
- R4: exactly one model has status default_firewall
- R5: negative_control => supports_firewall_actions=false
- R6: negative_control => supports_live_mode=false
- R7: policy_computed => warning contains 'comparison-only'
- R8: default_firewall / policy_packaged => thresholds.json, session_metrics.json, policy_report.json
- R9: nonzero flow/capture overlap => cannot be default_firewall or policy_packaged
- R10: strict.action=BLOCK requires strict test FPR == 0
- R11: balanced test FPR > 0.01 => balanced.action must be FLAG_REVIEW
- R12: byte-identical source artifacts must be aliases, not duplicate packages
- R13: LODO models must not be deployable
- R14: research_only must not have supports_firewall_actions=true

## Registry contents (per model)

| model_id | status | package_dir | source_artifact |
|---|---|---|---|
| `robust9_firewall` | default_firewall | `backend/model_registry/robust9_firewall` | `artifacts/ensemble/diverse_bagging_robust9` |
| `balanced_bagging_3ds_reference` | policy_computed | `backend/model_registry/balanced_bagging_3ds_reference` | `artifacts/balanced_bagging_firewall_tuned_ensemble` |
| `balanced_bagging_3ds_refresh` | alias | `backend/model_registry/balanced_bagging_3ds_refresh` | `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH` |
| `clean_pooled_benchmark` | policy_computed | `backend/model_registry/clean_pooled_benchmark` | `artifacts/clean_pipeline/models` |
| `twentyone_feature_experimental` | unsupported | `backend/model_registry/twentyone_feature_experimental` | `-` |
| `single_model_fallback` | policy_computed | `backend/model_registry/single_model_fallback` | `artifacts/clean_pipeline/models` |
| `lodo_hold_iscx` | negative_control | `backend/model_registry/lodo_hold_iscx` | `artifacts/lood_firewall_tuned/hold_iscx` |
| `lodo_hold_usbvpn` | negative_control | `backend/model_registry/lodo_hold_usbvpn` | `artifacts/lood_firewall_tuned/hold_usbvpn` |
| `lodo_hold_vnat` | negative_control | `backend/model_registry/lodo_hold_vnat` | `artifacts/lood_firewall_tuned/hold_vnat` |
| `balanced_bagging_xgb_baseline` | policy_computed | `backend/model_registry/balanced_bagging_xgb_baseline` | `artifacts/balanced_bagging_xgb` |
| `balanced_bagging_baseline` | policy_computed | `backend/model_registry/balanced_bagging_baseline` | `artifacts/balanced_bagging` |
| `balanced_bagging_tuned_baseline` | policy_computed | `backend/model_registry/balanced_bagging_tuned_baseline` | `artifacts/balanced_bagging_tuned` |
| `robust13_comparison` | policy_computed | `backend/model_registry/robust13_comparison` | `artifacts/ensemble/diverse_bagging_robust13` |
| `historical_3ds_degraded` | alias | `backend/model_registry/historical_3ds_degraded` | `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_DEGRADED` |

## Failures (errors)

_None._

## Outputs
- `reports/tables/model_registry_validation_errors.csv`
- `reports/model_registry_validation_report.md`
