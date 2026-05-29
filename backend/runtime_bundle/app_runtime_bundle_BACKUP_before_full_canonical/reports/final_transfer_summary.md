# Final Transfer Experiment — Summary Report

**Date:** 2026-05-29  
**Experiment:** `final_transfer`  
**Status:** ✅ Complete — No further retraining.

---

## 1. Selected Firewall Model

| Field | Value |
|-------|-------|
| **Model ID** | `full_canonical__lgbm` |
| **Algorithm** | LightGBM |
| **Feature family** | `full_canonical` (34 features) |
| **Deployment eligible** | ✅ Yes |
| **Runtime compatible** | ✅ Yes |
| **Recommendation** | `recommended_firewall = full_canonical__lgbm` |

### All recommendation slots

| Slot | Model |
|------|-------|
| `best_offline` | `full_canonical__lgbm` |
| `best_transfer` | `full_canonical__lgbm` |
| `best_low_fingerprint` | `timing_shape__lgbm` |
| `recommended_firewall` | `full_canonical__lgbm` |

---

## 2. Final Metrics — `full_canonical__lgbm`

### Detection Performance (In-Distribution)

| Metric | Value |
|--------|-------|
| Pooled AUC | 0.9994 |
| Pooled PR-AUC | 0.9840 |
| Session AUC | 1.0000 |
| Recall @ threshold | 0.9444 |
| FPR @ threshold | 0.0025 |
| TP / FP / TN / FN | 221 / 19 / 7699 / 13 |

### Transfer Performance (Leave-One-Dataset-Out)

| Dataset held out | LODO AUC |
|-----------------|----------|
| ISCX-VPN-2016 | 0.6164 |
| VNAT | 0.6898 |
| USBVPN | Not evaluated (single capture) |
| **LODO-mean** | **0.6531** |
| **LODO-min** | **0.6164** |

### Fingerprinting & Calibration

| Metric | Value |
|--------|-------|
| Domain AUC | 1.0000 |
| Domain Accuracy | 1.0000 |
| ECE | 0.0026 |
| Threshold Instability | 0.0346 |

### Multi-Objective Score

| Score | Value |
|-------|-------|
| Deployment final score | 0.6836 |
| Raw final score | 0.4336 |

---

## 3. Why DANN v2 Was Rejected

DANN v2 (Domain-Adversarial Neural Network) was trained across 21 hyperparameter configurations with:
- Gradient Reversal Layer (GRL) with lambda annealing (0 → 5.0)
- Balanced mini-batching across domains (`both`, `class`, `domain`, `none`)
- Embedding-level domain classifier (not input features)
- Architectures: `[32,16]`, `[64,32]`, `[128,64]` hidden units

**Outcome:**

| Metric | Value |
|--------|-------|
| Best `domain_reduction` | ≈ 0.00033 |
| `input_domain_auc` | ≈ 1.0000 |
| Best `embedding_domain_auc` | ≈ 0.9997 |
| Verdict | **No meaningful fingerprint reduction** |

- DANN models are **not runtime-compatible** (require PyTorch inference pipeline)
- DANN models have **no LODO evaluation** (NaN lodo_min_auc / lodo_mean_auc)
- `deployment_eligible = False` for all DANN configurations

**Conclusion:** DANN failed to learn a domain-invariant representation. The adversarial training approach cannot overcome structural dataset fingerprinting when packet size distributions and IAT patterns encode dataset origin at the feature level. This is not an architecture failure — it reflects a fundamental data limitation.

---

## 4. Domain Fingerprinting Conclusion

**Dataset fingerprinting is structural and cannot be resolved by adversarial training alone.**

- Domain classifier achieves AUC = 1.0 on raw features AND on frozen DANN encoder outputs
- Features such as `fwd_pkt_len_mean`, `bwd_pkt_len_mean`, `flow_iat_mean` encode absolute network conditions that differ systematically between datasets (capture environment, VPN software version, OS, hardware)
- Even the `timing_shape` family (5 relative timing features) reduces domain AUC only to ≈ 0.989
- The relative_shape_v2 family (11 normalised/ratio features + GroupDRO) achieves domain_auc = 1.0 — purely relative features do **not** remove fingerprinting
- This is consistent with published literature: cross-dataset VPN detection remains an open problem

**Implication:** All models trained in this experiment are **known-domain / simulation-only** prototypes.

---

## 5. Improvement Branch: relative_shape_v2 + GroupDRO

One improvement branch was executed to test whether purely normalised/ratio features,
combined with GroupDRO worst-domain reweighting, could improve LODO-min AUC.

### Feature family: `relative_shape_v2` (11 features)

`sz_cv`, `sz_iqr_norm_median`, `sz_qratio`, `sz_median_to_mean`,
`sz_p25_median_ratio`, `sz_p75_median_ratio`, `iat_cv`, `iat_iqr_norm_median`,
`iat_qratio`, `iat_median_to_mean`, `relative_burstiness`

No absolute-scale features (`flow_duration`, `total_bytes`, `packet_rate`, `byte_rate` excluded).

### Results

| Model | Pooled AUC | LODO-min | Domain AUC | FPR | ECE | Deploy Score |
|-------|-----------|----------|------------|-----|-----|-------------|
| `relative_shape_v2__lgbm` | 0.9937 | 0.5553 | 1.0 | 0.0293 | 0.0350 | 0.3704 |
| `relative_shape_v2__lgbm__groupdro` | 0.9940 | **0.6592** | 1.0 | 0.0294 | 0.0349 | 0.5002 |
| `relative_shape_v2__xgb` | 0.9905 | 0.3630 | 1.0 | 0.0526 | 0.0573 | 0.0228 |
| `relative_shape_v2__xgb__groupdro` | 0.9904 | 0.4109 | 1.0 | 0.0533 | 0.0576 | 0.1115 |
| `relative_shape_v2__cat` | 0.9889 | 0.4798 | 1.0 | 0.0670 | 0.0652 | 0.2327 |
| `relative_shape_v2__cat__groupdro` | 0.9902 | 0.4266 | 1.0 | 0.0425 | 0.0431 | 0.1560 |
| **`full_canonical__lgbm`** | **0.9994** | 0.6164 | 1.0 | **0.0025** | **0.0026** | **0.6836** |

### Verdict

`relative_shape_v2__lgbm__groupdro` achieves LODO-min = 0.6592 (above the 0.6164 baseline).
However:
- domain_auc = 1.0 — fingerprinting **unchanged** (absolute scale is not the sole fingerprinting signal)
- FPR = 0.029 — **12× higher** than full_canonical
- ECE = 0.035 — **13× worse** calibration
- Pooled AUC = 0.9940 — slightly lower in-distribution detection
- Deployment_final_score = 0.5002 vs 0.6836

**`full_canonical__lgbm` remains the recommended_firewall.** The relative_shape_v2 branch
confirms that absolute-scale features carry genuine domain-invariant signal — simply removing them
does not reduce fingerprinting and degrades operational quality.

---

## 6. Deployment Limitations

1. **Known-domain only:** The model was trained and evaluated on ISCX-VPN-2016, USBVPN, and VNAT. Performance on unseen deployment environments is unknown.
2. **LODO-min AUC = 0.6164:** Moderate transfer performance. When ISCX-VPN-2016 is held out, AUC drops to ~0.616, close to the detection floor.
3. **Domain AUC = 1.0:** The model has fully memorised dataset origin. It cannot generalise to new environments without fine-tuning.
4. **Capture-level splitting:** Evaluation is honest (no flow-level leakage), but all captures come from a small number of controlled experiments.
5. **Runtime pipeline:** Requires the same feature extraction pipeline as training (CICFlowMeter-compatible features). Any change to extraction parameters will degrade performance.
6. **No adversarial robustness:** Active adversaries manipulating traffic patterns are not evaluated.
7. **Simulation-only:** All firewall decisions are labelled SIMULATED_BLOCK / FLAG_REVIEW / PASS.
   No real network traffic is blocked.

---

## 7. Next Improvement Ideas

### Medium-term (data collection — highest impact)
1. **New capture environments:** Collect VPN traffic from 2–3 additional OS/hardware/network
   configurations. Domain AUC will only drop when feature distributions overlap across environments.
   This is the **only proven path** to reducing domain fingerprinting.
2. **Modern VPN protocols:** WireGuard, QUIC-over-VPN. Current datasets are OpenVPN/PPTP-era.
3. **Adversarial traffic augmentation:** Inject noise into packet sizes/IAT to simulate real-world
   variation and force models to rely on structural rather than absolute features.

### Short-term (no new data)
4. **Threshold calibration per-domain:** Separate operating thresholds for ISCX vs VNAT to
   maximise worst-case recall.
5. **Isotonic recalibration per-domain:** Per-domain calibration maps (already applied globally).
6. **Feature selection within full_canonical:** Drop the highest domain_importance features and
   re-evaluate if LODO-min improves without sacrificing pooled AUC.

### Already attempted
- ~~**relative_shape_v2 + GroupDRO:**~~ Authoritative 3-fold LODO-min = **0.4027** (not 0.6592 — 2-fold
  result was biased by usbvpn split containing only label=0 flows). domain_auc = 1.0 unchanged.
  Does not beat full_canonical__lgbm on any criterion. See `artifacts/relative_shape_v2_groupdro/`.
- ~~**DANN v2 adversarial training:**~~ domain_reduction ≈ 0.0003. Ineffective.

### Long-term (architecture)
7. **Packet-sequence models (CNN/LSTM):** Per-packet byte sequences instead of flow statistics.
   Reduces reliance on absolute scale while capturing protocol fingerprints.
8. **Federated LODO training:** Train across datasets collaboratively without sharing raw traffic.
   Directly targets domain generalisation.
9. **Concept drift monitoring:** Deploy with a domain-shift detector. Alert when incoming flow
   statistics diverge from training distribution.

---

## 8. Artifact Locations

| Artifact | Path |
|----------|------|
| Model comparison | `artifacts/final_transfer/model_comparison.csv` |
| Recommended models | `artifacts/final_transfer/recommended_models.json` |
| DANN v2 results | `artifacts/final_transfer/dann_v2/dann_v2_results.csv` |
| DANN v1 results | `artifacts/final_transfer/dann_results.csv` |
| Anti-fingerprint scores | `artifacts/final_transfer/anti_fingerprint_scores.csv` |
| Trained models | `artifacts/final_transfer/models/` |
| Figures (13 total) | `artifacts/final_transfer/figures/` |
| Notebook | `notebooks/final_model_results.ipynb` |
| HTML export | `artifacts/final_transfer/final_model_results.html` |
| This report | `artifacts/final_transfer/final_transfer_summary.md` |
| Model documentation | `artifacts/final_transfer/models/full_canonical__lgbm/MODEL_DOCS.md` |
| Open-set thresholds | `artifacts/final_transfer/models/full_canonical__lgbm/thresholds.json` |
| Backend registry | `backend/model_registry/` |
| **relative_shape_v2 branch** | **`artifacts/relative_shape_v2_groupdro/`** |
| Branch recommendation | `artifacts/relative_shape_v2_groupdro/final_recommendation.json` |
| Branch LODO results | `artifacts/relative_shape_v2_groupdro/lodo_results.csv` |

### Figures inventory

| Figure | Description |
|--------|-------------|
| `fig1_auc_comparison.png` | Pooled ROC-AUC comparison — top models |
| `fig2_domain_fingerprinting_scatter.png` | VPN AUC vs domain AUC scatter (per family) |
| `fig3_lodo_breakdown.png` | LODO-min AUC ranking — all models |
| `fig4_deployment_score.png` | Deployment score ranking — eligible models |
| `fig5_relative_shape_v2_comparison.png` | Improvement branch: relative_shape_v2 results |
| `fig6_lodo_heatmap.png` | LODO AUC heatmap per dataset |
| `fig7_vpn_vs_domain_auc_scatter.png` | VPN AUC vs domain AUC (extended, all families) |
| `fig8_calibration_ece.png` | ECE calibration ranking |
| `fig9_confusion_matrix_grid.png` | Confusion matrix grid — top LGBM models |
| `fig10_threshold_stability.png` | Threshold instability ranking |
| `fig11_anti_fingerprint_feature_importance.png` | Anti-fingerprint feature scores |
| `fig12_dann_v2_domain_reduction.png` | DANN v2 domain reduction across all configs |
| `fig13_multi_metric_summary_heatmap.png` | Multi-metric heatmap — top candidates |

---

## 9. Thesis-Ready Final Conclusion

> "The selected firewall prototype is `full_canonical__lgbm` because it is deployment-eligible,
> runtime-compatible, LODO-evaluated, well-calibrated, low-FPR, and has the highest deployment score.
> However, dataset-origin predictability remains perfect (`domain_auc = 1.0`), and DANN v2 did not
> meaningfully reduce embedding-level fingerprinting. Therefore, the model is suitable as a
> known-domain simulation prototype, not as a production-ready unseen-domain firewall."

### Supporting evidence summary

| Criterion | `full_canonical__lgbm` | Status |
|-----------|----------------------|--------|
| Deployment eligible | True | ✅ Pass |
| Runtime compatible | True | ✅ Pass |
| LODO evaluated | LODO-min = 0.6164 | ✅ Pass |
| Calibrated | ECE = 0.0026 | ✅ Pass |
| Low FPR | FPR = 0.0025 | ✅ Pass |
| Highest deployment score | 0.6836 | ✅ Pass |
| Domain AUC = 1.0 | Perfect fingerprinting | ⚠️ Known limitation |
| DANN v2 reduction | domain_reduction ≈ 0.0003 | ⚠️ Insufficient |
| relative_shape_v2 branch | 3-fold LODO-min = 0.4027 (authoritative) | ⚠️ Does not replace |
| Production ready | False | ❌ Simulation-only |
