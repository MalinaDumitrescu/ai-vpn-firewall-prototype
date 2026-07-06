# Prototype Integration Guide — Frontend Model Details

**Experiment:** unified_feature_contract_v2  
**Date:** 2026-05-30  
**For use by:** prototype app agent / frontend developer  

---

## 1. Source Files to Copy

Copy the entire `artifacts/frontend_model_details/` folder into the prototype backend:

```
SOURCE:
  C:/Users/scoti/PycharmProjects/ai-vpn-firewall/artifacts/frontend_model_details/

TARGET (suggestion):
  <prototype_root>/backend/runtime_bundle/app_runtime_bundle/frontend_model_details/
```

Files to copy:

| File | Purpose |
|------|---------|
| `model_detail_inventory.csv` | Full model registry for backend model loader |
| `model_cards_frontend.json` | Rich model card data for Models page and Dashboard |
| `model_feature_details.json` | Feature lists, formulas, type tags for all models |
| `model_metrics_summary.json` | All metrics per model for comparison tables |
| `model_metrics_summary.csv` | CSV version for tabular display |
| `benchmark_compatibility.json` | Which models can run in which benchmark CSV schemas |
| `frontend_page_content.json` | Pre-structured content for each frontend page |
| `missing_frontend_details.md` | To-do list for the frontend developer |
| `prototype_integration_guide.md` | This file |

---

## 2. How Dashboard Should Consume These Files

Load `frontend_page_content.json` → `pages.Dashboard`:

```python
with open("frontend_model_details/frontend_page_content.json") as f:
    content = json.load(f)

dashboard = content["pages"]["Dashboard"]
active_model = dashboard["active_model_summary"]
# → model_id, display_name, test_auc, lodo_min_auc, domain_auc, deployment_score
# → show in the active model card

compact_metrics = dashboard["compact_metrics"]
# → render as metric badges/chips with label, value, badge color

warning_banner = dashboard["warning_banner"]
# → persistent warning banner at top: "SIMULATION ONLY — No packets are blocked..."

limitation_notes = dashboard["limitation_notes"]
# → expandable "known limitations" section below active model card
```

---

## 3. How Models Page Should Consume These Files

Load `model_cards_frontend.json` → `cards`:

```python
with open("frontend_model_details/model_cards_frontend.json") as f:
    cards = json.load(f)["cards"]

for model_id, card in cards.items():
    # card["title"] → card heading
    # card["badges"] → badge list
    # card["short_explanation"] → description paragraph
    # card["why_selected"] or card["why_not_selected"] → bullet list
    # card["metrics"] → metric table
    # card["thresholds"] → threshold display
    # card["caveats"] → collapsible caveats section
    # card["live_extractor_compatible"] → compatibility chip
    # card["live_pcap_status"] → validation status chip
```

Load `model_feature_details.json` → per-model feature list:

```python
with open("frontend_model_details/model_feature_details.json") as f:
    feat_details = json.load(f)["models"]

features = feat_details["unified_relative_shape_v2__lgbm"]["features"]
for name, meta in features.items():
    # meta["formula"] → tooltip on feature name
    # meta["is_ratio_feature"] → ratio badge
    # meta["is_directional_feature"] → directional badge
    # meta["previous_fingerprinting_concern"] → warning icon
    # meta["live_extractor_compatible"] → compatibility status
```

---

## 4. How Robustness Page Should Consume These Files

Load `frontend_page_content.json` → `pages.RobustnessPage`:

```python
robustness = content["pages"]["RobustnessPage"]

# robustness["final_research_outcome"] → headline + detail paragraph at top
# robustness["domain_fingerprinting_story"] → waterfall/bullet list
# robustness["lodo_negative_control_interpretation"] → LODO section
# robustness["live_validation_caveat"] → validation status box
# robustness["deployment_checklist"] → checklist table (status = DONE / PENDING)
# robustness["what_is_not_solved"] → honest limitations section
```

Load `model_metrics_summary.json` for LODO heatmap data:

```python
with open("frontend_model_details/model_metrics_summary.json") as f:
    metrics = json.load(f)["models"]

# build LODO heatmap:
lodo_data = [
    (m["model_id"], m["lodo_iscx_auc"], m["lodo_vnat_auc"], m["lodo_min_auc"])
    for m in metrics if m["lodo_iscx_auc"] is not None
]
```

---

## 5. How Model Comparison Should Use Benchmark Compatibility

Load `benchmark_compatibility.json`:

```python
with open("frontend_model_details/benchmark_compatibility.json") as f:
    compat = json.load(f)

# For each model the user tries to add to comparison:
model_compat = compat["models"][model_id]

if not model_compat["selectable_in_model_comparison"]:
    show_disabled_reason(model_compat["reason_not_selectable"])
else:
    required_features = model_compat["required_features"]
    # validate uploaded CSV contains all required features
    if uploaded_csv_missing_features(required_features):
        show_warning("Uploaded CSV is missing required features for this model.")
    else:
        run_model_inference(model_id, csv)
```

Cross-schema warning:
```python
selected_schemas = set(
    compat["models"][mid]["required_csv_schema"]
    for mid in selected_model_ids
    if compat["models"].get(mid)
)
if len(selected_schemas) > 1:
    show_banner("WARNING: Selected models require different CSV schemas. "
                "Cross-schema comparison may produce misleading results.")
```

---

## 6. Fields That Must NOT Be Editable in the Frontend

The following fields must be read-only and never editable through the UI:

| Field | Reason |
|-------|--------|
| `production_ready` | Always `false` in this release. |
| `action_mode` | Always `simulation`. Must not be changed to `enforce`. |
| `model_id` | Immutable identifier. |
| `extractor_version` | Fixed to `unified_v2.0`. |
| `feature_order` | Fixed feature list. Must not be user-editable. |
| `thresholds.policy` | Policy string (`PASS/FLAG_REVIEW/SIMULATED_BLOCK`). |
| `live_extractor_compatible` | Determined by experiment, not UI config. |
| `calibration_method` | Trained artifact. Not runtime-configurable. |

Thresholds (`review_threshold`, `block_threshold`) **may** be exposed as read-only display but should not be editable in the frontend without a backend threshold recalibration pipeline.

---

## 7. Additional Figures to Copy

Copy these figures into the prototype's static assets:

```
SOURCE: artifacts/unified_feature_contract_v2/figures/
TARGET: <prototype_root>/frontend/src/assets/figures/unified_feature_contract_v2/

Key figures:
  01_pooled_auc_comparison.png     → Models comparison page
  02_lodo_min_ranking.png          → Robustness page
  03_lodo_per_dataset.png          → Robustness page (LODO heatmap)
  04_domain_auc_comparison.png     → Robustness page (fingerprinting section)
  05_performance_vs_fingerprint.png → Robustness page (scatter)
  06_calibration_ece.png           → Models page (per-model calibration)
  07_confusion_matrices_top3.png   → Models page (top 3 models)
  09_anti_fingerprint_scores.png   → Robustness page (feature importance)
  10_legacy_vs_unified.png         → Dashboard or Models page header
  11_deployment_score_ranking.png  → Model comparison page
```

---

## 8. Demo CSV Integration

The demo CSV is ready for the prototype:

```
SOURCE: artifacts/unified_feature_contract_v2/runtime_export/demo_data/unified_model_demo_flows.csv
TARGET: <prototype_root>/backend/runtime_bundle/app_runtime_bundle/demo_data/unified_model_demo_flows.csv
```

- 588 rows, 10 captures, 12 feature columns
- Metadata columns: `capture_id`, `flow_id`, `dataset`, `label`
- `label` is metadata only — must NOT be passed as model input
- Expected results: TP=338, FN=58, TN=187, FP=5 (at block threshold 0.425)

---

## 9. Not-Yet-Available Items

The following should NOT be shown in the frontend until completed:

| Item | Status |
|------|--------|
| Live PCAP validation results | PENDING |
| End-to-end VM traffic test | PENDING |
| Production-ready threshold tuning | PENDING |
| DANN/GroupDRO in unified pipeline (full LODO) | PENDING |
| USBVPN LODO AUC | UNAVAILABLE — test set too imbalanced |
