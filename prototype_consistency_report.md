# Prototype Consistency Report

**Date:** 2026-05-29  
**Prototype:** AI VPN Firewall Prototype  
**Audit type:** Full post-lock consistency audit after enforcing `full_canonical__lgbm` as sole executable model

---

## 1. Active Executable Model

| Property | Value |
|---|---|
| model_id | `full_canonical__lgbm` |
| algorithm | LightGBM (single model) |
| feature_family | full_canonical |
| n_features | 34 |
| probability_column | `prob` |
| aggregation | `mean_per_capture` |
| session_grouping | `capture_id` |
| policy | `open_set_three_tier` |
| review_threshold | 0.02709 (p95 benign val score) |
| block_threshold | 0.165365 (max benign val score) |
| action_mode | `simulation` |
| production_ready | `false` |
| executable | `true` |
| deployment_eligible | `true` |
| runtime_compatible | `true` |

---

## 2. Three-Tier Action Policy

| Band | Condition | Action |
|---|---|---|
| PASS | score < 0.02709 | No action |
| FLAG_REVIEW | 0.02709 ≤ score < 0.165365 | Manual review recommended |
| SIMULATED_BLOCK | score ≥ 0.165365 | Logged as simulated block (no packets dropped) |

---

## 3. Comparison-Only Models

All models other than `full_canonical__lgbm` are marked `executable: false, comparison_only: true, inference_permitted: false` in the allowlist.

| Model ID | Role |
|---|---|
| `robust9_firewall` | Legacy baseline — 9-feature XGB+LGBM+CatBoost ensemble (PCAP compat only) |
| `timing_shape__lgbm` | Low-fingerprint diagnostic — lower detection performance, not selected |
| `balanced_bagging_3ds_reference` | Benchmark comparison |
| `balanced_bagging_xgb_baseline` | Benchmark comparison |
| `balanced_bagging_baseline` | Benchmark comparison |
| `robust13_comparison` | Benchmark comparison |
| DANN v2 models | Research-only — did not reduce embedding fingerprinting |
| LODO hold-out models | Negative controls — not deployable |

---

## 4. Backend Endpoints Audited

All 50 checks passed (0 failures).

| Endpoint | Method | Result | Notes |
|---|---|---|---|
| `/health` | GET | ✅ PASS | status=ok |
| `/models/default` | GET | ✅ PASS | Returns full_canonical__lgbm, executable=true, n_features=34 |
| `/models/full_canonical__lgbm/policy` | GET | ✅ PASS | review_threshold=0.02709, block_threshold=0.165365, simulation_only=true |
| `/firewall/runtime-models` | GET | ✅ PASS | full_canonical default_firewall=true; robust9 executable=false |
| `/firewall/required-features` | GET | ✅ PASS | 34 features, model_id=full_canonical__lgbm |
| `/firewall/demo` | GET | ✅ PASS | model_id=full_canonical__lgbm, counts PASS/FLAG_REVIEW/BLOCK present |
| `/firewall/live-replay/state` | GET | ✅ PASS | model_id=full_canonical__lgbm, executable=true |
| `/firewall/live-ingest/state` | GET | ✅ PASS | recommended_model=full_canonical__lgbm (robust9 retained for PCAP compat) |
| `/firewall/analyze-csv-multimodel?selected_model_ids=robust9_firewall` | POST | ✅ PASS | Returns HTTP 400 with "comparison-only" detail |
| `/comparison/summary` | GET | ✅ PASS | Read-only comparison list returned |
| `/models` | GET | ✅ PASS | 17 registered models visible for audit |

### Inference Enforcement
- Any attempt to run inference on a non-executable model via `POST /firewall/analyze-csv-multimodel?selected_model_ids=<other>` returns **HTTP 400** with the message: *"The following model IDs are comparison-only and cannot run inference: … Only 'full_canonical__lgbm' is executable in this prototype."*

---

## 5. Action Policy Audit — Output Fields

Session-level firewall decisions include:

| Field | Present | Notes |
|---|---|---|
| `session_id` | ✅ | Grouping key |
| `session_score` | ✅ | Mean prob across flows in session |
| `action` | ✅ | One of: PASS, FLAG_REVIEW, BLOCK |
| `strict_trigger` | ✅ | Boolean — score ≥ block_threshold |
| `balanced_trigger` | ✅ | Boolean — score ≥ review_threshold |
| `simulated` | ✅ | Always `true` — no real packet blocking |
| `model_id` | ✅ | Always `full_canonical__lgbm` |
| `action_mode` | ✅ | Always `simulation` |
| `production_readiness` | ✅ | Always `false` |

---

## 6. Frontend UI Pages Audited

### Text Search Results

| Search term | Occurrences | Verdict |
|---|---|---|
| `robust9_firewall` | 5 | ✅ All in legacy/comparison context only |
| `robust9 analysis` | 0 | ✅ None |
| `default robust9` | 0 | ✅ None |
| `9 robust9 features` | 0 | ✅ None |
| `Run all selected models` | 0 | ✅ None |
| `Analyze CSV (6 models)` | 0 | ✅ None |
| `default_firewall` (as label) | 0 active | ✅ Only as data field reader (not a label string) |

### Page-by-Page Summary

| Page | Component | Status | Notes |
|---|---|---|---|
| Dashboard | `Dashboard.jsx` | ✅ Correct | Shows full_canonical__lgbm; simulation warning; domain fingerprinting warning |
| Single-model Demo | `FirewallDemo.jsx` | ✅ Correct | Title "Final model demo"; 34 features; full_canonical__lgbm only |
| Multi-model Evaluation | `MultiModelCsvEvaluation.jsx` | ✅ Correct | Read-only model roster; only full_canonical executable; button "Analyze CSV with final model" |
| Live VM — CSV Replay | `LiveVMReplay.jsx` | ✅ Correct | full_canonical__lgbm pipeline; 34 features; simulation warning |
| Live VM — PCAP Monitor | `LiveVMMonitor.jsx` | ✅ Correct | robust9 retained for PCAP compat with clear "executable model is full_canonical__lgbm" notice |
| Models Registry | `ModelRegistry.jsx` | ✅ Correct | All 17 models visible; full_canonical labeled "Recommended / executable"; others labeled appropriately |
| Model Comparison | `ModelComparison.jsx` | ✅ Correct | Read-only comparison table; robust9 labeled "legacy baseline" |
| Robustness | `Robustness.jsx` | ✅ Correct | "34 input features"; LODO failure mode documented; simulation-only confirmed |
| Demo Runner | `DemoRunner.jsx` | ✅ Correct | Local thesis demo runner only |

---

## 7. Feature Contract Verification

`full_canonical__lgbm` expects exactly 34 features:

```
sz_coef_variation, sz_p25_median_ratio, sz_p75_median_ratio, sz_iqr_norm_median,
dispersion_symmetry, direction_balance_bytes, direction_balance_packets,
sz_mean_max, sz_mean_min, sz_std_max, sz_std_min,
iat_all_mean, iat_all_std, iat_all_p25, iat_all_median, iat_all_p75,
iat_mean_max, iat_mean_min, iat_std_max, iat_std_min,
sz_all_mean, sz_all_std, sz_all_median, sz_all_p25, sz_all_p75,
sz_cv, sz_iqr, sz_qratio, sz_median_to_mean,
iat_iqr, iat_cv, iat_median, iat_p25, iat_p75
```

- ✅ Runtime models endpoint confirms 34 features
- ✅ `/firewall/required-features` returns all 34
- ✅ `live_replay_service.py` validates against engine's `feature_order` (34 features)
- ✅ `live_ingest_service.py` retains 9-feature robust9 schema for PCAP compat only

---

## 8. Known Remaining Limitations

| Limitation | Status | Notes |
|---|---|---|
| Dataset fingerprinting unresolved | ⚠️ Known | `domain_auc = 1.0` — model can identify dataset of origin |
| DANN v2 did not fix fingerprinting | ⚠️ Known | `domain_reduction ≈ 0.0003` — negligible |
| LODO generalisation not solved | ⚠️ Known | `lodo_min_auc = 0.6164` — moderate cross-dataset transfer only |
| PCAP monitor uses legacy robust9 | ℹ️ By design | `pcap_to_live_stream.py` generates only 9 `sz_*` features; cannot use full_canonical without rewriting pcap tool |
| Not production-ready | ⚠️ Known | Known-domain prototype; simulation-only; no calibration on target network |
| Single capture in bundled demo | ℹ️ Known | Bundled demo CSV has limited VPN session diversity |

---

## 9. Confirmation Statements

> ✅ **No packets are blocked.** All BLOCK decisions are `SIMULATED_BLOCK` — audit/log actions only. The system does not intercept, modify, or drop any network traffic.

> ✅ **This prototype is not production-ready.** `production_ready: false` is enforced across all endpoints. The model requires local revalidation, threshold recalibration, and drift monitoring before any real-world deployment.

> ✅ **Only `full_canonical__lgbm` is executable.** All other models return `executable: false, comparison_only: true` and are enforced at the backend — any attempt to run inference on a comparison model returns HTTP 400.

> ✅ **All other models are comparison-only.** They remain visible in the Model Registry, Model Comparison, and Multi-model Evaluation pages for audit and research documentation purposes only.

---

## 10. Audit Tool

The audit script is saved at:

```
tools/full_audit.py
```

Run it with the backend running on port 8000:

```bash
cd ai-vpn-firewall-prototype
python tools/full_audit.py
```

Expected output: **50 passed, 0 failed**

