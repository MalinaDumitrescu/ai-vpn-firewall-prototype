"""CSV ingestion helpers."""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List

import pandas as pd

from .registry_loader import BUNDLE_ROOT, COMPARISON_CSV_PATH, DEMO_FLOWS_PATH
from .robust9_inference import REQUIRED_FEATURES

DEMO_MULTIMODEL_FLOWS_PATH = BUNDLE_ROOT / "demo_data" / "demo_multimodel_flows.csv"


def load_demo_flows() -> pd.DataFrame:
    if not DEMO_FLOWS_PATH.exists():
        raise FileNotFoundError(f"Demo CSV missing: {DEMO_FLOWS_PATH}")
    return pd.read_csv(DEMO_FLOWS_PATH)


def load_multimodel_demo_flows() -> pd.DataFrame:
    if not DEMO_MULTIMODEL_FLOWS_PATH.exists():
        raise FileNotFoundError(f"Multimodel demo CSV missing: {DEMO_MULTIMODEL_FLOWS_PATH}")
    return pd.read_csv(DEMO_MULTIMODEL_FLOWS_PATH)


def parse_uploaded_csv(raw_bytes: bytes) -> pd.DataFrame:
    try:
        df = pd.read_csv(io.BytesIO(raw_bytes))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Could not parse uploaded CSV: {exc}") from exc
    missing = [c for c in REQUIRED_FEATURES if c not in df.columns]
    if missing:
        raise ValueError(
            "Uploaded CSV is missing required robust9 feature columns: " + ", ".join(missing)
        )
    return df


def parse_multimodel_csv(raw_bytes: bytes) -> pd.DataFrame:
    """Parse an uploaded CSV for multi-model evaluation. No feature validation here —
    each engine validates its own required features and gracefully skips if missing."""
    try:
        return pd.read_csv(io.BytesIO(raw_bytes))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Could not parse uploaded CSV: {exc}") from exc


def load_comparison_rows() -> List[Dict[str, Any]]:
    if not COMPARISON_CSV_PATH.exists():
        raise FileNotFoundError(f"Comparison CSV missing: {COMPARISON_CSV_PATH}")
    rows: List[Dict[str, Any]] = []
    with COMPARISON_CSV_PATH.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append({k: (v if v != "" else None) for k, v in r.items()})
    return rows



