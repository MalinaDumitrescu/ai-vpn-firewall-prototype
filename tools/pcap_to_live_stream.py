"""
pcap_to_live_stream.py
======================
PCAP → unified_relative_shape_v2 feature extractor → FastAPI live-ingest streamer.

Reads an existing .pcap file captured inside the Ubuntu Server VM,
extracts the 12 unified_relative_shape_v2 features required by
unified_relative_shape_v2__lgbm (default), and streams them in batches to:
  POST /firewall/live-ingest

Default feature schema: unified_relative_shape_v2__lgbm (12 features)
Legacy schema: full_canonical__lgbm (34 features, use --model-id full_canonical__lgbm)

Packet size: IP total length (ip_layer.len — NOT Ethernet frame length)
IAT:         consecutive inter-arrival times in seconds
Direction:   1=upload/client-to-server, 0=download/server-to-client

────────────────────────────────────────────────────────────────────
SAFETY CONSTRAINTS (enforced in this script):
  - Does NOT capture live traffic.
  - Does NOT call tcpdump, subprocess, or any shell command.
  - Does NOT modify iptables, nftables, Windows Firewall, or routing tables.
  - Does NOT require the FastAPI server to sniff packets.
  - Reads EXISTING .pcap files only.
  - All backend decisions are simulation-only.
────────────────────────────────────────────────────────────────────

Recommended workflow:
  1. Inside VM:    sudo tcpdump -i any -w /tmp/capture.pcap
  2. Copy to host: scp -P 2222 scoti@127.0.0.1:/tmp/capture.pcap captures/
  3. On host:      python tools/pcap_to_live_stream.py --pcap captures/capture.pcap

Install dependencies:
  pip install -r tools/requirements_tools.txt
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Windows-safe console output.
#
# Some Windows consoles (cmd.exe, older PowerShell) default to cp1252 / cp850
# and cannot encode characters like Unicode box-drawing glyphs, which causes
# UnicodeEncodeError mid-stream and aborts the script. We do two things:
#   1. Try to reconfigure stdout/stderr to UTF-8 (best-effort, Python 3.7+).
#   2. Provide a safe_print() fallback that swaps unencodable characters for
#      a safe ASCII replacement instead of crashing.
# ---------------------------------------------------------------------------
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001
    pass


def safe_print(text: str = "") -> None:
    """print() that never raises UnicodeEncodeError on Windows consoles."""
    try:
        print(text)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(enc, errors="replace").decode(enc, errors="replace"))

try:
    from scapy.all import rdpcap, IP, TCP, UDP  # type: ignore[import]
except ImportError:
    print(
        "\n[ERROR] Missing dependency: scapy.\n"
        "Install with:\n"
        "  pip install -r tools/requirements_tools.txt\n"
    )
    sys.exit(1)

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _requests = None
    _HAS_REQUESTS = False

#
# Default: unified_relative_shape_v2__lgbm (12 features, unified feature contract v2)
# Legacy:  full_canonical__lgbm            (34 features)
#
# All 12 unified features are a SUBSET of the 34 full_canonical features.
# _compute_full_canonical() already computes all intermediate values needed
# for both schemas.  We simply select the relevant columns afterwards.

DEFAULT_MODEL_ID = "unified_relative_shape_v2__lgbm"

UNIFIED_V2_FEATURES: List[str] = [
    "sz_cv",
    "sz_iqr",
    "sz_qratio",
    "sz_median_to_mean",
    "sz_p25_median_ratio",
    "sz_p75_median_ratio",
    "sz_iqr_norm_median",
    "iat_cv",
    "iat_iqr",
    "direction_balance_bytes",
    "direction_balance_packets",
    "dispersion_symmetry",
]

FULL_CANONICAL_FEATURES: List[str] = [
    "sz_coef_variation",
    "sz_p25_median_ratio",
    "sz_p75_median_ratio",
    "sz_iqr_norm_median",
    "dispersion_symmetry",
    "direction_balance_bytes",
    "direction_balance_packets",
    "sz_mean_max",
    "sz_mean_min",
    "sz_std_max",
    "sz_std_min",
    "iat_all_mean",
    "iat_all_std",
    "iat_all_p25",
    "iat_all_median",
    "iat_all_p75",
    "iat_mean_max",
    "iat_mean_min",
    "iat_std_max",
    "iat_std_min",
    "sz_all_mean",
    "sz_all_std",
    "sz_all_median",
    "sz_all_p25",
    "sz_all_p75",
    "sz_cv",
    "sz_iqr",
    "sz_qratio",
    "sz_median_to_mean",
    "iat_iqr",
    "iat_cv",
    "iat_median",
    "iat_p25",
    "iat_p75",
]

FEATURES_BY_MODEL: Dict[str, List[str]] = {
    "unified_relative_shape_v2__lgbm": UNIFIED_V2_FEATURES,
    "full_canonical__lgbm": FULL_CANONICAL_FEATURES,
}

FEATURE_SCHEMA_BY_MODEL: Dict[str, str] = {
    "unified_relative_shape_v2__lgbm": "unified_relative_shape_v2",
    "full_canonical__lgbm": "full_canonical_34",
}

META_COLUMNS = [
    "session_id",
    "flow_id",
    "timestamp",
    "src_ip",
    "dst_ip",
    "protocol",
    "dst_port",
    "scenario",
]


_EPS = 1e-6



def _normalize_flow_key(
    src_ip: str,
    dst_ip: str,
    protocol: str,
    src_port: Optional[int],
    dst_port: Optional[int],
) -> Tuple:
    """Return a canonical bidirectional flow key so A→B and B→A map to the same key."""
    if src_port is not None and dst_port is not None:
        ep_a = (src_ip, src_port)
        ep_b = (dst_ip, dst_port)
        if ep_a > ep_b:
            ep_a, ep_b = ep_b, ep_a
        return (ep_a[0], ep_b[0], protocol, ep_a[1], ep_b[1])
    else:
        a, b = sorted([src_ip, dst_ip])
        return (a, b, protocol, None, None)




def _mean(lst: List[float]) -> float:
    return sum(lst) / len(lst) if lst else 0.0


def _std_pop(lst: List[float]) -> float:
    """Population standard deviation (ddof=0)."""
    if not lst:
        return 0.0
    m = _mean(lst)
    return math.sqrt(sum((x - m) ** 2 for x in lst) / len(lst))


def _percentile(lst: List[float], p: float) -> float:
    """Linear interpolation percentile; p in [0, 100]."""
    if not lst:
        return 0.0
    s = sorted(lst)
    n = len(s)
    idx = p / 100.0 * (n - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return float(s[lo])
    return float(s[lo] + (s[hi] - s[lo]) * (idx - lo))


def _iats(times: List[float]) -> List[float]:
    """Compute inter-arrival times from a list of packet timestamps (seconds).

    Sorts timestamps before differencing. Returns [] for single-packet flows.
    """
    if len(times) < 2:
        return []
    s = sorted(times)
    return [s[i + 1] - s[i] for i in range(len(s) - 1)]




def _compute_full_canonical(
    sizes_a:   List[float],
    sizes_b:   List[float],
    all_sizes: List[float],
    times_a:   List[float],
    times_b:   List[float],
    all_times: List[float],
) -> Dict[str, float]:
    """Compute ALL intermediate and derived flow features (superset of both schemas).

    Returns a dict containing both:
      - 12 unified_relative_shape_v2 features (default schema)
      - 34 full_canonical features (legacy schema)

    Packet size:
        IP total length (ip_layer.len) — NOT Ethernet frame length.
        Matches unified feature_contract.json (packet_size_mode=ip_total_length_bytes).

    Direction A = first-seen source IP (direction=1/upload/client-to-server).
    Direction B = reverse (direction=0/download/server-to-client).
    direction_balance_bytes/packets: (A - B) / (A + B + eps)  ∈ [-1, 1].

    IAT: consecutive inter-arrival times in seconds (all packets combined
    and per-direction). Single-packet flows → all IAT stats = 0.

    Numeric stability: EPS = 1e-6 (matches feature_contract.json).
    """
    if not all_sizes:
        all_feat_names = list(dict.fromkeys(FULL_CANONICAL_FEATURES + UNIFIED_V2_FEATURES))
        return {k: 0.0 for k in all_feat_names}

    sz_all_mean   = _mean(all_sizes)
    sz_all_std    = _std_pop(all_sizes)
    sz_all_p25    = _percentile(all_sizes, 25.0)
    sz_all_median = _percentile(all_sizes, 50.0)
    sz_all_p75    = _percentile(all_sizes, 75.0)
    sz_iqr        = sz_all_p75 - sz_all_p25

    sz_cv             = sz_all_std / (sz_all_mean + _EPS)
    sz_coef_variation = sz_cv                                      # same global CoV
    sz_qratio         = sz_all_p75 / (sz_all_p25 + _EPS)
    sz_median_to_mean = sz_all_median / (sz_all_mean + _EPS)
    sz_p25_median_ratio = sz_all_p25 / (sz_all_median + _EPS)
    sz_p75_median_ratio = sz_all_p75 / (sz_all_median + _EPS)
    sz_iqr_norm_median  = sz_iqr     / (sz_all_median + _EPS)

    mean_a = _mean(sizes_a) if sizes_a else 0.0
    mean_b = _mean(sizes_b) if sizes_b else 0.0
    std_a  = _std_pop(sizes_a) if sizes_a else 0.0
    std_b  = _std_pop(sizes_b) if sizes_b else 0.0

    sz_mean_max = max(mean_a, mean_b)
    sz_mean_min = min(mean_a, mean_b)
    sz_std_max  = max(std_a, std_b)
    sz_std_min  = min(std_a, std_b)

    dispersion_symmetry = 1.0 - abs(std_a - std_b) / (std_a + std_b + _EPS)

    sum_a = sum(sizes_a) if sizes_a else 0.0
    sum_b = sum(sizes_b) if sizes_b else 0.0
    cnt_a = len(sizes_a)
    cnt_b = len(sizes_b)
    direction_balance_bytes   = (sum_a - sum_b) / (sum_a + sum_b + _EPS)
    direction_balance_packets = (cnt_a - cnt_b) / (cnt_a + cnt_b + _EPS)

    all_iats_list = _iats(all_times)

    iat_all_mean   = _mean(all_iats_list)    if all_iats_list else 0.0
    iat_all_std    = _std_pop(all_iats_list) if all_iats_list else 0.0
    iat_all_p25    = _percentile(all_iats_list, 25.0) if all_iats_list else 0.0
    iat_all_median = _percentile(all_iats_list, 50.0) if all_iats_list else 0.0
    iat_all_p75    = _percentile(all_iats_list, 75.0) if all_iats_list else 0.0
    iat_iqr        = iat_all_p75 - iat_all_p25
    iat_cv         = iat_all_std / (iat_all_mean + _EPS) if iat_all_mean > 0 else 0.0
    iat_median     = iat_all_median
    iat_p25        = iat_all_p25
    iat_p75        = iat_all_p75

    iats_a_list = _iats(times_a)
    iats_b_list = _iats(times_b)

    mean_iat_a = _mean(iats_a_list)    if iats_a_list else 0.0
    mean_iat_b = _mean(iats_b_list)    if iats_b_list else 0.0
    std_iat_a  = _std_pop(iats_a_list) if iats_a_list else 0.0
    std_iat_b  = _std_pop(iats_b_list) if iats_b_list else 0.0

    iat_mean_max = max(mean_iat_a, mean_iat_b)
    iat_mean_min = min(mean_iat_a, mean_iat_b)
    iat_std_max  = max(std_iat_a, std_iat_b)
    iat_std_min  = min(std_iat_a, std_iat_b)

    return {
        k: round(v, 6)
        for k, v in {
            "sz_cv":          sz_cv,
            "sz_iqr":         sz_iqr,
            "sz_qratio":      sz_qratio,
            "sz_median_to_mean": sz_median_to_mean,
            "sz_p25_median_ratio":  sz_p25_median_ratio,
            "sz_p75_median_ratio":  sz_p75_median_ratio,
            "sz_iqr_norm_median":   sz_iqr_norm_median,
            "iat_cv":         iat_cv,
            "iat_iqr":        iat_iqr,
            "direction_balance_bytes":   direction_balance_bytes,
            "direction_balance_packets": direction_balance_packets,
            "dispersion_symmetry":       dispersion_symmetry,
            "sz_coef_variation":        sz_cv,
            "sz_all_mean":    sz_all_mean,
            "sz_all_std":     sz_all_std,
            "sz_all_median":  sz_all_median,
            "sz_all_p25":     sz_all_p25,
            "sz_all_p75":     sz_all_p75,
            "sz_mean_max":    sz_mean_max,
            "sz_mean_min":    sz_mean_min,
            "sz_std_max":     sz_std_max,
            "sz_std_min":     sz_std_min,
            "iat_all_mean":   iat_all_mean,
            "iat_all_std":    iat_all_std,
            "iat_all_p25":    iat_all_p25,
            "iat_all_median": iat_all_median,
            "iat_all_p75":    iat_all_p75,
            "iat_mean_max":   iat_mean_max,
            "iat_mean_min":   iat_mean_min,
            "iat_std_max":    iat_std_max,
            "iat_std_min":    iat_std_min,
            "iat_median":     iat_median,
            "iat_p25":        iat_p25,
            "iat_p75":        iat_p75,
        }.items()
    }


def _select_features_for_model(
    all_features: Dict[str, float],
    model_id: str,
) -> Dict[str, float]:
    """Select only the features required by the given model_id."""
    feature_list = FEATURES_BY_MODEL.get(model_id, UNIFIED_V2_FEATURES)
    return {k: all_features[k] for k in feature_list if k in all_features}




def parse_pcap(
    pcap_path: str,
    scenario: str,
    min_packets_per_flow: int,
    max_packets: Optional[int],
    model_id: str = DEFAULT_MODEL_ID,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Parse a PCAP file and return (flow_rows, stats_dict).

    Each flow must have ≥ min_packets_per_flow packets to be included.
    Uses 5-second time windows for session_id assignment.

    Packet size = IP total length (ip_layer.len), NOT Ethernet frame length.
    Timestamps tracked per flow and per direction for IAT computation.

    model_id controls which feature schema is extracted:
      - unified_relative_shape_v2__lgbm (default): 12 unified features
      - full_canonical__lgbm (legacy): 34 full canonical features
    """
    print(f"[*] Reading PCAP: {pcap_path}")
    try:
        packets = rdpcap(pcap_path)
    except Exception as exc:
        print(f"[ERROR] Could not read PCAP file: {exc}")
        sys.exit(1)

    total_packets = len(packets)
    print(f"[*] Loaded {total_packets} packet(s) from PCAP.")

    usable_ip       = 0
    usable_tcp_udp  = 0
    skipped_non_ip  = 0
    pkt_count       = 0
    capture_start_time: Optional[float] = None

    flows: Dict[Tuple, Dict[str, Any]] = {}

    for pkt in packets:
        if max_packets is not None and pkt_count >= max_packets:
            break
        pkt_count += 1

        if not pkt.haslayer(IP):
            skipped_non_ip += 1
            continue

        usable_ip += 1
        ip_layer  = pkt[IP]
        src_ip    = str(ip_layer.src)
        dst_ip    = str(ip_layer.dst)
        proto_num = int(ip_layer.proto)
        # Use IP total length (NOT len(pkt) which includes Ethernet headers).
        # This matches the training feature extraction pipeline for full_canonical__lgbm.
        pkt_len   = float(ip_layer.len)
        ts        = float(pkt.time)

        if capture_start_time is None:
            capture_start_time = ts

        if pkt.haslayer(TCP):
            usable_tcp_udp += 1
            tcp      = pkt[TCP]
            src_port = int(tcp.sport)
            dst_port = int(tcp.dport)
            protocol = "TCP"
        elif pkt.haslayer(UDP):
            usable_tcp_udp += 1
            udp      = pkt[UDP]
            src_port = int(udp.sport)
            dst_port = int(udp.dport)
            protocol = "UDP"
        else:
            src_port = None
            dst_port = None
            protocol = str(proto_num)

        key = _normalize_flow_key(src_ip, dst_ip, protocol, src_port, dst_port)

        if key not in flows:
            flows[key] = {
                "first_ts":     ts,
                "first_src_ip": src_ip,
                "sizes_a":      [],
                "sizes_b":      [],
                "all_sizes":    [],
                "times_a":      [],
                "times_b":      [],
                "all_times":    [],
                "src_ip":       key[0],
                "dst_ip":       key[1],
                "protocol":     protocol,
                "dst_port":     key[4],
            }

        flow = flows[key]
        flow["all_sizes"].append(pkt_len)
        flow["all_times"].append(ts)

        if src_ip == flow["first_src_ip"]:
            flow["sizes_a"].append(pkt_len)
            flow["times_a"].append(ts)
        else:
            flow["sizes_b"].append(pkt_len)
            flow["times_b"].append(ts)

    if capture_start_time is None:
        capture_start_time = 0.0

    flow_rows: List[Dict[str, Any]] = []
    flows_skipped_short = 0

    for idx, (key, flow) in enumerate(flows.items()):
        if len(flow["all_sizes"]) < min_packets_per_flow:
            flows_skipped_short += 1
            continue

        first_ts     = flow["first_ts"]
        window_index = int(math.floor((first_ts - capture_start_time) / 5.0))
        session_id   = f"{scenario}__window_{window_index:04d}"
        flow_id      = f"flow_{idx:06d}"

        all_feats = _compute_full_canonical(
            sizes_a   = flow["sizes_a"],
            sizes_b   = flow["sizes_b"],
            all_sizes = flow["all_sizes"],
            times_a   = flow["times_a"],
            times_b   = flow["times_b"],
            all_times = flow["all_times"],
        )
        feats = _select_features_for_model(all_feats, model_id)

        row: Dict[str, Any] = {
            "session_id": session_id,
            "flow_id":    flow_id,
            "timestamp":  datetime.fromtimestamp(first_ts, tz=timezone.utc).isoformat(),
            "src_ip":     flow["src_ip"],
            "dst_ip":     flow["dst_ip"],
            "protocol":   flow["protocol"],
            "dst_port":   flow["dst_port"],
            "scenario":   scenario,
        }
        row.update(feats)
        flow_rows.append(row)

    stats: Dict[str, int] = {
        "total_packets":       total_packets,
        "packets_read":        pkt_count,
        "usable_ip":           usable_ip,
        "usable_tcp_udp":      usable_tcp_udp,
        "skipped_non_ip":      skipped_non_ip,
        "flows_extracted":     len(flow_rows),
        "flows_skipped_short": flows_skipped_short,
    }

    return flow_rows, stats




def validate_rows(
    flow_rows: List[Dict[str, Any]],
    model_id: str = DEFAULT_MODEL_ID,
) -> List[str]:
    """Validate that all required features for model_id are present and numeric.

    Returns a list of error strings (empty list = valid).
    """
    feature_list = FEATURES_BY_MODEL.get(model_id, UNIFIED_V2_FEATURES)
    errors: List[str] = []
    if not flow_rows:
        errors.append("No flow rows to validate.")
        return errors

    sample = flow_rows[0]
    missing = [f for f in feature_list if f not in sample]
    if missing:
        errors.append(
            f"Live PCAP features are not valid for {model_id}. "
            f"Missing features ({len(missing)}): {missing}"
        )

    nan_cols: Dict[str, int] = defaultdict(int)
    inf_cols: Dict[str, int] = defaultdict(int)
    for row in flow_rows:
        for feat in feature_list:
            v = row.get(feat)
            if v is None:
                nan_cols[feat] += 1
            elif isinstance(v, float):
                if math.isnan(v):
                    nan_cols[feat] += 1
                elif math.isinf(v):
                    inf_cols[feat] += 1

    if nan_cols:
        errors.append(f"NaN values in features: { {k: v for k, v in nan_cols.items()} }")
    if inf_cols:
        errors.append(f"Inf values in features: { {k: v for k, v in inf_cols.items()} }")

    return errors




def save_csv(
    flow_rows: List[Dict[str, Any]],
    out_csv: str,
    model_id: str = DEFAULT_MODEL_ID,
) -> None:
    """Save extracted feature rows to a CSV; creates parent dirs."""
    feature_list = FEATURES_BY_MODEL.get(model_id, UNIFIED_V2_FEATURES)
    schema_name  = FEATURE_SCHEMA_BY_MODEL.get(model_id, model_id)
    columns      = META_COLUMNS + feature_list
    p = Path(out_csv)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flow_rows)
    print(f"[*] Saved {len(flow_rows)} flow row(s) to: {p.resolve()}")
    print(f"[*] Schema: {schema_name} ({len(feature_list)} model features + {len(META_COLUMNS)} metadata columns)")




def stream_to_api(
    flow_rows: List[Dict[str, Any]],
    api_base: str,
    batch_size: int,
    delay_seconds: float,
    source: str,
    model_id: str = DEFAULT_MODEL_ID,
) -> Tuple[int, int]:
    """
    POST flow_rows in batches to /firewall/live-ingest.

    Returns (batches_sent, flows_sent).
    Handles Ctrl+C gracefully.
    Prints a clear error and exits if the backend is unreachable.
    """
    if not _HAS_REQUESTS or _requests is None:
        print(
            "\n[ERROR] Missing dependency: requests.\n"
            "Install with:\n"
            "  pip install -r tools/requirements_tools.txt\n"
        )
        sys.exit(1)

    feature_list = FEATURES_BY_MODEL.get(model_id, UNIFIED_V2_FEATURES)
    schema_name  = FEATURE_SCHEMA_BY_MODEL.get(model_id, model_id)
    url           = f"{api_base.rstrip('/')}/firewall/live-ingest"
    total_batches = math.ceil(len(flow_rows) / batch_size)
    batches_sent  = 0
    flows_sent    = 0

    print(f"\n[*] Streaming {len(flow_rows)} flow(s) across {total_batches} batch(es)")
    print(f"    Endpoint      : {url}")
    print(f"    batch_size    : {batch_size}   delay: {delay_seconds}s")
    print(f"    Model         : {model_id}")
    print(f"    Feature schema: {schema_name} ({len(feature_list)} features)\n")

    try:
        for batch_num in range(total_batches):
            start = batch_num * batch_size
            end   = min(start + batch_size, len(flow_rows))
            batch = flow_rows[start:end]

            batch_id = f"pcap_batch_{batch_num + 1:04d}"
            payload  = {
                "source":         source,
                "batch_id":       batch_id,
                "feature_schema": schema_name,
                "model_id":       model_id,
                "flows":          batch,
            }

            try:
                resp = _requests.post(url, json=payload, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except _requests.exceptions.ConnectionError:
                print(
                    f"\n[ERROR] Cannot connect to FastAPI at {api_base}\n"
                    "Make sure the backend is running:\n"
                    "  cd backend\n"
                    "  python -m uvicorn main:app --host 127.0.0.1 --port 8765\n"
                )
                sys.exit(1)
            except _requests.exceptions.HTTPError as exc:
                print(f"[ERROR] HTTP {exc.response.status_code} from API: {exc}")
                sys.exit(1)
            except Exception as exc:  # noqa: BLE001
                print(f"[ERROR] Unexpected error posting batch: {exc}")
                sys.exit(1)

            batches_sent += 1
            flows_sent   += len(batch)

            resp_batches  = data.get("total_batches", "?")
            resp_flows    = data.get("total_flows", "?")
            resp_labelled = data.get("labelled_counts", {})
            resp_model    = data.get("model_id", "?")

            print(
                f"  [{batch_id}] sent {len(batch):>3} flow(s) | "
                f"model={resp_model} "
                f"server total_batches={resp_batches} "
                f"total_flows={resp_flows} "
                f"labelled={resp_labelled}"
            )

            if batch_num < total_batches - 1:
                time.sleep(delay_seconds)

    except KeyboardInterrupt:
        print(
            f"\n[!] Streaming interrupted (Ctrl+C). "
            f"Sent {batches_sent}/{total_batches} batch(es), {flows_sent} flow(s)."
        )

    return batches_sent, flows_sent




def _print_final_summary(
    stats: Dict[str, int],
    batches_sent: int,
    flows_sent: int,
    out_csv: Optional[str],
    dry_run: bool,
    model_id: str = DEFAULT_MODEL_ID,
    validation_errors: Optional[List[str]] = None,
) -> None:
    feature_list = FEATURES_BY_MODEL.get(model_id, UNIFIED_V2_FEATURES)
    schema_name  = FEATURE_SCHEMA_BY_MODEL.get(model_id, model_id)
    safe_print("\n-- Final Summary ----------------------------------------")
    print(f"  packets read          : {stats['packets_read']}")
    print(f"  usable IP packets     : {stats['usable_ip']}")
    print(f"  usable TCP/UDP pkts   : {stats['usable_tcp_udp']}")
    print(f"  skipped (non-IP)      : {stats['skipped_non_ip']}")
    print(f"  flows extracted       : {stats['flows_extracted']}")
    print(f"  flows skipped (short) : {stats['flows_skipped_short']}")
    print(f"  model                 : {model_id}")
    print(f"  feature schema        : {schema_name} ({len(feature_list)} features)")
    if validation_errors:
        for e in validation_errors:
            print(f"  [VALIDATION ERROR]    : {e}")
    else:
        print(f"  schema validation     : PASSED")
    if dry_run:
        print(f"  [dry-run] no data posted to API")
    else:
        print(f"  flows sent            : {flows_sent}")
        print(f"  batches sent          : {batches_sent}")
    if out_csv:
        print(f"  output CSV            : {Path(out_csv).resolve()}")
    safe_print("---------------------------------------------------------\n")




def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pcap_to_live_stream.py",
        description=(
            "PCAP → unified_relative_shape_v2 feature extractor → FastAPI live-ingest streamer.\n\n"
            "Reads an existing .pcap file (captured inside the Ubuntu Server VM),\n"
            "extracts flow features for the specified model, and streams them to\n"
            "POST /firewall/live-ingest.\n\n"
            "Default model : unified_relative_shape_v2__lgbm (12 unified features)\n"
            "Legacy model  : full_canonical__lgbm (34 features, use --model-id full_canonical__lgbm)\n\n"
            "Packet size    : IP total length (ip_layer.len), NOT Ethernet frame length.\n"
            "Direction      : 1=upload/client-to-server, 0=download/server-to-client.\n\n"
            "SAFETY: Does NOT capture live traffic. Does NOT call tcpdump.\n"
            "        All backend decisions remain simulation-only.\n\n"
            "Typical workflow:\n"
            "  Inside VM:    sudo tcpdump -i any -w /tmp/capture.pcap\n"
            "  Copy to host: scp -P 2222 scoti@127.0.0.1:/tmp/capture.pcap captures/\n"
            "  Stream:       python tools/pcap_to_live_stream.py "
            "--pcap captures/capture.pcap\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--pcap",
        required=True,
        metavar="PATH",
        help="Path to the .pcap file to read (required).",
    )
    p.add_argument(
        "--api",
        default="http://127.0.0.1:8765",
        metavar="URL",
        help="FastAPI base URL (default: http://127.0.0.1:8765).",
    )
    p.add_argument(
        "--batch-size",
        type=int,
        default=5,
        metavar="N",
        help="Number of flows to include per POST batch (default: 5).",
    )
    p.add_argument(
        "--delay-seconds",
        type=float,
        default=2.0,
        metavar="S",
        help="Seconds to wait between batches (default: 2).",
    )
    p.add_argument(
        "--source",
        default="vm-pcap",
        metavar="LABEL",
        help="Source label included in each batch payload (default: vm-pcap).",
    )
    p.add_argument(
        "--scenario",
        default="vm_pcap",
        metavar="NAME",
        help="Scenario name embedded in session_id (default: vm_pcap).",
    )
    p.add_argument(
        "--max-packets",
        type=int,
        default=None,
        metavar="N",
        help="Maximum number of packets to read from the PCAP (optional, reads all by default).",
    )
    p.add_argument(
        "--min-packets-per-flow",
        type=int,
        default=3,
        metavar="N",
        help="Minimum packets required to include a flow (default: 3).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Parse PCAP and extract features, print summary, optionally save CSV, "
            "but do NOT POST to the API."
        ),
    )
    p.add_argument(
        "--out-csv",
        default=None,
        metavar="PATH",
        help=(
            "Optional path to save extracted feature rows as CSV "
            "(parent dirs created automatically)."
        ),
    )
    p.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        metavar="MODEL_ID",
        choices=list(FEATURES_BY_MODEL.keys()),
        help=(
            f"Model ID to extract features for (default: {DEFAULT_MODEL_ID}). "
            "Choices: " + ", ".join(FEATURES_BY_MODEL.keys()) + ". "
            "Controls which feature schema is extracted."
        ),
    )
    return p




def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    model_id     = args.model_id
    feature_list = FEATURES_BY_MODEL.get(model_id, UNIFIED_V2_FEATURES)
    schema_name  = FEATURE_SCHEMA_BY_MODEL.get(model_id, model_id)

    pcap_path = Path(args.pcap)
    if not pcap_path.exists():
        print(f"[ERROR] PCAP file not found: {pcap_path.resolve()}")
        sys.exit(1)
    if not pcap_path.is_file():
        print(f"[ERROR] Path is not a regular file: {pcap_path.resolve()}")
        sys.exit(1)

    print(f"[*] Model          : {model_id}")
    print(f"[*] Feature schema : {schema_name} ({len(feature_list)} features)")
    print(f"[*] Packet size    : IP total length (ip_layer.len)")

    flow_rows, stats = parse_pcap(
        pcap_path=str(pcap_path),
        scenario=args.scenario,
        min_packets_per_flow=args.min_packets_per_flow,
        max_packets=args.max_packets,
        model_id=model_id,
    )

    safe_print("\n-- Extraction Summary -----------------------------------")
    print(f"  packets read          : {stats['packets_read']}")
    print(f"  usable IP packets     : {stats['usable_ip']}")
    print(f"  usable TCP/UDP pkts   : {stats['usable_tcp_udp']}")
    print(f"  skipped (non-IP)      : {stats['skipped_non_ip']}")
    print(f"  flows extracted       : {stats['flows_extracted']}")
    print(f"  flows skipped (short) : {stats['flows_skipped_short']}")

    validation_errors: List[str] = []
    if flow_rows:
        validation_errors = validate_rows(flow_rows, model_id=model_id)
        if validation_errors:
            print("\n[ERROR] Schema validation FAILED:")
            for e in validation_errors:
                print(f"  {e}")
        else:
            print(
                f"[*] Schema validation PASSED — "
                f"all {len(feature_list)} {schema_name} features present and numeric."
            )

    if args.out_csv and flow_rows:
        save_csv(flow_rows, args.out_csv, model_id=model_id)

    if len(flow_rows) < 1:
        print(
            "\n[!] No valid flows extracted. "
            "Try a longer capture or lower --min-packets-per-flow."
        )
        sys.exit(0)

    if validation_errors:
        print(
            f"\n[ERROR] Live PCAP features are not valid for {model_id}. "
            "Fix the converter before streaming to the API."
        )
        _print_final_summary(stats, 0, 0, args.out_csv, dry_run=True,
                             model_id=model_id, validation_errors=validation_errors)
        sys.exit(1)

    if args.dry_run:
        print("\n[dry-run] Feature extraction complete. Skipping API POST.")
        _print_final_summary(stats, 0, 0, args.out_csv, dry_run=True,
                             model_id=model_id, validation_errors=validation_errors)
        return

    batches_sent, flows_sent = stream_to_api(
        flow_rows=flow_rows,
        api_base=args.api,
        batch_size=args.batch_size,
        delay_seconds=args.delay_seconds,
        source=args.source,
        model_id=model_id,
    )

    _print_final_summary(stats, batches_sent, flows_sent, args.out_csv, dry_run=False,
                         model_id=model_id, validation_errors=validation_errors)


if __name__ == "__main__":
    main()

