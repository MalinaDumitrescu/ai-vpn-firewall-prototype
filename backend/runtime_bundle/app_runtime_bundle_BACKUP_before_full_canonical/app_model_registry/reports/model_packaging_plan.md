# App Model Packaging Plan (Inventory + Capability Audit)

This is an inventory/capability audit only. No retraining and no artifact mutation were performed.

## Scope
- `artifacts/ensemble/diverse_bagging_robust9`
- `artifacts/balanced_bagging_firewall_tuned_ensemble`
- `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH`
- `artifacts/clean_pipeline/models`
- `artifacts/lood_firewall_tuned/hold_iscx`
- `artifacts/lood_firewall_tuned/hold_usbvpn`
- `artifacts/lood_firewall_tuned/hold_vnat`

## Capability Matrix (preliminary status)

| Artifact | Status | Inference | Calibrators | Prob cols | Split/Dataset/Label | Session grouping | Threshold computation | Feature order recoverable |
|---|---|---|---|---|---|---|---|---|
| `artifacts/ensemble/diverse_bagging_robust9` | policy_packaging_possible | live_inference_possible | iso/platt | raw/iso/platt | 1/1/1 | True | True | True |
| `artifacts/balanced_bagging_firewall_tuned_ensemble` | candidate_default | live_inference_possible | iso/platt | raw/iso/platt | 1/1/1 | True | True | True |
| `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH` | candidate_default | live_inference_possible | iso/platt | raw/iso/platt | 1/1/1 | True | True | True |
| `artifacts/clean_pipeline/models` | research_only | live_inference_possible | -/- | -/-/- | 0/1/1 | True | False | True |
| `artifacts/lood_firewall_tuned/hold_iscx` | negative_control | live_inference_possible | iso/platt | raw/iso/platt | 1/1/1 | True | True | True |
| `artifacts/lood_firewall_tuned/hold_usbvpn` | negative_control | live_inference_possible | iso/platt | raw/iso/platt | 1/1/1 | True | True | True |
| `artifacts/lood_firewall_tuned/hold_vnat` | negative_control | live_inference_possible | iso/platt | raw/iso/platt | 1/1/1 | True | True | True |

## Duplicate Hash Findings

### Prediction file duplicates
- `e9cd6e6eea2d0e9570d954499028ed3a`: `artifacts/balanced_bagging_firewall_tuned_ensemble/predictions.csv`, `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH/predictions.csv`

### Model file duplicates
- `21047d94a1d43d80fb4889f71aeccc55`: `artifacts/balanced_bagging_firewall_tuned_ensemble/model_cat_bag2.pkl`, `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH/model_cat_bag2.pkl`
- `57b8af34d4bb3240d01f16b3db51eb73`: `artifacts/balanced_bagging_firewall_tuned_ensemble/model_xgb_bag2.pkl`, `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH/model_xgb_bag2.pkl`
- `7c404f66c18d15e30cd84fac28936069`: `artifacts/balanced_bagging_firewall_tuned_ensemble/model_cat_bag0.pkl`, `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH/model_cat_bag0.pkl`
- `9684c28c90a0b6e494a67a525b96dc8d`: `artifacts/balanced_bagging_firewall_tuned_ensemble/isotonic_calibrator.pkl`, `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH/isotonic_calibrator.pkl`
- `a617475d93d5869c3fd48d36da493dc5`: `artifacts/balanced_bagging_firewall_tuned_ensemble/model_lgbm_bag0.pkl`, `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH/model_lgbm_bag0.pkl`
- `b294660405323aac98ee04eeecfe7b99`: `artifacts/balanced_bagging_firewall_tuned_ensemble/model_xgb_bag1.pkl`, `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH/model_xgb_bag1.pkl`
- `b7a44c04faf82955c16761461733a953`: `artifacts/balanced_bagging_firewall_tuned_ensemble/model_lgbm_bag1.pkl`, `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH/model_lgbm_bag1.pkl`
- `c3bae352f9bbcabfe339872327dc449c`: `artifacts/balanced_bagging_firewall_tuned_ensemble/model_xgb_bag0.pkl`, `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH/model_xgb_bag0.pkl`
- `ec8640857d5d15ea596930bb347823fb`: `artifacts/balanced_bagging_firewall_tuned_ensemble/platt_calibrator.pkl`, `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH/platt_calibrator.pkl`
- `f354c744834aff83494ed193aba5335b`: `artifacts/balanced_bagging_firewall_tuned_ensemble/model_lgbm_bag2.pkl`, `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH/model_lgbm_bag2.pkl`
- `fcd608874f3365efe8d08f5ac18302f1`: `artifacts/balanced_bagging_firewall_tuned_ensemble/model_cat_bag1.pkl`, `artifacts/balanced_bagging_firewall_tuned_ensemble_3dataset_REFRESH/model_cat_bag1.pkl`

## Notes
- `candidate_default` = policy-capable ensemble artifact likely suitable for app default evaluation.
- `policy_packaging_possible` = enough artifact content to compute/apply policy with additional packaging work.
- `policy_computation_possible` = thresholds/metrics computable but packaging completeness uncertain.
- `research_only` = useful for experiments; not currently app-policy-native.
- `negative_control` = held-out/LODO artifacts for robustness validation; not app defaults.
- `unsupported` = missing required pieces for policy/inference audit use.
