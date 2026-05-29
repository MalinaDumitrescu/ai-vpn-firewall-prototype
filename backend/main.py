"""FastAPI entrypoint for the AI VPN Firewall Prototype."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from app import registry_loader
from app.csv_service import (
    load_comparison_rows,
    load_demo_flows,
    load_demo_flows_full_canonical,
    load_multimodel_demo_flows,
    parse_multimodel_csv,
    parse_uploaded_csv,
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
    version="0.1.0",
    description=(
        "Read-only access to the standalone runtime bundle. "
        "Default inference model: full_canonical__lgbm (single LightGBM, 34 features). "
        "Legacy baseline: robust9_firewall (XGB+LGBM+CatBoost ensemble, 9 features). "
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
    # Prefer allowlist's declared default_firewall; fall back to registry status.
    default_id = registry_loader.get_default_firewall_model_id()
    if not default_id:
        defaults = registry_loader.find_default_models()
        if len(defaults) == 0:
            raise HTTPException(status_code=500, detail="No default firewall model found.")
        if len(defaults) > 1:
            raise HTTPException(
                status_code=500,
                detail=f"Multiple default firewall models found: {list(defaults.keys())}",
            )
        default_id = next(iter(defaults))
    entry = registry_loader.get_model_entry(default_id)
    if entry is None:
        raise HTTPException(status_code=500, detail=f"Default model '{default_id}' not found in registry.")
    return {"model_id": default_id, **entry}


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

# Legacy single-model guard — kept for reference; default model is now full_canonical__lgbm.
# The live ingest and live replay services continue to use robust9_firewall since they
# consume 9-feature PCAP-derived flow batches that match the robust9 feature schema.


# ---------------------------------------------------------------- runtime models

def _get_default_engine_and_demo_csv():
    """Return (RuntimeModelEngine, load_fn) for the allowlist default firewall model."""
    default_id = registry_loader.get_default_firewall_model_id() or "full_canonical__lgbm"
    engine = get_engine(default_id)
    # Use the full_canonical demo CSV for full_canonical__lgbm; fall back to legacy CSV.
    if default_id == "full_canonical__lgbm":
        load_csv = load_demo_flows_full_canonical
    else:
        load_csv = load_demo_flows
    return engine, load_csv

@app.get("/firewall/runtime-models")
def get_runtime_models() -> List[Dict[str, Any]]:
    """Return all models in the runtime inference allowlist with metadata."""
    try:
        alist = registry_loader.load_inference_allowlist()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    allowed_ids: List[str] = alist.get("allowlist", [])
    default_id: str = alist.get("default_firewall", "full_canonical__lgbm")
    result = []
    for mid in allowed_ids:
        entry = registry_loader.get_model_entry(mid) or {}
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
                # Nested format: {"strict": {"threshold": ...}, "balanced": {"threshold": ...}}
                strict_threshold = th.get("strict", {}).get("threshold")
                balanced_threshold = th.get("balanced", {}).get("threshold")
                # Flat format fallback: {"block_threshold": ..., "review_threshold": ...}
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

        result.append(
            {
                "model_id": mid,
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
                "comparison_only": mid != default_id,
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
    """Run all allowlisted models against the bundled multimodel demo CSV."""
    try:
        df = load_multimodel_demo_flows()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    allowed_ids = registry_loader.get_allowlisted_model_ids()
    per_model_results: List[Dict[str, Any]] = []
    for mid in allowed_ids:
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

    # Determine sessions from session_id col if present.
    total_sessions = (
        int(df["session_id"].nunique())
        if "session_id" in df.columns
        else int(len(df))
    )

    return {
        "input_summary": {
            "total_flows": int(len(df)),
            "total_sessions": total_sessions,
            "source": "demo_multimodel_flows.csv",
        },
        "selected_models": allowed_ids,
        "action_mode": "simulation",
        "production_readiness": False,
        "model_results": per_model_results,
        "warnings": [
            "Simulation only — no real packets are blocked.",
            "All comparison model results are for benchmarking only.",
            "full_canonical__lgbm is the recommended firewall model (simulation mode). robust9_firewall is the legacy baseline.",
        ],
    }


@app.post("/firewall/analyze-csv-multimodel")
async def firewall_analyze_csv_multimodel(
    file: UploadFile = File(...),
    selected_model_ids: Optional[str] = None,
) -> Dict[str, Any]:
    """Run multi-model inference on an uploaded CSV.

    selected_model_ids: optional comma-separated list of model IDs.
    If omitted, all allowlist models are used.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        df = parse_multimodel_csv(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    allowed_ids = registry_loader.get_allowlisted_model_ids()

    if selected_model_ids:
        requested = [s.strip() for s in selected_model_ids.split(",") if s.strip()]
        # Validate each requested model is in allowlist.
        invalid = [mid for mid in requested if mid not in allowed_ids]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=(
                    "The following model IDs are not in the runtime inference allowlist: "
                    + ", ".join(invalid)
                ),
            )
        target_ids = requested
    else:
        target_ids = allowed_ids

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
        "selected_models": target_ids,
        "action_mode": "simulation",
        "production_readiness": False,
        "model_results": per_model_results,
        "warnings": [
            "Simulation only — no real packets are blocked.",
            "All comparison model results are for benchmarking only.",
            "full_canonical__lgbm is the recommended firewall model (simulation mode). robust9_firewall is the legacy baseline.",
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
    default_id = registry_loader.get_default_firewall_model_id() or "full_canonical__lgbm"
    try:
        engine = get_engine(default_id)
        return {"model_id": default_id, "required_features": engine.feature_order}
    except Exception as exc:
        logger.warning("Could not load engine for required-features: %s", exc)
        return {"model_id": default_id, "required_features": []}


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
    """Accept a batch of robust9 flow features from tools/pcap_to_live_stream.py.

    Each call ingests one batch of flows extracted from a PCAP file captured
    inside the Ubuntu Server VM.  The endpoint runs robust9_firewall inference
    on every accumulated flow and returns up-to-date session labels so the
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













