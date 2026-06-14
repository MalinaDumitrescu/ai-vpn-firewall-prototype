#!/usr/bin/env python3
"""
validate_unified_model_csv.py
==============================
Validate a CSV against unified_relative_shape_v2__lgbm (or another model).

Usage:
  python tools/validate_unified_model_csv.py --csv captures/test.csv
  python tools/validate_unified_model_csv.py --csv captures/test.csv --model-id unified_relative_shape_v2__lgbm
  python tools/validate_unified_model_csv.py --csv captures/test.csv --dry-inference

Checks:
  - All required features present (from feature_order.json)
  - All feature columns are numeric
  - No NaN or Inf values in feature columns
  - Metadata columns present (optional)
  - Optionally runs dry inference with the backend engine

Prints:
  VALID FOR unified_relative_shape_v2__lgbm   (on success)
  INVALID FOR unified_relative_shape_v2__lgbm (on failure, with details)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


_SCRIPT_DIR  = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent


DEFAULT_MODEL_ID = "unified_relative_shape_v2__lgbm"

FEATURES_BY_MODEL: Dict[str, List[str]] = {
    "unified_relative_shape_v2__lgbm": [
        "sz_cv", "sz_iqr", "sz_qratio", "sz_median_to_mean",
        "sz_p25_median_ratio", "sz_p75_median_ratio", "sz_iqr_norm_median",
        "iat_cv", "iat_iqr",
        "direction_balance_bytes", "direction_balance_packets", "dispersion_symmetry",
    ],
    "full_canonical__lgbm": [
        "sz_coef_variation", "sz_p25_median_ratio", "sz_p75_median_ratio",
        "sz_iqr_norm_median", "dispersion_symmetry", "direction_balance_bytes",
        "direction_balance_packets", "sz_mean_max", "sz_mean_min",
        "sz_std_max", "sz_std_min", "iat_all_mean", "iat_all_std",
        "iat_all_p25", "iat_all_median", "iat_all_p75", "iat_mean_max",
        "iat_mean_min", "iat_std_max", "iat_std_min", "sz_all_mean",
        "sz_all_std", "sz_all_median", "sz_all_p25", "sz_all_p75",
        "sz_cv", "sz_iqr", "sz_qratio", "sz_median_to_mean",
        "iat_iqr", "iat_cv", "iat_median", "iat_p25", "iat_p75",
    ],
}

OPTIONAL_META_COLS = [
    "capture_id", "session_id", "flow_id", "dataset", "label",
    "timestamp", "src_ip", "dst_ip", "protocol", "dst_port", "scenario",
]


def _load_feature_order_from_bundle(model_id: str) -> Optional[List[str]]:
    """Try to load feature_order.json from the runtime bundle."""
    bundle_path = (
        _PROJECT_ROOT
        / "backend"
        / "runtime_bundle"
        / "app_runtime_bundle"
        / "runtime_models"
        / model_id
        / "feature_order.json"
    )
    if not bundle_path.exists():
        return None
    try:
        with bundle_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data.get("features") or data.get("feature_order") or []
    except Exception:
        return None


def validate_csv(
    csv_path: str,
    model_id: str = DEFAULT_MODEL_ID,
    dry_inference: bool = False,
    verbose: bool = True,
) -> bool:
    """Validate a CSV file against the given model's feature schema.

    Returns True if valid, False otherwise.
    """
    import pandas as pd

    path = Path(csv_path)
    if not path.exists():
        print(f"[ERROR] CSV file not found: {path.resolve()}")
        return False

    # Load feature list — try bundle first, fall back to hardcoded
    feature_list = _load_feature_order_from_bundle(model_id)
    if feature_list is None:
        feature_list = FEATURES_BY_MODEL.get(model_id)
    if feature_list is None:
        print(f"[ERROR] Unknown model_id '{model_id}'. Known models: {list(FEATURES_BY_MODEL)}")
        return False

    print(f"\n=== Validating CSV for {model_id} ===")
    print(f"  CSV: {path.resolve()}")
    print(f"  Expected features ({len(feature_list)}): {feature_list}\n")

    # Load CSV
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        print(f"[ERROR] Cannot read CSV: {exc}")
        return False

    print(f"  Rows: {len(df)},  Columns: {len(df.columns)}")

    errors: List[str] = []
    warnings: List[str] = []

    missing_feats = [f for f in feature_list if f not in df.columns]
    if missing_feats:
        errors.append(f"Missing {len(missing_feats)} required feature(s): {missing_feats}")
    else:
        print(f"  [OK] All {len(feature_list)} required features present.")

    present_meta = [c for c in OPTIONAL_META_COLS if c in df.columns]
    missing_meta = [c for c in ["capture_id", "session_id"] if c not in df.columns]
    if present_meta:
        print(f"  [OK] Optional metadata columns present: {present_meta}")
    if missing_meta:
        warnings.append(f"Optional session/grouping columns missing: {missing_meta} (not required for validation)")

    if not missing_feats:
        nan_counts: Dict[str, int] = {}
        inf_counts: Dict[str, int] = {}
        non_numeric: List[str]    = []

        for feat in feature_list:
            col = df[feat]
            if not pd.api.types.is_numeric_dtype(col):
                non_numeric.append(feat)
                continue
            n_nan = int(col.isna().sum())
            n_inf = int((col == float("inf")).sum() + (col == float("-inf")).sum())
            if n_nan > 0:
                nan_counts[feat] = n_nan
            if n_inf > 0:
                inf_counts[feat] = n_inf

        if non_numeric:
            errors.append(f"Non-numeric feature columns: {non_numeric}")
        else:
            print(f"  [OK] All {len(feature_list)} feature columns are numeric.")

        if nan_counts:
            errors.append(f"NaN values in features: {nan_counts}")
        else:
            print(f"  [OK] No NaN values in feature columns.")

        if inf_counts:
            errors.append(f"Inf values in features: {inf_counts}")
        else:
            print(f"  [OK] No Inf values in feature columns.")

    forbidden = ["dataset", "label", "capture_id", "session_id", "flow_id", "source_file"]
    present_forbidden = [c for c in forbidden if c in df.columns]
    if present_forbidden:
        warnings.append(
            f"Forbidden model-input columns present (OK as metadata, do not feed to model): {present_forbidden}"
        )

    if warnings:
        for w in warnings:
            print(f"  [WARN] {w}")

    if dry_inference and not errors:
        print("\n  [*] Running dry inference via backend engine...")
        try:
            sys.path.insert(0, str(_PROJECT_ROOT / "backend"))
            from app.runtime_model_inference import get_engine  # type: ignore
            engine = get_engine(model_id)
            result = engine.run(df)
            if result.get("skipped"):
                errors.append(
                    f"Inference skipped — missing features: {result.get('missing_features')}"
                )
            else:
                print(f"  [OK] Dry inference passed: {result['total_flows']} flows, "
                      f"{result['total_sessions']} sessions, counts={result['counts']}")
        except Exception as exc:
            errors.append(f"Dry inference failed: {exc}")

    print()
    if errors:
        print(f"INVALID FOR {model_id}")
        for e in errors:
            print(f"  [ERROR] {e}")
        return False
    else:
        print(f"VALID FOR {model_id}")
        print(f"  model_id       : {model_id}")
        print(f"  feature_schema : unified_relative_shape_v2" if "unified_relative_shape_v2" in model_id else f"  feature_schema : {model_id}")
        print(f"  feature_count  : {len(feature_list)}")
        print(f"  action_mode    : simulation")
        print(f"  production_readiness : False")
        return True


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="validate_unified_model_csv.py",
        description=(
            "Validate a CSV against unified_relative_shape_v2__lgbm (or another model).\n\n"
            "Checks required features, numeric types, NaN/Inf values,\n"
            "and optionally runs dry inference via the backend engine.\n\n"
            "Prints: VALID FOR <model_id> or INVALID FOR <model_id>\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--csv",
        required=True,
        metavar="PATH",
        help="Path to the CSV file to validate.",
    )
    p.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        metavar="MODEL_ID",
        help=(
            f"Model ID to validate against (default: {DEFAULT_MODEL_ID}). "
            "Choices: " + ", ".join(FEATURES_BY_MODEL.keys())
        ),
    )
    p.add_argument(
        "--dry-inference",
        action="store_true",
        help=(
            "Also run dry inference via the backend engine (requires backend to be importable). "
            "Only runs if all schema checks pass."
        ),
    )
    return p


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    valid = validate_csv(
        csv_path=args.csv,
        model_id=args.model_id,
        dry_inference=args.dry_inference,
    )
    sys.exit(0 if valid else 1)


if __name__ == "__main__":
    main()

