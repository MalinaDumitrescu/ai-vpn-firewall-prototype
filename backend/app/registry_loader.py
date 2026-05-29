"""Read-only access to the standalone runtime bundle (registry + policy files)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

# Bundle root: backend/runtime_bundle/app_runtime_bundle/
BUNDLE_ROOT = Path(__file__).resolve().parent.parent / "runtime_bundle" / "app_runtime_bundle"

REGISTRY_PATH = BUNDLE_ROOT / "app_model_registry" / "backend" / "model_registry" / "registry.json"
REGISTRY_PACKAGES_DIR = BUNDLE_ROOT / "app_model_registry" / "backend" / "model_registry"
UI_GROUPS_PATH = BUNDLE_ROOT / "app_model_registry" / "backend" / "model_registry" / "ui_model_groups.json"
ALLOWLIST_PATH = BUNDLE_ROOT / "app_model_registry" / "backend" / "model_registry" / "runtime_inference_allowlist.json"
RUNTIME_MODELS_DIR = BUNDLE_ROOT / "runtime_models"
DEMO_FLOWS_PATH = BUNDLE_ROOT / "demo_data" / "demo_flows.csv"
DEMO_FLOWS_FULL_CANONICAL_PATH = BUNDLE_ROOT / "demo_data" / "demo_flows_full_canonical.csv"
COMPARISON_CSV_PATH = (
    BUNDLE_ROOT / "app_model_registry" / "reports" / "tables" / "app_model_policy_comparison.csv"
)


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_registry() -> Dict[str, Any]:
    data = _read_json(REGISTRY_PATH)
    if data is None:
        raise FileNotFoundError(f"Registry not found at {REGISTRY_PATH}")
    return data


def list_models() -> Dict[str, Any]:
    return load_registry().get("models", {})


def get_model_entry(model_id: str) -> Optional[Dict[str, Any]]:
    return list_models().get(model_id)


def _package_dir(model_id: str, entry: Dict[str, Any]) -> Path:
    """Resolve the registry package dir for a model.

    Registry's ``package_dir`` is recorded as ``backend/model_registry/<id>`` —
    relative to the bundled ``app_model_registry/`` root.
    """
    pkg = entry.get("package_dir", f"backend/model_registry/{model_id}")
    # Strip leading "backend/model_registry/" if present
    rel = pkg.split("backend/model_registry/", 1)[-1]
    return REGISTRY_PACKAGES_DIR / rel


def _runtime_dir(model_id: str) -> Path:
    return RUNTIME_MODELS_DIR / model_id


def _load_first(model_id: str, filename: str) -> Optional[Dict[str, Any]]:
    """Try runtime_models/<id>/file first, then registry package dir."""
    entry = get_model_entry(model_id) or {}
    candidates = [
        _runtime_dir(model_id) / filename,
        _package_dir(model_id, entry) / filename,
    ]
    for path in candidates:
        if path.exists():
            return _read_json(path)
    return None


def get_model_card(model_id: str) -> Optional[Dict[str, Any]]:
    return _load_first(model_id, "model_card.json")


def get_thresholds(model_id: str) -> Optional[Dict[str, Any]]:
    return _load_first(model_id, "thresholds.json")


def get_policy_report(model_id: str) -> Optional[Dict[str, Any]]:
    return _load_first(model_id, "policy_report.json")


def get_session_metrics(model_id: str) -> Optional[Dict[str, Any]]:
    return _load_first(model_id, "session_metrics.json")


def get_calibration_info(model_id: str) -> Optional[Dict[str, Any]]:
    return _load_first(model_id, "calibration_info.json")


def find_default_models() -> Dict[str, Dict[str, Any]]:
    """Return models with status 'default_firewall' or 'recommended_firewall'."""
    return {
        mid: entry
        for mid, entry in list_models().items()
        if entry.get("status") in ("default_firewall", "recommended_firewall")
    }


def get_default_firewall_model_id() -> Optional[str]:
    """Return the default_firewall model ID from the inference allowlist."""
    try:
        alist = _read_json(ALLOWLIST_PATH)
        if alist:
            return alist.get("default_firewall")
    except Exception:
        pass
    # Fallback: find from registry
    defaults = find_default_models()
    if defaults:
        return next(iter(defaults))
    return None


# ----------------------------------------------------------------- UI groups

def load_ui_groups() -> Dict[str, Any]:
    data = _read_json(UI_GROUPS_PATH)
    if data is None:
        raise FileNotFoundError(f"ui_model_groups.json not found at {UI_GROUPS_PATH}")
    return data


def _group_ids(group_key: str) -> list:
    data = load_ui_groups()
    # Support both {"groups": {...}} (current bundle) and a flat layout.
    groups = data.get("groups", data)
    ids = groups.get(group_key)
    if ids is None:
        return []
    return list(ids)


def get_models_in_group(group_key: str) -> list:
    """Return ``[{"model_id": id, ...entry}]`` for all ids in the group, sorted by ui_sort_order."""
    ids = _group_ids(group_key)
    models = list_models()
    out = []
    for mid in ids:
        entry = models.get(mid)
        if entry is None:
            continue
        out.append({"model_id": mid, **entry})
    out.sort(key=lambda e: (e.get("ui_sort_order", 9999), e.get("model_id", "")))
    return out


# ----------------------------------------------------------- inference allowlist

def load_inference_allowlist() -> Dict[str, Any]:
    data = _read_json(ALLOWLIST_PATH)
    if data is None:
        raise FileNotFoundError(f"runtime_inference_allowlist.json not found at {ALLOWLIST_PATH}")
    return data


def get_allowlisted_model_ids() -> list:
    """Return the list of model_ids from the runtime inference allowlist."""
    return list(load_inference_allowlist().get("allowlist", []))


def get_runtime_model_dir(model_id: str) -> Path:
    return RUNTIME_MODELS_DIR / model_id

