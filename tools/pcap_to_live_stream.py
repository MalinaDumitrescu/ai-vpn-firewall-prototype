#!/usr/bin/env python3
"""
pcap_to_live_stream.py
======================
PCAP → robust9 feature extractor → FastAPI live-ingest streamer.

Reads an existing .pcap file captured inside the Ubuntu Server VM,
extracts robust9-compatible flow features, and streams them in batches to:
  POST /firewall/live-ingest

────────────────────────────────────────────────────────────────────
SAFETY CONSTRAINTS (enforced in this script):
  - Does NOT capture live traffic.
  - Does NOT call tcpdump, subprocess, or any shell command.
  - Does NOT modify iptables, nftables, Windows Firewall, or routing tables.
  - Does NOT require the FastAPI server to sniff packets.
  - Reads EXISTING .pcap files only.
  - All backend decisions are simulation-only.
  - Uses robust9_firewall feature format only.
────────────────────────────────────────────────────────────────────

Recommended workflow:
  1. Inside VM:   sudo tcpdump -i any -w /tmp/capture.pcap
  2. Copy to host: scp -P 2222 scoti@127.0.0.1:/tmp/capture.pcap captures/
  3. On host:     python tools/pcap_to_live_stream.py --pcap captures/capture.pcap

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
    # Python 3.7+: io.TextIOWrapper.reconfigure
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

# ─── dependency guard: scapy ─────────────────────────────────────────────────
try:
    from scapy.all import rdpcap, IP, TCP, UDP  # type: ignore[import]
except ImportError:
    print(
        "\n[ERROR] Missing dependency: scapy.\n"
        "Install with:\n"
        "  pip install -r tools/requirements_tools.txt\n"
    )
    sys.exit(1)

# ─── dependency guard: requests (only needed for live streaming) ──────────────
try:
    import requests as _requests  # type: ignore[import]
    _HAS_REQUESTS = True
except ImportError:
    _requests = None  # type: ignore[assignment]
    _HAS_REQUESTS = False

# ─── robust9 feature names ───────────────────────────────────────────────────

ROBUST9_FEATURES = [
    "sz_all_mean",
    "sz_cv",
    "sz_all_p25",
    "sz_all_median",
    "sz_all_p75",
    "sz_mean_max",
    "sz_mean_min",
    "sz_std_max",
    "sz_std_min",
]

FLOW_ROW_COLUMNS = [
    "session_id",
    "flow_id",
    "timestamp",
    "src_ip",
    "dst_ip",
    "protocol",
    "dst_port",
    "scenario",
] + ROBUST9_FEATURES

# ─── bidirectional flow key helpers ──────────────────────────────────────────


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
        # Non-TCP/UDP: normalize src/dst order only
        a, b = sorted([src_ip, dst_ip])
        return (a, b, protocol, None, None)


# ─── pure-Python statistics helpers ──────────────────────────────────────────


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


# ─── robust9 feature computation ─────────────────────────────────────────────


def _compute_robust9(
    sizes_a: List[float],
    sizes_b: List[float],
    all_sizes: List[float],
) -> Dict[str, float]:
    """Compute the 9 robust9 flow features from directional packet size lists."""
    if not all_sizes:
        return {k: 0.0 for k in ROBUST9_FEATURES}

    mean_all = _mean(all_sizes)
    sz_cv = (_std_pop(all_sizes) / mean_all) if mean_all != 0.0 else 0.0

    mean_a = _mean(sizes_a) if sizes_a else 0.0
    mean_b = _mean(sizes_b) if sizes_b else 0.0
    std_a  = _std_pop(sizes_a) if sizes_a else 0.0
    std_b  = _std_pop(sizes_b) if sizes_b else 0.0

    return {
        "sz_all_mean":   round(mean_all, 6),
        "sz_cv":         round(sz_cv, 6),
        "sz_all_p25":    round(_percentile(all_sizes, 25.0), 6),
        "sz_all_median": round(_percentile(all_sizes, 50.0), 6),
        "sz_all_p75":    round(_percentile(all_sizes, 75.0), 6),
        "sz_mean_max":   round(max(mean_a, mean_b), 6),
        "sz_mean_min":   round(min(mean_a, mean_b), 6),
        "sz_std_max":    round(max(std_a, std_b), 6),
        "sz_std_min":    round(min(std_a, std_b), 6),
    }


# ─── packet-size mode ────────────────────────────────────────────────────────
#
# The robust9 training pipeline computed sz_* features from the IP-layer
# *declared* total length (the ``len`` field of the IP header). Matching that
# convention here is critical so the live-extracted features land in the same
# distribution the model was trained on. Empirical parity check vs. the
# training distributions:
#
#   usbvpn  sz_all_mean min=28   p25=330.5  median=480.2  mean=604.9  p75=763.3
#   iscx    sz_all_mean min=30   p25= 80.1  median=150.0  mean=248.3  p75=256.7
#
# The 28/30-byte minima rule out frame-size (>= 60 due to Ethernet padding) and
# payload-only (often 0 for ACK-only packets). They are characteristic of the
# IP total-length field. See tools/debug_robust9_parity.py for the comparator.

PKT_SIZE_MODES = ("ip_field", "ip_layer", "frame", "payload")
DEFAULT_PKT_SIZE_MODE = "ip_field"


def get_packet_size(pkt, pkt_size_mode: str = DEFAULT_PKT_SIZE_MODE) -> Optional[float]:
    """Return the per-packet size used by the robust9 sz_* features.

    Modes
    -----
    ip_field (default)
        IP header's declared total-length field. Matches the original training
        feature extractor.
    ip_layer
        Bytes of the IP layer as serialized by scapy (header + payload).
        Useful for raw IP captures with no Ethernet.
    frame
        Full L2 frame including Ethernet. Off by ~14 bytes vs. training on
        Ethernet captures.
    payload
        L4 payload bytes only. Wrong for the training distribution because
        ACK-only packets collapse to 0. Debug-only.

    Returns ``None`` if the packet should be skipped (e.g. a non-IP frame in
    ``ip_field`` / ``ip_layer`` / ``payload`` modes).
    """
    if pkt_size_mode == "ip":
        pkt_size_mode = "ip_field"

    if pkt_size_mode == "frame":
        return float(len(pkt))

    if not pkt.haslayer(IP):
        return None

    ip = pkt[IP]

    if pkt_size_mode == "ip_field":
        val = getattr(ip, "len", None)
        if val is None or val == 0:
            # Scapy sometimes leaves ip.len unset on synthesized / truncated
            # packets; fall back to the serialized IP-layer length.
            return float(len(ip))
        return float(val)

    if pkt_size_mode == "ip_layer":
        return float(len(ip))

    if pkt_size_mode == "payload":
        if pkt.haslayer(TCP):
            return float(len(pkt[TCP].payload))
        if pkt.haslayer(UDP):
            return float(len(pkt[UDP].payload))
        return 0.0

    raise ValueError(
        f"Unsupported pkt_size_mode: {pkt_size_mode!r}. "
        f"Expected one of {PKT_SIZE_MODES} (or alias 'ip')."
    )


# ─── PCAP parsing ─────────────────────────────────────────────────────────────


def parse_pcap(
    pcap_path: str,
    scenario: str,
    min_packets_per_flow: int,
    max_packets: Optional[int],
    pkt_size_mode: str = DEFAULT_PKT_SIZE_MODE,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Parse a PCAP file and return (flow_rows, stats_dict).

    Each flow must have ≥ min_packets_per_flow packets to be included.
    Uses 5-second time windows for session_id assignment.

    ``pkt_size_mode`` controls how per-packet byte sizes are measured for the
    sz_* features; default ``ip_field`` matches the robust9 training pipeline.
    """
    print(f"[*] Reading PCAP: {pcap_path}")
    print(f"[*] packet_size_mode={pkt_size_mode}")
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
    skipped_no_size = 0
    pkt_count       = 0
    capture_start_time: Optional[float] = None

    # flow_key → accumulator dict
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
        pkt_len   = get_packet_size(pkt, pkt_size_mode)
        if pkt_len is None:
            skipped_no_size += 1
            continue
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
                # canonical identifiers from the key
                "src_ip":       key[0],
                "dst_ip":       key[1],
                "protocol":     protocol,
                # key[4] = port_b (higher port) or None for non-TCP/UDP
                "dst_port":     key[4],
            }

        flow = flows[key]
        flow["all_sizes"].append(pkt_len)

        # Assign packet to direction A (first-seen src) or B (reverse)
        if src_ip == flow["first_src_ip"]:
            flow["sizes_a"].append(pkt_len)
        else:
            flow["sizes_b"].append(pkt_len)

    if capture_start_time is None:
        capture_start_time = 0.0

    # ── Build flow rows ────────────────────────────────────────────────────
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

        feats = _compute_robust9(flow["sizes_a"], flow["sizes_b"], flow["all_sizes"])

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
        "skipped_no_size":     skipped_no_size,
        "flows_extracted":     len(flow_rows),
        "flows_skipped_short": flows_skipped_short,
    }

    return flow_rows, stats


# ─── CSV save ────────────────────────────────────────────────────────────────


def save_csv(flow_rows: List[Dict[str, Any]], out_csv: str) -> None:
    """Save extracted flow feature rows to a CSV file; creates parent dirs."""
    p = Path(out_csv)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FLOW_ROW_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flow_rows)
    print(f"[*] Saved {len(flow_rows)} flow row(s) to: {p.resolve()}")


# ─── streaming ───────────────────────────────────────────────────────────────


def stream_to_api(
    flow_rows: List[Dict[str, Any]],
    api_base: str,
    batch_size: int,
    delay_seconds: float,
    source: str,
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

    url           = f"{api_base.rstrip('/')}/firewall/live-ingest"
    total_batches = math.ceil(len(flow_rows) / batch_size)
    batches_sent  = 0
    flows_sent    = 0

    print(f"\n[*] Streaming {len(flow_rows)} flow(s) across {total_batches} batch(es)")
    print(f"    Endpoint  : {url}")
    print(f"    batch_size: {batch_size}   delay: {delay_seconds}s\n")

    try:
        for batch_num in range(total_batches):
            start = batch_num * batch_size
            end   = min(start + batch_size, len(flow_rows))
            batch = flow_rows[start:end]

            batch_id = f"pcap_batch_{batch_num + 1:04d}"
            payload  = {
                "source":   source,
                "batch_id": batch_id,
                "flows":    batch,
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

            print(
                f"  [{batch_id}] sent {len(batch):>3} flow(s) | "
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


# ─── summary printer ─────────────────────────────────────────────────────────


def _print_final_summary(
    stats: Dict[str, int],
    batches_sent: int,
    flows_sent: int,
    out_csv: Optional[str],
    dry_run: bool,
) -> None:
    safe_print("\n-- Final Summary ----------------------------------------")
    print(f"  packets read          : {stats['packets_read']}")
    print(f"  usable IP packets     : {stats['usable_ip']}")
    print(f"  usable TCP/UDP pkts   : {stats['usable_tcp_udp']}")
    print(f"  skipped (non-IP)      : {stats['skipped_non_ip']}")
    print(f"  flows extracted       : {stats['flows_extracted']}")
    print(f"  flows skipped (short) : {stats['flows_skipped_short']}")
    if dry_run:
        print(f"  [dry-run] no data posted to API")
    else:
        print(f"  flows sent            : {flows_sent}")
        print(f"  batches sent          : {batches_sent}")
    if out_csv:
        print(f"  output CSV            : {Path(out_csv).resolve()}")
    safe_print("---------------------------------------------------------\n")


# ─── CLI argument parser ──────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pcap_to_live_stream.py",
        description=(
            "PCAP → robust9 feature extractor → FastAPI live-ingest streamer.\n\n"
            "Reads an existing .pcap file (captured inside the Ubuntu Server VM),\n"
            "extracts robust9-compatible flow features, and streams them to\n"
            "POST /firewall/live-ingest so the frontend Live VM Monitor updates\n"
            "session labels in near real time.\n\n"
            "SAFETY: Does NOT capture live traffic. Does NOT call tcpdump.\n"
            "        All backend decisions remain simulation-only.\n\n"
            "Typical workflow:\n"
            "  Inside VM:   sudo tcpdump -i any -w /tmp/capture.pcap\n"
            "  Copy to host: scp -P 2222 scoti@127.0.0.1:/tmp/capture.pcap captures/\n"
            "  Stream:      python tools/pcap_to_live_stream.py "
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
        help="Optional path to save extracted robust9 feature rows as CSV (parent dirs created automatically).",
    )
    p.add_argument(
        "--pkt-size-mode",
        default=DEFAULT_PKT_SIZE_MODE,
        choices=list(PKT_SIZE_MODES) + ["ip"],
        metavar="MODE",
        help=(
            "How to measure each packet's byte size for the sz_* features. "
            "Choices: ip_field (default; matches training, alias 'ip'), "
            "ip_layer (scapy IP-layer length), frame (full L2 frame), "
            "payload (L4 payload only; debug only)."
        ),
    )
    return p


# ─── entry point ─────────────────────────────────────────────────────────────


def main() -> None:
    parser = _build_parser()
    args   = parser.parse_args()

    # ── validate PCAP path ──────────────────────────────────────────────────
    pcap_path = Path(args.pcap)
    if not pcap_path.exists():
        print(f"[ERROR] PCAP file not found: {pcap_path.resolve()}")
        sys.exit(1)
    if not pcap_path.is_file():
        print(f"[ERROR] Path is not a regular file: {pcap_path.resolve()}")
        sys.exit(1)

    # ── parse PCAP → flow features ─────────────────────────────────────────
    flow_rows, stats = parse_pcap(
        pcap_path=str(pcap_path),
        scenario=args.scenario,
        min_packets_per_flow=args.min_packets_per_flow,
        max_packets=args.max_packets,
        pkt_size_mode=args.pkt_size_mode,
    )

    # ── extraction summary ─────────────────────────────────────────────────
    safe_print("\n-- Extraction Summary -----------------------------------")
    print(f"  packets read          : {stats['packets_read']}")
    print(f"  usable IP packets     : {stats['usable_ip']}")
    print(f"  usable TCP/UDP pkts   : {stats['usable_tcp_udp']}")
    print(f"  skipped (non-IP)      : {stats['skipped_non_ip']}")
    print(f"  flows extracted       : {stats['flows_extracted']}")
    print(f"  flows skipped (short) : {stats['flows_skipped_short']}")

    # ── save CSV if requested ──────────────────────────────────────────────
    if args.out_csv and flow_rows:
        save_csv(flow_rows, args.out_csv)

    # ── bail if no usable flows ─────────────────────────────────────────────
    if len(flow_rows) < 1:
        print(
            "\n[!] No valid flows extracted. "
            "Try a longer capture or lower --min-packets-per-flow."
        )
        sys.exit(0)

    # ── dry-run: stop here ─────────────────────────────────────────────────
    if args.dry_run:
        print("\n[dry-run] Feature extraction complete. Skipping API POST.")
        _print_final_summary(stats, 0, 0, args.out_csv, dry_run=True)
        return

    # ── live streaming ─────────────────────────────────────────────────────
    batches_sent, flows_sent = stream_to_api(
        flow_rows=flow_rows,
        api_base=args.api,
        batch_size=args.batch_size,
        delay_seconds=args.delay_seconds,
        source=args.source,
    )

    _print_final_summary(stats, batches_sent, flows_sent, args.out_csv, dry_run=False)


if __name__ == "__main__":
    main()

