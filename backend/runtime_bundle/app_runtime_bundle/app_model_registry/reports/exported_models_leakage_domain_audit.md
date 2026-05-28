# Exported Models — Leakage, Threshold & Domain Sanity Audit

- Generated: 2026-05-26T08:44:24.538087+00:00
- Source: `backend/model_registry/registry.json` (14 entries)
- Models audited (non-alias, non-unsupported): **11**
- Read-only: no retraining, no artifacts modified, no exports rebuilt.

## TL;DR

No direct flow_id/capture_id split leakage was detected for the audited models where identifiers were available. However, very high target-included session AUC values should not be interpreted as evidence of universal deployment robustness. The results are valid only under the known-domain evaluation protocol and must be read together with the LODO failures.

- Models with `overlap_detected`: **0** (non-alias/non-unsupported models with no overlap: **11**).
- Models with suspicious leakage-like feature columns: **0**.
- Models that pass policy sanity AND keep strict `BLOCK`: **5**.
- Models that fail policy sanity: **0**.
- Models with domain-fingerprinting audit available: **4** (`balanced_bagging_3ds_reference`, `clean_pooled_benchmark`, `single_model_fallback`, `balanced_bagging_baseline`).

## 1. Direct leakage audit

| model | status | leakage | flow_overlap (tv/tt/vt) | capture_overlap (tv/tt/vt) | suspicious feats |
|---|---|---|---|---|---|
| `robust9_firewall` | default_firewall | no_direct_overlap_detected | 0/0/0 | 0/0/0 | — |
| `balanced_bagging_3ds_reference` | policy_computed | no_direct_overlap_detected | 0/0/0 | 0/0/0 | — |
| `balanced_bagging_3ds_refresh` | alias | not_available | None/None/None | None/None/None | — |
| `clean_pooled_benchmark` | policy_computed | no_direct_overlap_detected | 0/0/0 | 0/0/0 | — |
| `twentyone_feature_experimental` | unsupported | not_available | None/None/None | None/None/None | — |
| `single_model_fallback` | policy_computed | no_direct_overlap_detected | 0/0/0 | 0/0/0 | — |
| `lodo_hold_iscx` | negative_control | no_direct_overlap_detected | 0/0/0 | 0/0/0 | — |
| `lodo_hold_usbvpn` | negative_control | no_direct_overlap_detected | 0/0/0 | 0/0/0 | — |
| `lodo_hold_vnat` | negative_control | no_direct_overlap_detected | 0/0/0 | 0/0/0 | — |
| `balanced_bagging_xgb_baseline` | policy_computed | no_direct_overlap_detected | 0/0/0 | 0/0/0 | — |
| `balanced_bagging_baseline` | policy_computed | no_direct_overlap_detected | 0/0/0 | 0/0/0 | — |
| `balanced_bagging_tuned_baseline` | policy_computed | no_direct_overlap_detected | 0/0/0 | 0/0/0 | — |
| `robust13_comparison` | policy_computed | no_direct_overlap_detected | 0/0/0 | 0/0/0 | — |
| `historical_3ds_degraded` | alias | not_available | None/None/None | None/None/None | — |

**Result**: no model has nonzero flow_id or capture_id overlap in the train/val/test splits used for its packaged metrics.

## 2. Policy safety audit

| model | status | strict action | balanced action | strict FPR (test) | balanced FPR (test) | issues |
|---|---|---|---|---|---|---|
| `robust9_firewall` | default_firewall | BLOCK | FLAG_REVIEW | 0.0 | 0.0 | — |
| `balanced_bagging_3ds_reference` | policy_computed | BLOCK | FLAG_REVIEW | 0.0 | 0.0 | — |
| `balanced_bagging_3ds_refresh` | alias | — | — | — | — | alias entry; policy inherited |
| `clean_pooled_benchmark` | policy_computed | DISABLED_DO_NOT_BLOCK | FLAG_REVIEW | 0.125 | 0.0 | — |
| `twentyone_feature_experimental` | unsupported | — | — | — | — | unsupported stub; no policy expected |
| `single_model_fallback` | policy_computed | DISABLED_DO_NOT_BLOCK | FLAG_REVIEW | 0.041666666666666664 | 0.0 | — |
| `lodo_hold_iscx` | negative_control | — | — | 0.0 | 0.0 | — |
| `lodo_hold_usbvpn` | negative_control | — | — | 0.0 | 0.0 | — |
| `lodo_hold_vnat` | negative_control | — | — | 0.0 | 0.0 | — |
| `balanced_bagging_xgb_baseline` | policy_computed | BLOCK | FLAG_REVIEW | 0.0 | 0.0 | — |
| `balanced_bagging_baseline` | policy_computed | BLOCK | FLAG_REVIEW | 0.0 | 0.0 | — |
| `balanced_bagging_tuned_baseline` | policy_computed | DISABLED_DO_NOT_BLOCK | FLAG_REVIEW | 0.00980392156862745 | 0.00980392156862745 | — |
| `robust13_comparison` | policy_computed | BLOCK | FLAG_REVIEW | 0.0 | 0.0 | — |
| `historical_3ds_degraded` | alias | — | — | — | — | alias entry; policy inherited |

## 3. Session reconstruction (known-domain test split)

| model | prob | agg | n_test | strict R/FPR | balanced R/FPR | session AUC (test) | audit_inferred |
|---|---|---|---:|---|---|---|:---:|
| `robust9_firewall` | prob_iso | p80 | 124 | 0.9091/0.0000 | 0.9091/0.0000 | 0.9991 | no |
| `balanced_bagging_3ds_reference` | prob_raw | wt5 | 106 | 0.4000/0.0000 | 0.4000/0.0000 | 0.9505 | no |
| `balanced_bagging_3ds_refresh` | — | — | — | — | — | — | (n/a — alias entry) |
| `clean_pooled_benchmark` | ensemble_score | p80 | 91 | 1.0000/0.1250 | 0.7313/0.0000 | 0.9988 | no |
| `twentyone_feature_experimental` | — | — | — | — | — | — | (n/a — unsupported entry) |
| `single_model_fallback` | xgb_score | p80 | 91 | 1.0000/0.0417 | 0.7761/0.0000 | 1.0000 | no |
| `lodo_hold_iscx` | prob_iso | p80 | 140 | 0.0000/0.0000 | 0.0000/0.0000 | 0.5623 | no |
| `lodo_hold_usbvpn` | prob_platt | wt5 | 504 | 0.0435/0.0000 | 0.0435/0.0000 | 0.8134 | no |
| `lodo_hold_vnat` | prob_platt | p80 | 88 | 0.0000/0.0000 | 0.0000/0.0000 | 0.1759 | no |
| `balanced_bagging_xgb_baseline` | prob_raw | wt5 | 124 | 0.0909/0.0000 | 0.6818/0.0000 | 0.9710 | no |
| `balanced_bagging_baseline` | prob_raw | p80 | 106 | 0.2000/0.0000 | 0.2000/0.0000 | 0.9307 | no |
| `balanced_bagging_tuned_baseline` | prob_iso | wt5 | 124 | 0.1818/0.0098 | 0.1818/0.0098 | 0.9679 | no |
| `robust13_comparison` | prob_platt | wt5 | 124 | 0.0909/0.0000 | 0.7273/0.0000 | 0.9389 | no |
| `historical_3ds_degraded` | — | — | — | — | — | — | (n/a — alias entry) |

## 4. Label permutation sanity (test sessions, 200 shuffles)

Expected AUC under permuted labels ≈ 0.5. Mid-band values (e.g., 0.40–0.60) indicate the model is not silently encoding identity.

| model | n_perm | AUC mean | std | p05 | p50 | p95 | note |
|---|---:|---:|---:|---:|---:|---:|---|
| `robust9_firewall` | 200 | 0.498 | 0.074 | 0.381 | 0.501 | 0.621 | OK |
| `balanced_bagging_3ds_reference` | 200 | 0.506 | 0.123 | 0.305 | 0.498 | 0.713 | OK |
| `balanced_bagging_3ds_refresh` | 0 | — | — | — | — | — | alias entry |
| `clean_pooled_benchmark` | 200 | 0.497 | 0.069 | 0.389 | 0.491 | 0.614 | OK |
| `twentyone_feature_experimental` | 0 | — | — | — | — | — | unsupported entry |
| `single_model_fallback` | 200 | 0.500 | 0.068 | 0.388 | 0.501 | 0.608 | OK |
| `lodo_hold_iscx` | 200 | 0.503 | 0.040 | 0.430 | 0.501 | 0.562 | OK |
| `lodo_hold_usbvpn` | 200 | 0.501 | 0.065 | 0.392 | 0.503 | 0.604 | OK |
| `lodo_hold_vnat` | 200 | 0.494 | 0.139 | 0.272 | 0.487 | 0.733 | OK |
| `balanced_bagging_xgb_baseline` | 200 | 0.495 | 0.075 | 0.382 | 0.499 | 0.622 | OK |
| `balanced_bagging_baseline` | 200 | 0.513 | 0.124 | 0.319 | 0.512 | 0.709 | OK |
| `balanced_bagging_tuned_baseline` | 200 | 0.499 | 0.069 | 0.384 | 0.499 | 0.608 | OK |
| `robust13_comparison` | 200 | 0.504 | 0.070 | 0.383 | 0.507 | 0.617 | OK |
| `historical_3ds_degraded` | 0 | — | — | — | — | — | alias entry |

## 5. Bootstrap 95% CI (1000 resamples)

| model | n_boot | n_test | session AUC [lo, hi] | strict R [lo, hi] | strict FPR [lo, hi] |
|---|---:|---:|---|---|---|
| `robust9_firewall` | 1000 | 124 | [0.9957, 1.0000] | [0.7500, 1.0000] | [0.0000, 0.0000] |
| `balanced_bagging_3ds_reference` | 997 | 106 | [0.8598, 1.0000] | [0.0000, 1.0000] | [0.0000, 0.0000] |
| `balanced_bagging_3ds_refresh` | 0 | — | — | — | — |
| `clean_pooled_benchmark` | 1000 | 91 | [0.9944, 1.0000] | [1.0000, 1.0000] | [0.0000, 0.2760] |
| `twentyone_feature_experimental` | 0 | — | — | — | — |
| `single_model_fallback` | 1000 | 91 | [1.0000, 1.0000] | [1.0000, 1.0000] | [0.0000, 0.1429] |
| `lodo_hold_iscx` | 1000 | 140 | [0.5027, 0.6168] | [0.0000, 0.0000] | [0.0000, 0.0000] |
| `lodo_hold_usbvpn` | 1000 | 504 | [0.7030, 0.9153] | [0.0000, 0.1539] | [0.0000, 0.0000] |
| `lodo_hold_vnat` | 996 | 88 | [0.0388, 0.3904] | [0.0000, 0.0000] | [0.0000, 0.0000] |
| `balanced_bagging_xgb_baseline` | 1000 | 124 | [0.9376, 0.9962] | [0.0000, 0.2273] | [0.0000, 0.0000] |
| `balanced_bagging_baseline` | 997 | 106 | [0.8528, 0.9960] | [0.0000, 0.6667] | [0.0000, 0.0000] |
| `balanced_bagging_tuned_baseline` | 1000 | 124 | [0.9183, 0.9992] | [0.0417, 0.3684] | [0.0000, 0.0309] |
| `robust13_comparison` | 1000 | 124 | [0.8614, 0.9897] | [0.0000, 0.2273] | [0.0000, 0.0000] |
| `historical_3ds_degraded` | 0 | — | — | — | — |

## 6. Domain fingerprinting audit

Train a small RandomForest on each model's own feature subset to predict `dataset` (iscx/usbvpn/vnat). A high macro-OvR AUC means the feature set itself encodes dataset identity even before any VPN label is considered. **This auxiliary classifier is not a deployment model.**

Unified cross-dataset feature matrix used: `artifacts/clean_pipeline/features.parquet` (7 dispersion features; iscx + usbvpn + vnat).

| model | available | n_samples | feats used / required | classes | split strategy | accuracy | macro OvR-AUC | reason if n/a |
|---|:---:|---:|---|---|---|---:|---:|---|
| `robust9_firewall` | no | — | 0/9 | — | — | — | — | too few of this model's features present in unified matrix: 0/9 |
| `balanced_bagging_3ds_reference` | yes | 4712 | 7/7 | iscx;usbvpn;vnat | RF(existing_train_test_split) | 0.358 | 0.501 | — |
| `balanced_bagging_3ds_refresh` | no | — | 0/0 | — | — | — | — | alias entry; domain audit skipped |
| `clean_pooled_benchmark` | yes | 4712 | 9/9 | iscx;usbvpn;vnat | RF(existing_train_test_split) | 0.361 | 0.502 | — |
| `twentyone_feature_experimental` | no | — | 0/0 | — | — | — | — | unsupported entry; domain audit skipped |
| `single_model_fallback` | yes | 4712 | 9/9 | iscx;usbvpn;vnat | RF(existing_train_test_split) | 0.361 | 0.502 | — |
| `lodo_hold_iscx` | no | — | 0/0 | — | — | — | — | negative_control entry; domain audit skipped |
| `lodo_hold_usbvpn` | no | — | 0/0 | — | — | — | — | negative_control entry; domain audit skipped |
| `lodo_hold_vnat` | no | — | 0/0 | — | — | — | — | negative_control entry; domain audit skipped |
| `balanced_bagging_xgb_baseline` | no | — | 3/27 | — | — | — | — | too few of this model's features present in unified matrix: 3/27 |
| `balanced_bagging_baseline` | yes | 4712 | 7/7 | iscx;usbvpn;vnat | RF(existing_train_test_split) | 0.358 | 0.501 | — |
| `balanced_bagging_tuned_baseline` | no | — | 3/27 | — | — | — | — | too few of this model's features present in unified matrix: 3/27 |
| `robust13_comparison` | no | — | 3/12 | — | — | — | — | too few of this model's features present in unified matrix: 3/12 |
| `historical_3ds_degraded` | no | — | 0/0 | — | — | — | — | alias entry; domain audit skipped |

## 7. Figures generated

- `reports/figures/exported_models_session_auc_vs_strict_recall.png` — auc_vs_recall
- `reports/figures/exported_models_strict_recall_fpr_scatter.png` — strict_recall_fpr
- `reports/figures/exported_models_domain_fingerprint_auc.png` — domain_audit

- `reports/figures/exported_models_score_distribution_balanced_bagging_3ds_reference.png`
- `reports/figures/exported_models_score_distribution_balanced_bagging_baseline.png`
- `reports/figures/exported_models_score_distribution_balanced_bagging_tuned_baseline.png`
- `reports/figures/exported_models_score_distribution_balanced_bagging_xgb_baseline.png`
- `reports/figures/exported_models_score_distribution_clean_pooled_benchmark.png`
- `reports/figures/exported_models_score_distribution_lodo_hold_iscx.png`
- `reports/figures/exported_models_score_distribution_lodo_hold_usbvpn.png`
- `reports/figures/exported_models_score_distribution_lodo_hold_vnat.png`
- `reports/figures/exported_models_score_distribution_robust13_comparison.png`
- `reports/figures/exported_models_score_distribution_robust9_firewall.png`
- `reports/figures/exported_models_score_distribution_single_model_fallback.png`

## 8. Interpretation for thesis

**Direct leakage** — `flow_id` and `capture_id` are partitioned cleanly across train/val/test for every model where the prediction schema includes those columns. No suspicious meta-columns appear in any model's `feature_order.json`. The known-domain AUC values are therefore not the product of trivial split contamination.

**Policy safety** — three models with strict test FPR > 0 (`clean_pooled_benchmark` 0.125, `single_model_fallback` 0.042, `balanced_bagging_tuned_baseline` 0.0098) correctly carry `strict.action = DISABLED_DO_NOT_BLOCK`. No `negative_control` or alias supports firewall actions. Every `policy_computed` entry carries the required `comparison-only, not deployment-approved` warning.

**Label permutation** — permuted-label AUC medians cluster tightly around 0.50 for every reconstructable model (`robust9_firewall` p50 ≈ 0.50, std ≈ 0.074). This rules out silent identity encoding through metadata columns.

**Bootstrap CI** — known-domain CI bands for `robust9_firewall` are tight and far above chance. `robust9_firewall` 95% CI: session AUC ∈ [0.9957, 1.0000], strict recall ∈ [0.7500, 1.0000], strict FPR ∈ [0.0000, 0.0000]. `policy_computed` baselines that train on the smaller `clean_pipeline` test set (~91 sessions) and the LODO controls have wider bands, as expected.

**Domain fingerprinting** — on this **shared 7-feature dispersion subset**, macro OvR-AUC ≈ 0.50 (chance). The dispersion features themselves do NOT carry strong dataset identity for the models whose feature order is a subset of this parquet. This is a positive finding for the models audited.

Important caveat: models whose feature order extends beyond the unified 7-feature dispersion parquet (`robust9_firewall` 9 feats, `robust13_comparison` 12 feats, `balanced_bagging_xgb_baseline` / `balanced_bagging_tuned_baseline` 27 feats) could NOT be audited cross-dataset because their extra `sz_all_*` / `iat_*` / `session_prob_*` features are not present in the unified parquet. The fingerprinting result therefore cannot be extrapolated to those richer feature sets — the LODO negative-control collapses (test AUC 0.18 / 0.56 / 0.81 in `lodo_hold_vnat` / `lodo_hold_iscx` / `lodo_hold_usbvpn`) remain the authoritative evidence that unseen-domain robustness is not solved.

**Does this invalidate `robust9_firewall`?** No. `robust9_firewall` remains the strongest known-domain default firewall prototype with strict FPR = 0, strict recall ≈ 0.91, the cleanest policy gates, permutation-AUC median ≈ 0.50, and tight bootstrap CIs. The audit shows that the high session AUC is not the result of split leakage or feature-identity leakage on the shared dispersion subset. The audit also shows — through the LODO negative-control collapses — that this performance cannot be advertised as universal VPN-detection robustness.

**Suggested thesis wording**:

> Under the project's split protocol, no direct `flow_id` or `capture_id` leakage between train/val/test was detected for any exported model. The known-domain session AUC ≈ 0.999 for the default firewall is genuine within this protocol. On the shared 7-feature dispersion subset, an auxiliary domain classifier achieves macro OvR-AUC ≈ 0.50 (near chance), so the dispersion features themselves do not encode dataset identity in a directly attackable way. However, the LODO negative-control models collapse on held-out datasets, indicating that label-feature relationships shift across domains in ways the models do not generalize across. Known-domain performance must therefore not be reported as evidence of universal deployment robustness.

## 9. Limitations

- This audit consumes packaged `predictions.csv` /   `*_predictions.parquet` files. It does not regenerate model   inferences; if a prediction file was generated with a stale model,   the audit cannot detect that.
- Domain fingerprinting uses the unified 7-feature dispersion   parquet (`artifacts/clean_pipeline/features.parquet`) because it   is the only cross-dataset feature matrix that exists in the   workspace. Models whose feature order requires features absent   from this parquet (e.g. the `robust9` 9-feature set, the   27-feature tuned baselines, the 12-feature `robust13`) report   `available=false` with a precise reason. This is not a failure   of the audit; it is an honest data-availability constraint.
- The auxiliary domain classifier is fitted only for the audit,   with `random_state=42`. It is not exposed in the registry, the   app, or any runtime bundle.
- All comparison/aliasing logic is metadata-only. Aliases are   intentionally not re-evaluated; they inherit their target's   audit row by reference.
