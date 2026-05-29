# App Model UI Grouping — Summary

- Generated: 2026-05-26 (UTC)
- Source registry: `backend/model_registry/registry.json`
- UI groups helper: `backend/model_registry/ui_model_groups.json`
- CSV: `reports/tables/app_model_ui_groups.csv`
- Inject script: `scripts/apply_ui_grouping_metadata.py`

This task adds **UI/API grouping metadata** to the registry so that the
FastAPI + React prototype can:

1. show only useful models on the main comparison page,
2. surface unsafe-but-interesting high-AUC benchmarks behind an explicit
   "advanced" entry,
3. expose LODO models only as documented negative-control evidence, and
4. hide aliases and unsupported stubs from normal selectors.

**No metrics, thresholds, default-firewall assignment, alias targets, or
deployment flags were changed.** Only additive UI fields were written.

## Fields added to every registry entry and (where present) `model_card.json`

| field | purpose |
|---|---|
| `ui_group` | one of `main_demo_comparison`, `advanced_unsafe_benchmark`, `robustness_negative_control`, `hidden_alias_or_unsupported` |
| `ui_visible_main` | true only for `main_demo_comparison` |
| `ui_selectable_for_comparison` | true for `main_demo_comparison` and `advanced_unsafe_benchmark` |
| `ui_selectable_for_firewall_inference` | true **only** for `robust9_firewall` |
| `ui_badge` | short label shown next to the model name in the UI |
| `ui_warning` | concise sentence the UI must display when this model is selected |
| `ui_sort_order` | stable display order |

## Models shown in main comparison (`main_demo_comparison`)

These are visible on the main comparison page (`ui_visible_main = true`,
`ui_selectable_for_comparison = true`):

| sort | model_id | badge | warning |
|---:|---|---|---|
| 1 | `robust9_firewall` | Default known-domain prototype | Simulation-only default model. Strong known-domain performance, not production-ready. |
| 2 | `balanced_bagging_3ds_reference` | Comparison-only | Comparison-only, not deployment-approved. |
| 3 | `balanced_bagging_xgb_baseline` | Comparison-only | Comparison-only, not deployment-approved. |
| 4 | `balanced_bagging_baseline` | Comparison-only | Comparison-only, not deployment-approved. |
| 5 | `robust13_comparison` | Comparison-only | Comparison-only, not deployment-approved. |
| 6 | `balanced_bagging_tuned_baseline` | Comparison-only | Comparison-only, not deployment-approved. |

## Models hidden from main comparison and why

### A. `advanced_unsafe_benchmark` — high AUC but unsafe to auto-block

Excluded from the main page because their **strict test FPR is nonzero**,
so automatic blocking is disabled at the policy layer. They remain
selectable from the Model Comparison Lab for evaluation purposes.

| sort | model_id | badge | warning |
|---:|---|---|---|
| 20 | `clean_pooled_benchmark` | Blocking disabled — nonzero strict FPR | High AUC but strict FPR is nonzero; automatic blocking is disabled. |
| 21 | `single_model_fallback` | Blocking disabled — nonzero strict FPR | High AUC but strict FPR is nonzero; automatic blocking is disabled. |

### B. `robustness_negative_control` — LODO negative controls

These are the Leave-One-Dataset-Out stress tests. They collapse on the
held-out dataset (session AUC ≈ 0.18–0.81). They must **not** be
selectable for normal comparison and must **never** be deployable.

| sort | model_id | held-out | badge | warning |
|---:|---|---|---|---|
| 30 | `lodo_hold_iscx` | iscx | LODO negative control | Negative control for unseen-domain robustness. Not deployable. |
| 31 | `lodo_hold_usbvpn` | usbvpn | LODO negative control | Negative control for unseen-domain robustness. Not deployable. |
| 32 | `lodo_hold_vnat` | vnat | LODO negative control | Negative control for unseen-domain robustness. Not deployable. |

### C. `hidden_alias_or_unsupported` — aliases and unsupported stubs

These are intentionally hidden from selectors. They are retained for
documentation/traceability only.

| sort | model_id | badge | warning |
|---:|---|---|---|
| 90 | `balanced_bagging_3ds_refresh` | Alias / duplicate | Alias of balanced_bagging_3ds_reference; hide from normal comparison UI. |
| 91 | `historical_3ds_degraded` | Alias / duplicate | Historical/degraded alias; keep for documentation only. |
| 92 | `twentyone_feature_experimental` | Unsupported | Unsupported stub; exact deployable artifact/feature order not recovered. |

## Inference scope — `robust9_firewall` is the only inference model

`ui_selectable_for_firewall_inference = true` is set **only** on
`robust9_firewall`. Every other entry — including the 5 other models in
`main_demo_comparison` — has `ui_selectable_for_firewall_inference = false`.

This complements (and does **not** weaken) the existing safety rules:

- `status == "default_firewall"` is still `robust9_firewall` only (registry R4).
- `supports_live_mode` is still `false` for every entry.
- Runtime binaries are present in the runtime bundle **only** for
  `robust9_firewall` (see below).

## Validation result

```
python scripts/validate_model_registry.py
Validation: PASS  (errors=0, warnings=0)
```

The validator was not relaxed. All 14 rules (R1–R14) still pass with the
new UI fields in place. The validator ignores unknown keys, so the
additive metadata does not affect any rule.

## Export rebuild result

Both export pipelines were re-run **after** validation passed.

### `exports/app_model_registry/` (Task-7 bundle)

```
python scripts/build_app_export_bundle.py
[gate] PASS — proceeding with export.
[ok] Files: 102
[ok] Summary: reports/app_model_registry_export_summary.md
```

The exported `backend/model_registry/registry.json`, each per-model
`model_card.json` (where present), and the new
`backend/model_registry/ui_model_groups.json` all carry the UI fields.

### `exports/app_runtime_bundle/` (Task-8 bundle)

```
python scripts/build_app_runtime_bundle.py
[gate] PASS — building runtime bundle.
[ok] 124 files, 8,650,449 bytes
[ok] Default model files copied: 11
[ok] Demo CSV: exports/app_runtime_bundle/demo_data/demo_flows.csv (16 flows / 2 sessions)
```

Confirmed: `exports/app_runtime_bundle/runtime_models/` contains exactly
**one** subdirectory — `robust9_firewall/` — with the 11 real model
binaries (3 XGB bags + 3 LGBM bags + 3 CatBoost bags + isotonic + platt)
plus its metadata JSONs. No other model received binaries. No notebooks,
raw datasets, training data, logs, or unrelated artifact folders were
copied.

## Files written / updated by this task

- `scripts/apply_ui_grouping_metadata.py` (new)
- `backend/model_registry/registry.json` (UI fields added to every entry; `updated_utc` bumped)
- `backend/model_registry/<model_id>/model_card.json` for all 12 non-alias models (UI fields mirrored)
- `backend/model_registry/ui_model_groups.json` (new helper for API/frontend)
- `reports/tables/app_model_ui_groups.csv` (new)
- `exports/app_model_registry/` (rebuilt)
- `exports/app_runtime_bundle/` (rebuilt)
- `reports/app_model_ui_grouping_summary.md` (this report)

## Out of scope (explicitly NOT done)

- No retraining.
- No edits to `artifacts/` originals.
- No changes to metrics, thresholds, or policy actions.
- No change of `default_firewall` (still `robust9_firewall`).
- No removal of models, aliases, or negative controls from the registry.
- No `supports_live_mode = true` set for any model.
- No change to the FastAPI prototype project. The updated
  `exports/app_runtime_bundle/` will be copied into
  `ai-vpn-firewall-prototype/backend/runtime_bundle/` by the user.

