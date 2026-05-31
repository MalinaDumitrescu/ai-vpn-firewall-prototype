# Runtime Bundle — Reports

**Generated:** 2026-05-29  
**Bundle model:** `full_canonical__lgbm`

---

## Contents

| File | Description |
|------|-------------|
| `final_transfer_summary.md` | Full experiment summary — model selection rationale, LODO results, DANN v2 rejection, fingerprinting conclusion |
| `model_comparison.csv` | Raw per-model metrics from the final_transfer experiment (all feature families × algorithms) |

---

## Key findings

- **Recommended firewall:** `full_canonical__lgbm` — deployment_eligible, LODO-evaluated, well-calibrated, lowest FPR
- **Dataset fingerprinting:** Unresolved — `domain_auc = 1.0` for all models
- **DANN v2:** Did not reduce fingerprinting (`domain_reduction ≈ 0.0003`)
- **relative_shape_v2 + GroupDRO:** Does not replace `full_canonical__lgbm` (authoritative 3-fold LODO-min = 0.4027)
- **Simulation-only:** All decisions are PASS / FLAG_REVIEW / SIMULATED_BLOCK — no real blocking

---

## Model quick-reference

| Model | Pooled AUC | LODO-min | Domain AUC | FPR | Deploy Score | Role |
|-------|-----------|----------|------------|-----|-------------|------|
| `full_canonical__lgbm` | 0.9994 | 0.6164 | 1.0 | 0.0025 | 0.6836 | **recommended_firewall** |
| `robust9_firewall` | 0.9991 | — | — | 0.0 | — | legacy_baseline |
| `balanced_bagging_3ds_reference` | ~0.950 | — | — | 0.0 | — | benchmark_comparison |
| `balanced_bagging_baseline` | ~0.931 | — | — | 0.0 | — | benchmark_comparison |
| `balanced_bagging_xgb_baseline` | ~0.971 | — | — | 0.0 | — | benchmark_comparison |
| `robust13_comparison` | ~0.939 | — | — | 0.0 | — | benchmark_comparison |
