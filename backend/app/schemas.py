"""Pydantic response schemas for the AI VPN Firewall Prototype API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    service: str


class SessionDecision(BaseModel):
    session_id: str
    n_flows: int
    flow_score_mean: float
    flow_score_max: float
    session_score: float
    aggregation: str
    strict_trigger: bool
    balanced_trigger: bool
    action: str = Field(..., description="PASS | FLAG_REVIEW | BLOCK (simulation)")
    simulated: bool = True


class FirewallResult(BaseModel):
    model_id: str
    action_mode: str = "simulation"
    production_readiness: bool = False
    probability_column: str
    aggregation: str
    thresholds: Dict[str, float]
    total_flows: int
    total_sessions: int
    counts: Dict[str, int]
    sessions: List[SessionDecision]
    warnings: List[str] = []


class ModelRegistryEntry(BaseModel):
    model_id: str
    entry: Dict[str, Any]


class ModelDetailResponse(BaseModel):
    model_id: str
    entry: Dict[str, Any]
    model_card: Optional[Dict[str, Any]] = None


class ModelPolicyResponse(BaseModel):
    model_id: str
    thresholds: Optional[Dict[str, Any]] = None
    policy_report: Optional[Dict[str, Any]] = None


class ModelMetricsResponse(BaseModel):
    model_id: str
    session_metrics: Optional[Dict[str, Any]] = None
    calibration_info: Optional[Dict[str, Any]] = None


class LiveIngestRequest(BaseModel):
    """Payload for POST /firewall/live-ingest (sent by tools/pcap_to_live_stream.py)."""
    source: str = Field(default="vm-pcap", description="Source label, e.g. 'vm-pcap'.")
    batch_id: str = Field(..., description="Unique batch identifier, e.g. 'pcap_batch_0001'.")
    feature_schema: Optional[str] = Field(
        default=None,
        description="Feature schema used to generate this batch, e.g. 'full_canonical_34'.",
    )
    flows: List[Dict[str, Any]] = Field(
        ...,
        description="List of full_canonical_34-compatible flow feature dicts (34 features).",
    )


