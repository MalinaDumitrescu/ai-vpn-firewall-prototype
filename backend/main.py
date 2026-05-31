"""FastAPI entrypoint for the AI VPN Firewall Prototype."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from app import registry_loader
from app.registry_loader import EXECUTABLE_FIREWALL_MODEL_ID
from app.csv_service import (
    load_comparison_rows,
    load_benchmark_csv,
    load_demo_flows_unified,
    load_multimodel_demo_flows,
    parse_multimodel_csv,
    parse_uploaded_csv,
)
from app.benchmark_service import (
    run_benchmark,
    run_legacy_benchmark,
    get_legacy_benchmark_model_info,
    COMPATIBLE_BENCHMARK_MODEL_IDS,
    INCOMPATIBLE_MODEL_IDS,
    LEGACY_BENCHMARK_MODEL_IDS,
)
from app.live_replay_service import (
    TEMPLATE_HEADER,
    get_replay_state,
)
from app.live_ingest_service import get_ingest_state
from app.runtime_model_inference import get_engine
from app.schemas import (
    FirewallResult,
    HealthResponse,
    LiveIngestRequest,
    ModelDetailResponse,
    ModelMetricsResponse,
    ModelPolicyResponse,
)
from demo_runner import build_router as build_demo_router

logger = logging.getLogger("ai_vpn_firewall")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="AI VPN Firewall Prototype API",
    version="0.2.0",
    description=(
        "Read-only access to the standalone runtime bundle. "
        "Default inference model: unified_relative_shape_v2__lgbm "
        "(single LightGBM + isotonic calibration, 12 unified relative-shape features, unified_feature_contract_v2). "
        "Legacy models (full_canonical__lgbm, robust9_firewall, etc.) retained for comparison only — not executable. "
        "Inference is simulation-only — no real blocking is performed."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Local demo runner endpoints (POST /demo/run/*, GET /demo/jobs/*).
# SAFETY: this router only launches a fixed allowlist of local PowerShell
# scripts and is intended for local thesis demos only. Do not expose it on
# a public network.
app.include_router(build_demo_router())


# --------------------------------------------------------------------------- enforcement helpers

def _require_executable(model_id: str) -> None:
    """Raise HTTP 400 if model_id is not the single executable firewall model."""
    if model_id != EXECUTABLE_FIREWALL_MODEL_ID:
        raise HTTPException(
            status_code=400,
            detail=(
                f"This model is comparison-only. "
                f"Only '{EXECUTABLE_FIREWALL_MODEL_ID}' is executable in this prototype. "
                f"Requested: '{model_id}'."
            ),
        )


# --------------------------------------------------------------------------- meta

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="AI VPN Firewall Prototype API")


# --------------------------------------------------------------------------- models

@app.get("/models")
def list_models() -> Dict[str, Any]:
    return registry_loader.list_models()


@app.get("/models/default")
def get_default_model() -> Dict[str, Any]:
    # Priority-order selector: hardcoded constant → allowlist → role → deployment_eligible
    default_id = registry_loader.get_default_firewall_model_id()
    if not default_id:
        available = list(registry_loader.list_models().keys())
        raise HTTPException(
            status_code=500,
            detail=(
                f"No executable firewall model found. "
                f"Expected '{EXECUTABLE_FIREWALL_MODEL_ID}'. "
                f"Available model IDs: {available}"
            ),
        )
    entry = registry_loader.get_model_entry(default_id)
    if entry is None:
        raise HTTPException(status_code=500, detail=f"Default model '{default_id}' not found in registry.")
    return {
        "model_id": default_id,
        "executable": True,
        "comparison_only": False,
        "action_mode": "simulation",
        "production_ready": False,
        "warning": "Simulation only. No packets are blocked. Unified feature contract v2 model. Not production-ready.",
        **entry,
    }


# --- UI group endpoints (declared before /models/{model_id} to avoid path collision) ---

@app.get("/models/ui-groups")
def get_ui_groups() -> Dict[str, Any]:
    try:
        return registry_loader.load_ui_groups()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/models/main-comparison")
def get_main_comparison_models() -> List[Dict[str, Any]]:
    return registry_loader.get_models_in_group("main_demo_comparison")


@app.get("/models/advanced-benchmarks")
def get_advanced_benchmark_models() -> List[Dict[str, Any]]:
    return registry_loader.get_models_in_group("advanced_unsafe_benchmark")


@app.get("/models/robustness-controls")
def get_robustness_control_models() -> List[Dict[str, Any]]:
    return registry_loader.get_models_in_group("robustness_negative_control")


@app.get("/models/hidden")
def get_hidden_models() -> List[Dict[str, Any]]:
    return registry_loader.get_models_in_group("hidden_alias_or_unsupported")


@app.get("/models/{model_id}", response_model=ModelDetailResponse)
def get_model(model_id: str) -> ModelDetailResponse:
    entry = registry_loader.get_model_entry(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model_id}")
    return ModelDetailResponse(
        model_id=model_id,
        entry=entry,
        model_card=registry_loader.get_model_card(model_id),
    )


@app.get("/models/{model_id}/policy", response_model=ModelPolicyResponse)
def get_model_policy(model_id: str) -> ModelPolicyResponse:
    if registry_loader.get_model_entry(model_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model_id}")
    return ModelPolicyResponse(
        model_id=model_id,
        thresholds=registry_loader.get_thresholds(model_id),
        policy_report=registry_loader.get_policy_report(model_id),
    )


@app.get("/models/{model_id}/metrics", response_model=ModelMetricsResponse)
def get_model_metrics(model_id: str) -> ModelMetricsResponse:
    if registry_loader.get_model_entry(model_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown model: {model_id}")
    return ModelMetricsResponse(
        model_id=model_id,
        session_metrics=registry_loader.get_session_metrics(model_id),
        calibration_info=registry_loader.get_calibration_info(model_id),
    )


# ------------------------------------------------------------------- comparison

@app.get("/comparison/summary")
def comparison_summary() -> List[Dict[str, Any]]:
    try:
        return load_comparison_rows()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# --------------------------------------------------------------------------- firewall


# ---------------------------------------------------------------- runtime models

def _get_default_engine_and_demo_csv():
    """Return (RuntimeModelEngine, load_fn) for the executable firewall model."""
    engine = get_engine(EXECUTABLE_FIREWALL_MODEL_ID)
    load_csv = load_demo_flows_unified
    return engine, load_csv

@app.get("/firewall/runtime-models")
def get_runtime_models() -> List[Dict[str, Any]]:
    """Return all models in the runtime inference allowlist with metadata."""
    try:
        alist = registry_loader.load_inference_allowlist()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    allowlist_models = alist.get("allowlist", {})
    if isinstance(allowlist_models, list):
        # Legacy list format — wrap as dict
        allowlist_models = {mid: {} for mid in allowlist_models}
    allowed_ids: List[str] = list(allowlist_models.keys())
    default_id: str = alist.get("default_firewall", EXECUTABLE_FIREWALL_MODEL_ID)
    result = []
    for mid in allowed_ids:
        entry = registry_loader.get_model_entry(mid) or {}
        model_info = allowlist_models.get(mid, {})
        model_dir = registry_loader.RUNTIME_MODELS_DIR / mid
        # Feature info.
        feature_order: List[str] = []
        try:
            fo = registry_loader._read_json(model_dir / "feature_order.json")  # type: ignore[attr-defined]
            if fo:
                feature_order = fo.get("feature_order", [])
        except Exception:
            pass
        # Threshold info — supports both nested (robust9) and flat (full_canonical) formats.
        strict_threshold = balanced_threshold = None
        try:
            th = registry_loader._read_json(model_dir / "thresholds.json")  # type: ignore[attr-defined]
            if th:
                strict_threshold = th.get("strict", {}).get("threshold")
                balanced_threshold = th.get("balanced", {}).get("threshold")
                if strict_threshold is None:
                    strict_threshold = th.get("block_threshold")
                if balanced_threshold is None:
                    balanced_threshold = th.get("review_threshold")
        except Exception:
            pass
        # Loader config.
        prob_col = agg = None
        try:
            lc = registry_loader._read_json(model_dir / "runtime_loader_config.json")  # type: ignore[attr-defined]
            if lc:
                prob_col = lc.get("probability_column")
                agg = lc.get("session_aggregation")
        except Exception:
            pass

        is_exec = model_info.get("executable", mid == EXECUTABLE_FIREWALL_MODEL_ID)
        result.append(
            {
                "model_id": mid,
                "executable": is_exec,
                "comparison_only": model_info.get("comparison_only", not is_exec),
                "status": entry.get("status", "policy_computed"),
                "ui_badge": entry.get("ui_badge", ""),
                "ui_warning": entry.get("ui_warning", ""),
                "feature_order": feature_order,
                "feature_count": len(feature_order),
                "selected_probability_column": prob_col or entry.get("selected_probability_column"),
                "selected_aggregation": agg or entry.get("selected_aggregation"),
                "strict_threshold": strict_threshold,
                "balanced_threshold": balanced_threshold,
                "default_firewall": mid == default_id,
            }
        )
    return result


@app.get("/firewall/runtime-required-features")
def get_runtime_required_features() -> Dict[str, Any]:
    """Return required features per model and the union set."""
    allowed_ids = registry_loader.get_allowlisted_model_ids()
    per_model: Dict[str, List[str]] = {}
    union: set = set()
    for mid in allowed_ids:
        model_dir = registry_loader.RUNTIME_MODELS_DIR / mid
        fo_path = model_dir / "feature_order.json"
        feats: List[str] = []
        try:
            fo = registry_loader._read_json(fo_path)  # type: ignore[attr-defined]
            if fo:
                feats = fo.get("feature_order", [])
        except Exception:
            pass
        per_model[mid] = feats
        union.update(feats)

    return {
        "per_model_required_features": per_model,
        "union_required_features": sorted(union),
        "union_feature_count": len(union),
        "optional_columns": ["session_id", "flow_id", "dataset", "label"],
        "note": (
            "A CSV that includes all union_required_features can be evaluated "
            "against every allowlisted model. Missing features per model cause "
            "that model to be skipped, not the entire request."
        ),
    }


@app.get("/firewall/multimodel-demo")
def firewall_multimodel_demo() -> Dict[str, Any]:
    """Run the executable firewall model against the bundled demo CSV.
    Comparison models are listed with metadata but no inference is performed on them.
    """
    try:
        df = load_demo_flows_unified()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    allowed_ids = registry_loader.get_allowlisted_model_ids()
    per_model_results: List[Dict[str, Any]] = []
    for mid in allowed_ids:
        if mid != EXECUTABLE_FIREWALL_MODEL_ID:
            # Comparison-only: return metadata without running inference.
            entry = registry_loader.get_model_entry(mid) or {}
            per_model_results.append({
                "model_id": mid,
                "executable": False,
                "comparison_only": True,
                "skipped": True,
                "missing_features": [],
                "warnings": [
                    f"Comparison-only model — inference restricted to '{EXECUTABLE_FIREWALL_MODEL_ID}' only.",
                    "See /comparison/summary for cross-model benchmark metrics.",
                ],
                "counts": {"PASS": 0, "FLAG_REVIEW": 0, "BLOCK": 0},
                "sessions": [],
                "total_flows": 0,
                "total_sessions": 0,
                "action_mode": "report_only",
                "production_readiness": False,
                "status": entry.get("status", "comparison_only"),
                "ui_badge": entry.get("ui_badge", ""),
                "ui_warning": entry.get("ui_warning", ""),
            })
            continue
        try:
            engine = get_engine(mid)
            res = engine.run(df)
        except Exception as exc:  # noqa: BLE001
            logger.exception("multimodel-demo: inference failed for %s", mid)
            res = {
                "model_id": mid,
                "skipped": True,
                "missing_features": [],
                "warnings": [f"Runtime error: {exc}"],
                "counts": {"PASS": 0, "FLAG_REVIEW": 0, "BLOCK": 0},
                "sessions": [],
                "total_flows": 0,
                "total_sessions": 0,
                "action_mode": "simulation",
                "production_readiness": False,
            }
        per_model_results.append(res)

    total_sessions = (
        int(df["capture_id"].nunique())
        if "capture_id" in df.columns
        else int(df["session_id"].nunique())
        if "session_id" in df.columns
        else int(len(df))
    )

    return {
        "input_summary": {
            "total_flows": int(len(df)),
            "total_sessions": total_sessions,
            "source": "unified_model_demo_flows.csv",
        },
        "executable_model": EXECUTABLE_FIREWALL_MODEL_ID,
        "selected_models": allowed_ids,
        "action_mode": "simulation",
        "production_readiness": False,
        "model_results": per_model_results,
        "warnings": [
            "Simulation only — no real packets are blocked.",
            f"Only '{EXECUTABLE_FIREWALL_MODEL_ID}' runs inference. All other models are comparison/documentation only.",
            "See /comparison/summary for cross-model benchmark metrics.",
        ],
    }


@app.post("/firewall/analyze-csv-multimodel")
async def firewall_analyze_csv_multimodel(
    file: UploadFile = File(...),
    selected_model_ids: Optional[str] = None,
) -> Dict[str, Any]:
    """Run inference on an uploaded CSV using only the executable firewall model.

    selected_model_ids: optional comma-separated list.  Only
    EXECUTABLE_FIREWALL_MODEL_ID is permitted; any other model_id returns 400.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        df = parse_multimodel_csv(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if selected_model_ids:
        requested = [s.strip() for s in selected_model_ids.split(",") if s.strip()]
        non_executable = [mid for mid in requested if mid != EXECUTABLE_FIREWALL_MODEL_ID]
        if non_executable:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"The following model IDs are comparison-only and cannot run inference: "
                    + ", ".join(non_executable)
                    + f". Only '{EXECUTABLE_FIREWALL_MODEL_ID}' is executable in this prototype."
                ),
            )

    # Always use only the executable model.
    target_ids = [EXECUTABLE_FIREWALL_MODEL_ID]

    per_model_results: List[Dict[str, Any]] = []
    for mid in target_ids:
        try:
            engine = get_engine(mid)
            res = engine.run(df)
        except Exception as exc:  # noqa: BLE001
            logger.exception("analyze-csv-multimodel: inference failed for %s", mid)
            res = {
                "model_id": mid,
                "skipped": True,
                "missing_features": [],
                "warnings": [f"Runtime error: {exc}"],
                "counts": {"PASS": 0, "FLAG_REVIEW": 0, "BLOCK": 0},
                "sessions": [],
                "total_flows": 0,
                "total_sessions": 0,
                "action_mode": "simulation",
                "production_readiness": False,
            }
        per_model_results.append(res)

    total_sessions = (
        int(df["session_id"].nunique())
        if "session_id" in df.columns
        else int(len(df))
    )

    return {
        "input_summary": {
            "total_flows": int(len(df)),
            "total_sessions": total_sessions,
            "filename": file.filename or "uploaded.csv",
        },
        "executable_model": EXECUTABLE_FIREWALL_MODEL_ID,
        "selected_models": target_ids,
        "action_mode": "simulation",
        "production_readiness": False,
        "model_results": per_model_results,
        "warnings": [
            "Simulation only — no real packets are blocked.",
            f"Only '{EXECUTABLE_FIREWALL_MODEL_ID}' is executable. Comparison models are read-only via /comparison/summary.",
        ],
    }


@app.get("/firewall/demo", response_model=FirewallResult)
def firewall_demo() -> FirewallResult:
    """Run the default/recommended firewall model against the bundled demo CSV."""
    try:
        engine, load_csv = _get_default_engine_and_demo_csv()
        df = load_csv()
        result = engine.run(df)
    except Exception as exc:  # noqa: BLE001
        logger.exception("firewall/demo failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FirewallResult(**result)


@app.post("/firewall/analyze-csv", response_model=FirewallResult)
async def firewall_analyze_csv(file: UploadFile = File(...)) -> FirewallResult:
    """Analyze an uploaded CSV using the default/recommended firewall model."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        df = parse_uploaded_csv(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        engine, _ = _get_default_engine_and_demo_csv()
        result = engine.run(df)
    except Exception as exc:  # noqa: BLE001
        logger.exception("firewall/analyze-csv failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FirewallResult(**result)


@app.get("/firewall/required-features")
def firewall_required_features() -> Dict[str, Any]:
    try:
        engine = get_engine(EXECUTABLE_FIREWALL_MODEL_ID)
        return {"model_id": EXECUTABLE_FIREWALL_MODEL_ID, "required_features": engine.feature_order}
    except Exception as exc:
        logger.warning("Could not load engine for required-features: %s", exc)
        return {"model_id": EXECUTABLE_FIREWALL_MODEL_ID, "required_features": []}


# ======================================================================= live replay

@app.post("/firewall/live-replay/upload")
async def live_replay_upload(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Upload a flow-feature CSV to use as the live-replay source."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        return get_replay_state().load_csv(raw, file.filename or "uploaded.csv")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/firewall/live-replay/step")
def live_replay_step(
    batch_size: int = Query(default=5, ge=1, le=500),
) -> Dict[str, Any]:
    """Advance the replay by batch_size rows and return updated state."""
    try:
        return get_replay_state().step(batch_size=batch_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("live-replay/step failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/firewall/live-replay/reset")
def live_replay_reset() -> Dict[str, Any]:
    """Clear all replay state and uploaded CSV."""
    get_replay_state().reset()
    return {
        "loaded": False,
        "running": False,
        "finished": False,
        "message": "Replay state cleared.",
        "action_mode": "simulation",
    }


@app.get("/firewall/live-replay/state")
def live_replay_state() -> Dict[str, Any]:
    """Return current replay state without advancing the pointer."""
    return get_replay_state().get_state()


@app.get("/firewall/live-replay/template", response_class=PlainTextResponse)
def live_replay_template() -> str:
    """Return a CSV header template for a compatible replay upload."""
    return TEMPLATE_HEADER + "\n"


# ======================================================================= live ingest (PCAP streamer)

@app.post("/firewall/live-ingest")
def firewall_live_ingest(payload: LiveIngestRequest) -> Dict[str, Any]:
    """Accept a batch of unified_relative_shape_v2 flow features from tools/pcap_to_live_stream.py.

    Each call ingests one batch of flows extracted from a PCAP file captured
    inside the Ubuntu Server VM.  The endpoint runs unified_relative_shape_v2__lgbm
    inference on every accumulated flow and returns up-to-date session labels so the
    frontend Live VM Monitor can display near-real-time results.

    SAFETY: No packet capture is performed here.  All decisions are
    simulation-only.  No firewall rules are modified.
    """
    try:
        result = get_ingest_state().ingest_batch(
            source=payload.source,
            batch_id=payload.batch_id,
            flows=payload.flows,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("live-ingest failed for batch_id=%s", payload.batch_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return result


@app.post("/firewall/live-ingest/reset")
def firewall_live_ingest_reset() -> Dict[str, Any]:
    """Clear all accumulated live-ingest state."""
    get_ingest_state().reset()
    return {
        "message": "Live ingest state cleared.",
        "total_batches": 0,
        "total_flows": 0,
        "action_mode": "simulation",
    }


@app.get("/firewall/live-ingest/state")
def firewall_live_ingest_state() -> Dict[str, Any]:
    """Return the current live-ingest session state without modifying it."""
    return get_ingest_state().get_state()


# ======================================================================= benchmark

@app.get("/benchmark/compatible-csv/info")
def benchmark_compatible_info() -> Dict[str, Any]:
    """Return metadata about the compatible benchmark and model list."""
    return {
        "benchmark_only": True,
        "benchmark_csv": "unified_model_demo_flows.csv",
        "benchmark_csv_description": "Unified feature contract v2 demo flows — 588 flows, unified_relative_shape_v2 features",
        "compatible_models": COMPATIBLE_BENCHMARK_MODEL_IDS,
        "incompatible_models": INCOMPATIBLE_MODEL_IDS,
        "incompatible_reason": (
            "balanced_bagging_xgb_baseline and robust13_comparison require "
            "session-derived probability features not present in the raw-feature benchmark CSV."
        ),
        "firewall_model": EXECUTABLE_FIREWALL_MODEL_ID,
        "executable_firewall_model_only": True,
        "legacy_models_note": (
            "full_canonical__lgbm, robust9_firewall, balanced_bagging_* are legacy comparison models. "
            "They are not executable. Use /comparison/summary for cross-model metrics."
        ),
        "note": (
            "Benchmark comparison is read-only / benchmark-only. "
            "Results do not affect firewall decisions."
        ),
    }


@app.get("/benchmark/compatible-csv/bundled")
def benchmark_bundled() -> Dict[str, Any]:
    """Run the bundled unified demo CSV against the unified executable model.

    Uses demo_data/unified_model_demo_flows.csv (588 flows, unified_relative_shape_v2 features).
    Results are benchmark-only and do not affect firewall decisions.
    """
    try:
        df = load_demo_flows_unified()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        result = run_benchmark(df)
    except Exception as exc:  # noqa: BLE001
        logger.exception("benchmark/bundled failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    result["source"] = "bundled:unified_model_demo_flows.csv"
    return result


@app.post("/benchmark/compatible-csv")
async def benchmark_upload_csv(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Run an uploaded benchmark CSV against the 4 compatible models.

    The uploaded CSV must contain the required features for each model.
    Extra columns (session_id, flow_id, dataset, label, source_file) are
    silently passed through. Missing features for a specific model cause only
    that model to be skipped — the rest still run.

    Compatible models:
      - full_canonical__lgbm
      - robust9_firewall
      - balanced_bagging_3ds_reference
      - balanced_bagging_baseline

    NOT compatible (excluded automatically):
      - balanced_bagging_xgb_baseline
      - robust13_comparison

    Results are benchmark-only and do not affect firewall decisions.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        df = parse_multimodel_csv(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = run_benchmark(df)
    except Exception as exc:  # noqa: BLE001
        logger.exception("benchmark/compatible-csv upload failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    result["source"] = f"uploaded:{file.filename or 'uploaded.csv'}"
    return result


# ======================================================================= legacy benchmark comparison

@app.get("/benchmark/legacy/models")
def legacy_benchmark_models() -> Dict[str, Any]:
    """Return metadata for all legacy benchmark models (compatible + incompatible).

    These are comparison-only models. The active runtime firewall model
    (unified_relative_shape_v2__lgbm) is NOT included here.
    """
    try:
        return get_legacy_benchmark_model_info()
    except Exception as exc:
        logger.exception("legacy benchmark models info failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/benchmark/legacy/bundled")
def legacy_benchmark_bundled(
    selected_model_ids: Optional[str] = None,
) -> Dict[str, Any]:
    """Run selected compatible legacy models against the bundled benchmark CSV.

    selected_model_ids: optional comma-separated list of model IDs to run.
                        Only the 4 raw-feature compatible models are allowed.
    Uses demo_data/simultaneous_test_selected_models.csv when available,
    falling back to demo_multimodel_flows.csv.
    Results are benchmark-only and do NOT affect firewall decisions.
    unified_relative_shape_v2__lgbm is NOT run here.
    """
    # Try simultaneous_test first, fall back to multimodel demo
    try:
        df = load_benchmark_csv()
    except FileNotFoundError:
        try:
            df = load_multimodel_demo_flows()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    selected: Optional[List[str]] = None
    if selected_model_ids:
        selected = [s.strip() for s in selected_model_ids.split(",") if s.strip()]
        if EXECUTABLE_FIREWALL_MODEL_ID in selected:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"'{EXECUTABLE_FIREWALL_MODEL_ID}' is the active runtime firewall model "
                    "and must not be run on the legacy benchmark page. "
                    "Use Live VM for runtime inference."
                ),
            )

    try:
        result = run_legacy_benchmark(df, selected_ids=selected)
    except Exception as exc:
        logger.exception("legacy benchmark bundled failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    result["source"] = "bundled:simultaneous_test_selected_models.csv"
    return result


@app.post("/benchmark/compare")
async def benchmark_compare(
    file: UploadFile = File(...),
    selected_model_ids: Optional[str] = None,
) -> Dict[str, Any]:
    """Run selected compatible legacy models against an uploaded CSV.

    Allowlisted models only:
      - full_canonical__lgbm
      - robust9_firewall
      - balanced_bagging_3ds_reference
      - balanced_bagging_baseline

    unified_relative_shape_v2__lgbm is NEVER run here.
    Results are benchmark-only and do NOT affect firewall decisions.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        df = parse_multimodel_csv(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    selected: Optional[List[str]] = None
    if selected_model_ids:
        selected = [s.strip() for s in selected_model_ids.split(",") if s.strip()]
        if EXECUTABLE_FIREWALL_MODEL_ID in selected:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"'{EXECUTABLE_FIREWALL_MODEL_ID}' is the active runtime firewall model "
                    "and must not be run on the legacy benchmark page. "
                    "Use Live VM for runtime inference."
                ),
            )
        # Reject any non-allowlisted model IDs
        disallowed = [mid for mid in selected if mid not in LEGACY_BENCHMARK_MODEL_IDS]
        if disallowed:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"The following model IDs are not allowed on the benchmark comparison page: "
                    + ", ".join(disallowed)
                    + f". Allowed: {LEGACY_BENCHMARK_MODEL_IDS}"
                ),
            )

    try:
        result = run_legacy_benchmark(df, selected_ids=selected)
    except Exception as exc:
        logger.exception("benchmark/compare upload failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    result["source"] = f"uploaded:{file.filename or 'uploaded.csv'}"
    return result


# ===========================================================================
# /model-details/* — serve the frontend_model_details metadata package
# ===========================================================================

_FMD_DIR = (
    Path(__file__).resolve().parent
    / "runtime_bundle"
    / "app_runtime_bundle"
    / "frontend_model_details"
)


def _load_fmd_json(filename: str) -> Any:
    p = _FMD_DIR / filename
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Metadata file not found: {filename}")
    return json.loads(p.read_text(encoding="utf-8"))


@app.get("/model-details/frontend-content", tags=["model-details"])
def model_details_frontend_content() -> Any:
    """Returns frontend_page_content.json — per-page display content and metric chips."""
    return _load_fmd_json("frontend_page_content.json")


@app.get("/model-details/cards", tags=["model-details"])
def model_details_cards() -> Any:
    """Returns model_cards_frontend.json — rich model cards with metrics, caveats, and why_selected."""
    return _load_fmd_json("model_cards_frontend.json")


@app.get("/model-details/features", tags=["model-details"])
def model_details_features() -> Any:
    """Returns model_feature_details.json — per-feature formulas for all models."""
    return _load_fmd_json("model_feature_details.json")


@app.get("/model-details/metrics", tags=["model-details"])
def model_details_metrics() -> Any:
    """Returns model_metrics_summary.json — summary metrics for all evaluated models."""
    return _load_fmd_json("model_metrics_summary.json")


@app.get("/model-details/benchmark-compatibility", tags=["model-details"])
def model_details_benchmark_compatibility() -> Any:
    """Returns benchmark_compatibility.json — per-model CSV schema compatibility rules."""
    return _load_fmd_json("benchmark_compatibility.json")


@app.get("/model-details/missing-report", response_class=PlainTextResponse, tags=["model-details"])
def model_details_missing_report() -> str:
    """Returns missing_frontend_details.md as plain text."""
    p = _FMD_DIR / "missing_frontend_details.md"
    if not p.exists():
        raise HTTPException(status_code=404, detail="missing_frontend_details.md not found")
    return p.read_text(encoding="utf-8")














