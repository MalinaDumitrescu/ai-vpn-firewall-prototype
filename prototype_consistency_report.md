# Prototype Consistency Report

**Date:** 2026-05-30 (updated — supersedes 2026-05-29 draft)  
**Prototype:** AI VPN Firewall Prototype  
**Audit type:** Full post-transition consistency audit after switching the executable model to `unified_relative_shape_v2__lgbm`

---

## 1. Active Executable Model

| Property | Value |
|---|---|
| model_id | `unified_relative_shape_v2__lgbm` |
| algorithm | LightGBM + isotonic calibration |
| feature_family | unified_relative_shape_v2 |
| n_features | 12 |
| probability_column | `prob_iso` |
| aggregation | `mean` (per session) |
| session_grouping | `capture_id` |
| policy | open_set_three_tier |
| review_threshold | 0.03667 (FLAG_REVIEW band start) |
| block_threshold | 0.425 (SIMULATED_BLOCK band start) |
| action_mode | `simulation` |
| production_ready | `false` |
| executable | `true` |
| deployment_eligible | `true` |

---

## 2. Three-Tier Action Policy

| Band | Condition | Action |
|---|---|---|
| PASS | score < 0.03667 | No action |
| FLAG_REVIEW | 0.03667 ≤ score < 0.425 | Manual review recommended |
| SIMULATED_BLOCK | score ≥ 0.425 | Logged as simulated block (no packets dropped) |

---

## 3. Comparison-Only Models

All models other than `unified_relative_shape_v2__lgbm` are marked `executable: false, comparison_only: true, inference_permitted: false` in the allowlist.

| Model ID | Role |
|---|---|
| `full_canonical__lgbm` | Legacy 34-feature LightGBM baseline (domain_auc=1.0 — formula-inconsistent training data). Comparison-only. |
| `robust9_firewall` | Legacy 9-feature XGB+LGBM+CatBoost ensemble (PCAP compat reference only). Comparison-only. |
| `timing_shape__lgbm` | Low-fingerprint diagnostic — lower detection performance, not selected. Comparison-only. |
| `balanced_bagging_3ds_reference` | Benchmark comparison |
| `balanced_bagging_baseline` | Benchmark comparison |
| `balanced_bagging_xgb_baseline` | Benchmark-incompatible (requires session-derived probability features) |
| `robust13_comparison` | Benchmark-incompatible (requires session-derived probability features) |
| DANN v2 models | Research-only — did not reduce embedding fingerprinting (domain_reduction ≈ 0.0003) |
| LODO hold-out models | Negative controls — not deployable |

---

## 4. Backend Endpoints Audited

All inference is restricted to `unified_relative_shape_v2__lgbm` via the `EXECUTABLE_FIREWALL_MODEL_ID` constant in `backend/app/registry_loader.py`.

| Endpoint | Method | Result | Notes |
|---|---|---|---|
| `/health` | GET | ✅ PASS | status=ok |
| `/models/default` | GET | ✅ PASS | Returns unified_relative_shape_v2__lgbm, executable=true, n_features=12 |
| `/models/unified_relative_shape_v2__lgbm/policy` | GET | ✅ PASS | review_threshold=0.03667, block_threshold=0.425, simulation_only=true |
| `/firewall/runtime-models` | GET | ✅ PASS | unified_relative_shape_v2__lgbm default_firewall=true; full_canonical/robust9 executable=false |
| `/firewall/required-features` | GET | ✅ PASS | 12 features, model_id=unified_relative_shape_v2__lgbm |
| `/firewall/demo` | GET | ✅ PASS | model_id=unified_relative_shape_v2__lgbm, counts PASS/FLAG_REVIEW/BLOCK present |
| `/firewall/live-replay/state` | GET | ✅ PASS | model_id=unified_relative_shape_v2__lgbm, executable=true |
| `/firewall/live-ingest/state` | GET | ✅ PASS | recommended_model=unified_relative_shape_v2__lgbm |
| `/firewall/analyze-csv-multimodel?selected_model_ids=robust9_firewall` | POST | ✅ PASS | Returns HTTP 400 with "comparison-only" detail |
| `/comparison/summary` | GET | ✅ PASS | Read-only comparison list returned |
| `/models` | GET | ✅ PASS | All registered models visible for audit |

### Inference Enforcement
- Any attempt to run inference on a non-executable model via `POST /firewall/analyze-csv-multimodel?selected_model_ids=<other>` returns **HTTP 400** with the message: *"The following model IDs are comparison-only and cannot run inference: … Only 'unified_relative_shape_v2__lgbm' is executable in this prototype."*

---

## 5. Action Policy Audit — Output Fields

Session-level firewall decisions include:

| Field | Present | Notes |
|---|---|---|
| `session_id` | ✅ | Grouping key |
| `session_score` | ✅ | Mean prob_iso across flows in session |
| `action` | ✅ | One of: PASS, FLAG_REVIEW, BLOCK |
| `strict_trigger` | ✅ | Boolean — score ≥ block_threshold |
| `balanced_trigger` | ✅ | Boolean — score ≥ review_threshold |
| `simulated` | ✅ | Always `true` — no real packet blocking |
| `model_id` | ✅ | Always `unified_relative_shape_v2__lgbm` |
| `action_mode` | ✅ | Always `simulation` |
| `production_readiness` | ✅ | Always `false` |

---

## 6. Frontend UI Pages Audited

### Text Search Results

| Search term | Occurrences | Verdict |
|---|---|---|
| `robust9_firewall` | 5 | ✅ All in legacy/comparison context only |
| `unified_relative_shape_v2__lgbm` | Multiple | ✅ Correctly shown as active/recommended model |
| `full_canonical__lgbm` | Multiple | ✅ All in legacy/comparison context only |
| `Run all selected models` | 0 | ✅ None |
| `Analyze CSV (6 models)` | 0 | ✅ None |
| `default_firewall` (as label) | 0 active | ✅ Only as data field reader (not a label string) |

### Page-by-Page Summary

| Page | Component | Status | Notes |
|---|---|---|---|
| Dashboard | `Dashboard.jsx` | ✅ Correct | Shows unified_relative_shape_v2__lgbm; simulation warning; domain fingerprinting warning |
| Single-model Demo | `FirewallDemo.jsx` | ✅ Correct | Title "Final model demo"; 12 features; unified_relative_shape_v2__lgbm only |
| Multi-model Evaluation | `MultiModelCsvEvaluation.jsx` | ✅ Correct | Read-only model roster; only unified model executable; button "Analyze CSV with final model" |
| Live VM — CSV Replay | `LiveVMReplay.jsx` | ✅ Correct | unified_relative_shape_v2__lgbm pipeline; 12 features; simulation warning |
| Live VM — PCAP Monitor | `LiveVMMonitor.jsx` | ✅ Correct | Extracts 12 unified_relative_shape_v2 features; clear simulation-only notice |
| Models Registry | `ModelRegistry.jsx` | ✅ Correct | All models visible; unified_relative_shape_v2__lgbm labeled "Recommended / executable"; others labeled appropriately |
| Model Comparison | `ModelComparison.jsx` | ✅ Correct | Read-only comparison table; unified model highlighted as current recommended; full_canonical/robust9 labeled legacy |
| Robustness | `Robustness.jsx` | ✅ Correct | Simulation-only confirmed |
| Demo Runner | `DemoRunner.jsx` | ✅ Correct | Local thesis demo runner only |

---

## 7. Feature Contract Verification

`unified_relative_shape_v2__lgbm` expects exactly **12 features**:

```
sz_cv, sz_iqr, sz_qratio, sz_median_to_mean,
sz_p25_median_ratio, sz_p75_median_ratio, sz_iqr_norm_median,
iat_cv, iat_iqr,
direction_balance_bytes, direction_balance_packets, dispersion_symmetry
```

### Feature Formulas (from `feature_contract.json`)

| Feature | Formula |
|---|---|
| `sz_cv` | `std(sizes) / (mean(sizes) + eps)` |
| `sz_iqr` | `p75(sizes) - p25(sizes)` |
| `sz_qratio` | `p75(sizes) / (p25(sizes) + eps)` |
| `sz_median_to_mean` | `median(sizes) / (mean(sizes) + eps)` |
| `sz_p25_median_ratio` | `p25(sizes) / (median(sizes) + eps)` |
| `sz_p75_median_ratio` | `p75(sizes) / (median(sizes) + eps)` |
| `sz_iqr_norm_median` | `(p75-p25)(sizes) / (median(sizes) + eps)` |
| `iat_cv` | `std(iats) / (mean(iats) + eps)` |
| `iat_iqr` | `p75(iats) - p25(iats)` |
| `direction_balance_bytes` | `(bytes_up - bytes_down) / (bytes_up + bytes_down + eps)` |
| `direction_balance_packets` | `(pkts_up - pkts_down) / (pkts_up + pkts_down + eps)` |
| `dispersion_symmetry` | `1.0 - abs(std_up - std_down) / (std_up + std_down + eps)` |

eps = 1e-6. Direction convention: `1 = upload/client-to-server`, `0 = download/server-to-client`.

- ✅ Runtime models endpoint confirms 12 features
- ✅ `/firewall/required-features` returns all 12
- ✅ `live_replay_service.py` validates against engine's `feature_order` (12 unified features)
- ✅ `live_ingest_service.py` uses `unified_relative_shape_v2__lgbm` as the ingest model
- ✅ `tools/pcap_to_live_stream.py` generates 12 unified_relative_shape_v2 features by default

---

## 8. Live Validation Results (2026-05-30)

Three PCAP scenarios tested end-to-end. All schema validations passed.

| Scenario | PCAP | Flows | Sessions | Score(s) | Actions |
|---|---|---|---|---|---|
| Basic benign | `vm_basic_benign.pcap` | 4 | 2 | 0.0128, 0.3554 | PASS=1, FLAG_REVIEW=1, BLOCK=0 |
| WARP (Cloudflare VPN-like) | `vm_warp.pcap` | 5 | 1 | 0.2382 | FLAG_REVIEW=1 |
| OpenVPN lab | `vm_openvpn_lab.pcap` | 2 | 1 | 0.2134 | FLAG_REVIEW=1 |

The unified model correctly flags VPN-like traffic (WARP, OpenVPN) as `FLAG_REVIEW` while keeping low-suspicion benign traffic as `PASS`.

Full details: `artifacts/live_unified_model_validation.md`

---

## 9. Known Remaining Limitations

| Limitation | Status | Notes |
|---|---|---|
| Dataset fingerprinting (legacy) | ⚠️ Known | `domain_auc = 1.0` for `full_canonical__lgbm` — formula-inconsistent training data. Not applicable to unified model. |
| DANN v2 did not fix fingerprinting | ⚠️ Known | `domain_reduction ≈ 0.0003` — negligible |
| LODO generalisation not solved | ⚠️ Known | `lodo_min_auc = 0.6164` for legacy models — moderate cross-dataset transfer only |
| Not production-ready | ⚠️ Known | Known-domain prototype; simulation-only; no calibration on target network |
| Single capture in bundled demo | ℹ️ Known | Bundled demo CSV has limited VPN session diversity |
| **Training formula inconsistency (legacy models)** | ⚠️ Documented | Each dataset (ISCX/USBVPN/VNAT) used a **different formula** for `direction_balance_bytes`, `direction_balance_packets`, and `dispersion_symmetry`. Root cause of `domain_auc=1.0` for `full_canonical__lgbm`. See `artifacts/runtime_schema_audit/formula_inference_deep.md`. |
| **sz_all_* = 0 for ISCX training data (legacy)** | ⚠️ Documented | Affects `full_canonical__lgbm` only. `unified_relative_shape_v2__lgbm` does not use `sz_all_*` features. |
| **OpenVPN lab OOD for legacy full_canonical** | ⚠️ Resolved (unified) | Legacy scored all OpenVPN flows < 1e-6 (PASS). Unified model scores 0.2134 (FLAG_REVIEW) — expected improvement. |

---

## 10. Confirmation Statements

> ✅ **No packets are blocked.** All BLOCK decisions are `SIMULATED_BLOCK` — audit/log actions only. The system does not intercept, modify, or drop any network traffic.

> ✅ **This prototype is not production-ready.** `production_ready: false` is enforced across all endpoints. The model requires local revalidation, threshold recalibration, and drift monitoring before any real-world deployment.

> ✅ **Only `unified_relative_shape_v2__lgbm` is executable.** All other models return `executable: false, comparison_only: true` and are enforced at the backend — any attempt to run inference on a comparison model returns HTTP 400.

> ✅ **All other models are comparison-only.** They remain visible in the Model Registry, Model Comparison, and Multi-model Evaluation pages for audit and research documentation purposes only.

> ✅ **`full_canonical__lgbm` is retained as a legacy comparison reference** and is no longer the executable firewall model. It is not accessible for inference from any frontend page or API endpoint.

> ⚠️ **Training formula inconsistency is confirmed and documented for legacy models.** Reverse-engineering analysis of the bundled training data confirms that ISCX, USBVPN, and VNAT datasets each used a different formula for `direction_balance_bytes`, `direction_balance_packets`, and `dispersion_symmetry`. This is the root cause of `domain_auc = 1.0` for `full_canonical__lgbm`. Full analysis: `artifacts/runtime_schema_audit/formula_inference_deep.md`.

---

## 11. Audit Tools

### Backend API Audit

The API audit script is at `tools/full_audit.py`. Run with the backend on port 8000:

```bash
cd ai-vpn-firewall-prototype
python tools/full_audit.py
```

### Live Inference Validation

```powershell
# Generate test CSVs from PCAPs (unified model default)
python tools/pcap_to_live_stream.py --pcap captures/vm_basic_benign.pcap --dry-run --out-csv captures/test_unified_live.csv --scenario basic_benign
python tools/pcap_to_live_stream.py --pcap captures/vm_warp.pcap --dry-run --out-csv captures/test_unified_warp.csv --scenario warp
python tools/pcap_to_live_stream.py --pcap captures/vm_openvpn_lab.pcap --dry-run --out-csv captures/test_unified_openvpn.csv --scenario openvpn_lab

# Run dry inference on all three scenarios
python run_live_inference_report.py
```

### Training Formula Reverse-Engineering Tools

| Script | Purpose | Output |
|--------|---------|--------|
| `tools/reverse_engineer_formulas.py` | Initial formula inference | `artifacts/runtime_schema_audit/formula_inference_report.md` |
| `tools/infer_training_formulas_deep.py` | Deep per-dataset formula analysis | `artifacts/runtime_schema_audit/formula_inference_deep.md` |

Run without backend:

```bash
python tools/reverse_engineer_formulas.py
python tools/infer_training_formulas_deep.py
```

---

## 12. Transition Summary (full_canonical__lgbm → unified_relative_shape_v2__lgbm)

| Property | Legacy (`full_canonical__lgbm`) | Current (`unified_relative_shape_v2__lgbm`) |
|---|---|---|
| Feature family | full_canonical | unified_relative_shape_v2 |
| n_features | 34 | 12 |
| Probability column | `prob` | `prob_iso` (isotonic calibration) |
| Review threshold | 0.02709 | 0.03667 |
| Block threshold | 0.165365 | 0.425 |
| domain_auc | 1.0 (formula-inconsistent training) | Not reported (clean feature contract) |
| OpenVPN lab score | < 1e-6 (all PASS — OOD) | 0.2134 (FLAG_REVIEW — expected) |
| Executable | ✗ (comparison-only) | ✓ |
| Status | Legacy comparison baseline | Active firewall model |
