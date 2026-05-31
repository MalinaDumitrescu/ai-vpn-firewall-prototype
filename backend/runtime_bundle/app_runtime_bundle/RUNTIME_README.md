    # Runtime Export — unified_feature_contract_v2

    **Generated**: 2026-05-30  
    **Experiment**: `unified_feature_contract_v2`  
    **Selected model**: `unified_relative_shape_v2__lgbm`  

    ---

    ## ⚠️ SIMULATION ONLY — NOT PRODUCTION-READY

    This model is a **research prototype**. It operates in **simulation mode only**.
    - No network packets are blocked or modified.
    - Outputs are scored decisions for academic evaluation.
    - Must NOT be deployed to production without live PCAP validation.

    ---

    ## Selected Model

    | Property | Value |
    |----------|-------|
    | model_id | `unified_relative_shape_v2__lgbm` |
    | feature_family | `unified_relative_shape_v2` |
    | n_features | 12 |
    | model_type | LightGBM + isotonic calibration |
    | test_auc | 0.9826 |
    | lodo_min_auc | 0.6366 |
    | domain_auc | 0.9591 |
    | deployment_score | 0.4691 (highest among 30 trained models) |
    | runtime_compatible | Yes |
    | live_extractor_compatible | Yes — `unified_extractor.py` v2.0 |
    | production_ready | **No** |
    | action_mode | simulation |

    ---

    ## Feature Family: `unified_relative_shape_v2`

    **12 ratio/relative-shape features** (scale-invariant, anti-fingerprinting):

    - `sz_cv`
- `sz_iqr`
- `sz_qratio`
- `sz_median_to_mean`
- `sz_p25_median_ratio`
- `sz_p75_median_ratio`
- `sz_iqr_norm_median`
- `iat_cv`
- `iat_iqr`
- `direction_balance_bytes`
- `direction_balance_packets`
- `dispersion_symmetry`

    ### Feature conventions (from `extractor_config.json`)

    - **Packet size**: IP total length (bytes)
    - **Timestamps**: seconds
    - **Direction**: `1 = upload / client-to-server`, `0 = download / server-to-client`
    - **Window**: first `100` packets per flow
    - **Min packets**: `3`
    - **eps**: `1e-06`
    - **Extractor version**: `unified_v2.0`

    ---

    ## Policy Thresholds

    | Action | Threshold |
    |--------|-----------|
    | `PASS` | calibrated score < 0.0367 |
    | `FLAG_REVIEW` | 0.0367 ≤ score < 0.4250 |
    | `SIMULATED_BLOCK` | score ≥ 0.4250 |

    ---

    ## Directory Structure

    ```
    runtime_export/
    ├── runtime_models/
    │   └── unified_relative_shape_v2__lgbm/
    │       ├── model.pkl                  # trained LightGBM classifier
    │       ├── calibrator.pkl             # isotonic regression calibrator
    │       ├── feature_order.json         # required input columns (12)
    │       ├── thresholds.json            # review + block thresholds
    │       ├── feature_family.json        # feature family metadata
    │       ├── feature_contract.json      # full extractor contract
    │       ├── extractor_config.json      # extractor conventions
    │       └── model_card.md              # model card
    ├── app_model_registry/
    │   ├── unified_firewall_candidate.json  # full registry entry
    │   └── model_registry.csv              # summary CSV
    ├── reports/
    │   ├── final_report.md
    │   ├── thesis_summary.md
    │   ├── unified_formula_report.md
    │   ├── feature_contract.json
    │   ├── model_comparison.csv
    │   ├── lodo_results.csv
    │   ├── domain_fingerprint_results.csv
    │   ├── calibration_results.csv
    │   ├── anti_fingerprint_feature_scores.csv
    │   └── recommended_models.json
    ├── demo_data/
    │   └── (demo CSV to be generated in next phase)
    ├── scripts/
    │   └── smoke_test_unified_model.py
    ├── requirements_runtime.txt
    ├── RUNTIME_README.md
    └── smoke_test_output.txt
    ```

    ---

    ## How to Validate a CSV

    Your input CSV must contain these columns (in any order):

    ```
    sz_cv, sz_iqr, sz_qratio, sz_median_to_mean, sz_p25_median_ratio, sz_p75_median_ratio, sz_iqr_norm_median, iat_cv, iat_iqr, direction_balance_bytes, direction_balance_packets, dispersion_symmetry
    ```

    Load and score:

    ```python
    import joblib, json, pandas as pd
    from pathlib import Path

    BASE = Path("runtime_export/runtime_models/unified_relative_shape_v2__lgbm")
    clf  = joblib.load(BASE / "model.pkl")
    iso  = joblib.load(BASE / "calibrator.pkl")
    feat = json.load(open(BASE / "feature_order.json"))["features"]
    thr  = json.load(open(BASE / "thresholds.json"))

    df = pd.read_csv("your_flows.csv")
    X  = df[feat].values
    p_raw = clf.predict_proba(X)[:, 1]
    p_cal = iso.predict(p_raw)

    def action(p):
        if p >= thr["block_threshold"]:  return "SIMULATED_BLOCK"
        if p >= thr["review_threshold"]: return "FLAG_REVIEW"
        return "PASS"

    df["vpn_score"]  = p_cal
    df["decision"]   = [action(p) for p in p_cal]
    print(df[["vpn_score", "decision"]].value_counts())
    ```

    ---

    ## How to Run Smoke Test

    ```bash
    python runtime_export/scripts/smoke_test_unified_model.py
    ```

    Expected output (artifact-load check):
    ```
    [smoke_test] Model artifacts loaded OK
    [smoke_test] Features (12): sz_cv, sz_iqr, ...
    [smoke_test] Zero-vector inference: score=X.XXXX  action=PASS|FLAG_REVIEW|SIMULATED_BLOCK
    [smoke_test] production_ready = False
    [smoke_test] action_mode      = simulation
    [smoke_test] PASSED
    ```

    ---

    ## Should this replace the legacy model?

    **Not automatically.** Required steps before replacing `full_canonical__lgbm`:

    1. ✅ Unified model bundle exported (this folder)
    2. ⬜ Live PCAP validation: run unified extractor on known VPN traffic (Warp, OpenVPN)
    3. ⬜ Confirm FPR acceptable on live benign traffic
    4. ⬜ Side-by-side comparison in prototype with both models running in parallel
    5. ⬜ Threshold re-calibration on live traffic distribution

    **For scientific reporting**: use the unified model as the methodologically correct result.
    Present the legacy model's AUC=0.9994 with the dataset-fingerprinting caveat (domain AUC=1.0).

    ---

    ## Key metrics vs legacy

    | Metric | Legacy `full_canonical__lgbm` | Unified `unified_relative_shape_v2__lgbm` | Δ |
    |--------|-------------------------------|----------------------|---|
    | Test AUC | 0.9994 | 0.9826 | −0.0168 |
    | LODO-min AUC | 0.6164 | **0.6366** | **+0.0202** |
    | Domain AUC | 1.0000 | **0.9591** | **−0.0409** |
    | n_features | ~33 | 12 | −21 |

    ---

    *This bundle was generated by `scripts/build_runtime_export_candidate.py`.*
    *No models were retrained. No production bundles were overwritten.*
