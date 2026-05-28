# Robust9 Firewall Packaging Summary

- Model ID: `robust9_firewall`
- Source artifact: `artifacts/ensemble/diverse_bagging_robust9`
- Package dir: `backend/model_registry/robust9_firewall`
- Registry entry status: **default_firewall**
- Status reason: All policy files generated; session policy available; no flow_id/capture_id overlap; feature order recovered.
- Recommended action mode: **simulation** (production_readiness=False)
- wt5 verified: `True` (source: `src/deployment/decision_engine.py::_wt5_agg`)

## Selected combination
- Probability column: `prob_iso`
- Aggregation: `p80`
- Session grouping: `capture_id`

## Thresholds (chosen on validation, evaluated on test)
- Strict threshold: `0.871795` (target benign FPR=0 on val)
- Balanced threshold: `0.871795` (target benign FPR<=0.01 on val)

## Test-set session metrics (selected combo)
- Session AUC: 0.9991087344028521
- Strict: recall=0.9091 fpr=0.0000 TP=20 FP=0 TN=102 FN=2
- Balanced: recall=0.9091 fpr=0.0000 TP=20 FP=0 TN=102 FN=2
- Review load (test): 0.0000  (n_block=20, n_flag=0)
- Per-dataset session AUC: `{"iscx": 1.0, "usbvpn": 1.0, "vnat": 1.0}`

## Safety flags
- Strict unsafe for blocking: **False**
- Balanced review-only: **False**

## Leakage checks (flow_id / capture_id overlap across train/val/test)
- flow_overlap_train_val: `0`
- flow_overlap_train_test: `0`
- flow_overlap_val_test: `0`
- capture_overlap_train_val: `0`
- capture_overlap_train_test: `0`
- capture_overlap_val_test: `0`

- Any overlap detected: **False**

## All (prob_col, aggregation) combinations evaluated
See: `reports/tables/robust9_policy_packaging_check.csv`

| prob_col | aggregation | strict_recall | strict_fpr | balanced_recall | balanced_fpr | session_auc |
|---|---|---:|---:|---:|---:|---:|
| prob_raw | p80 | 0.9091 | 0.0000 | 0.9091 | 0.0000 | 0.9991 |
| prob_raw | wt5 | 0.9091 | 0.0196 | 0.9091 | 0.0196 | 0.9906 |
| prob_iso | p80 | 0.9091 | 0.0000 | 0.9091 | 0.0000 | 0.9991 |
| prob_iso | wt5 | 0.9091 | 0.0196 | 0.9091 | 0.0196 | 0.9900 |
| prob_platt | p80 | 0.9091 | 0.0000 | 0.9091 | 0.0000 | 0.9982 |
| prob_platt | wt5 | 0.9091 | 0.0098 | 0.9091 | 0.0098 | 0.9848 |

## Package files written
- `backend/model_registry/robust9_firewall/model_card.json`
- `backend/model_registry/robust9_firewall/loader_config.json`
- `backend/model_registry/robust9_firewall/feature_order.json`
- `backend/model_registry/robust9_firewall/calibration_info.json`
- `backend/model_registry/robust9_firewall/thresholds.json`
- `backend/model_registry/robust9_firewall/session_metrics.json`
- `backend/model_registry/robust9_firewall/policy_report.json`
- `backend/model_registry/robust9_firewall/package_manifest.json`

## Registry
- `backend/model_registry/registry.json` updated with entry `robust9_firewall` (default_firewall).

_No source artifact was modified. No model was retrained._