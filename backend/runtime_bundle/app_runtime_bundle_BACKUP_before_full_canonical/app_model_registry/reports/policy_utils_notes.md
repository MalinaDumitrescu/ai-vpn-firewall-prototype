# Policy Utils Sanity Notes (robust9)

This is a sanity-only utility test. No retraining and no artifact packaging were performed.

## Inputs
- predictions: `artifacts/ensemble/diverse_bagging_robust9/predictions.csv`
- task1 matrix: `reports/tables/app_model_capability_matrix.csv`
- task1 plan: `reports/model_packaging_plan.md`

## Detected capabilities
- available probability columns: `['prob_raw', 'prob_iso', 'prob_platt']`
- chosen probability column: `prob_raw`
- inferred session group column: `capture_id`
- wt5 verified: `True` (source: `src/deployment/decision_engine.py::_wt5_agg`)
- task1 preliminary status for robust9: `policy_packaging_possible`

## Leakage overlap check
- flow overlap train/val: `0`
- flow overlap train/test: `0`
- flow overlap val/test: `0`
- capture overlap train/val: `0`
- capture overlap train/test: `0`
- capture overlap val/test: `0`

## Output tables
- `reports/tables/policy_utils_sanity_check.csv`

## Sanity metrics summary

| Aggregation | Strict Recall/FPR | Balanced Recall/FPR | Session AUC |
|---|---:|---:|---:|
| `p80` | 0.9091/0.0000 | 0.9091/0.0000 | 0.9991 |
| `wt5` | 0.9091/0.0196 | 0.9091/0.0196 | 0.9906 |
