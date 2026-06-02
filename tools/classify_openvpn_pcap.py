"""
Read-only classification of the OpenVPN lab PCAP.

For each PCAP under ./captures/vm_openvpn_lab*.pcap, build per-5-tuple
flow statistics, classify into:
  - inner_tunnel_http       (10.8.0.x ↔ 10.8.0.x, port 8000 or other tunnel HTTP)
  - inner_tunnel_other      (10.8.0.x ↔ 10.8.0.x, any other port)
  - outer_openvpn_transport (UDP/TCP 1194 or other OpenVPN port between
                             non-tunnel IPs, e.g. VirtualBox NAT, host-only)
  - ssh_control             (TCP 22 between NAT/host-only IPs)
  - dns                     (UDP/TCP 53)
  - nat_or_local_control    (loopback, mDNS 5353, NetBIOS, DHCP, ARP-ish)
  - icmp                    (ICMP/ICMPv6)
  - unknown                 (everything else)

Cross-references each flow with the latest vm_openvpn_lab_auto_features.csv
to mark inclusion.

Writes:
  artifacts/runtime_integration_thesis/thesis_exports/openvpn_flow_classification.md
  artifacts/runtime_integration_thesis/thesis_exports/openvpn_flow_classification.csv
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from datetime import datetime, timezone
from ipaddress import IPv4Address, ip_address
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scapy.all import PcapReader  # type: ignore
from scapy.layers.inet import IP, TCP, UDP, ICMP  # type: ignore
from scapy.layers.inet6 import IPv6  # type: ignore
from scapy.layers.l2 import ARP  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
CAPTURES = ROOT / "captures"
OUT_DIR = ROOT / "artifacts" / "runtime_integration_thesis" / "thesis_exports"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Pin scope to the *latest* OpenVPN lab PCAP that the demo script writes.
PRIMARY_PCAP = CAPTURES / "vm_openvpn_lab_auto.pcap"

FEATURES_CSV = CAPTURES / "vm_openvpn_lab_auto_features.csv"

# OpenVPN transport candidate ports (config-default + common alternates seen in the lab).
OPENVPN_PORTS = {1194, 1195, 443}  # UDP 1194 default; TCP 443 / UDP 1195 alt
INNER_TUNNEL_NET = ("10.8.0.",)     # configured tunnel /24 (per lab script)
HTTP_DEMO_PORTS = {8000, 80, 8080}


def is_inner_tunnel_ip(ip: str) -> bool:
    return any(ip.startswith(prefix) for prefix in INNER_TUNNEL_NET)


def is_loopback(ip: str) -> bool:
    try:
        return ip_address(ip).is_loopback
    except Exception:
        return False


def is_multicast(ip: str) -> bool:
    try:
        return ip_address(ip).is_multicast
    except Exception:
        return False


def classify_flow(
    proto: str, src: str, dst: str, sport: Optional[int], dport: Optional[int]
) -> Tuple[str, str]:
    a_inner = is_inner_tunnel_ip(src)
    b_inner = is_inner_tunnel_ip(dst)
    pset = {sport, dport} if (sport is not None or dport is not None) else set()

    if proto == "ICMP":
        if a_inner or b_inner:
            return "icmp", "ICMP on tunnel network"
        return "icmp", "ICMP on non-tunnel network"

    if pset & {53}:
        return "dns", "DNS port 53"

    if pset & {22}:
        return "ssh_control", "TCP/22 SSH"

    if a_inner and b_inner:
        if pset & HTTP_DEMO_PORTS:
            return "inner_tunnel_http", f"10.8.0.x↔10.8.0.x with HTTP port {pset & HTTP_DEMO_PORTS}"
        # ephemeral TCP between tunnel IPs — almost certainly the HTTP downloads
        # initiated by the demo script (curl small/medium/large.bin from 10.8.0.1:8000)
        # but tcpdump -i any on SLL2 may strip the demo port if it became a high
        # ephemeral. Tag conservatively.
        return "inner_tunnel_other", "10.8.0.x↔10.8.0.x, no demo HTTP port in 5-tuple"

    if pset & OPENVPN_PORTS:
        return "outer_openvpn_transport", f"port {pset & OPENVPN_PORTS} in OpenVPN candidate set"

    if is_loopback(src) or is_loopback(dst):
        return "nat_or_local_control", "loopback traffic"

    if is_multicast(src) or is_multicast(dst):
        return "nat_or_local_control", "multicast (mDNS/etc)"

    # VirtualBox NAT default: 10.0.2.0/24
    if src.startswith("10.0.2.") or dst.startswith("10.0.2."):
        return "nat_or_local_control", "VirtualBox NAT 10.0.2.0/24"

    # Host-only network seen in the diagnosis: 10.10.10.0/24
    if src.startswith("10.10.10.") or dst.startswith("10.10.10."):
        return "nat_or_local_control", "host-only 10.10.10.0/24 (no OpenVPN port observed)"

    return "unknown", "no rule matched"


def proto_name(pkt) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    if TCP in pkt:
        return "TCP", int(pkt[TCP].sport), int(pkt[TCP].dport)
    if UDP in pkt:
        return "UDP", int(pkt[UDP].sport), int(pkt[UDP].dport)
    if ICMP in pkt:
        return "ICMP", None, None
    return None, None, None


def parse_pcap(path: Path) -> Tuple[Dict[Tuple, Dict[str, Any]], int, int, Dict[str, int]]:
    flows: Dict[Tuple, Dict[str, Any]] = {}
    pkt_count = 0
    byte_count = 0
    non_ip = defaultdict(int)
    with PcapReader(str(path)) as reader:
        for pkt in reader:
            pkt_count += 1
            byte_count += len(pkt)
            if IP in pkt:
                ip_layer = pkt[IP]
                src, dst = str(ip_layer.src), str(ip_layer.dst)
                ip_size = int(ip_layer.len) if hasattr(ip_layer, "len") else len(pkt)
            elif IPv6 in pkt:
                non_ip["IPv6"] += 1
                continue
            elif ARP in pkt:
                non_ip["ARP"] += 1
                continue
            else:
                non_ip["other_non_ip"] += 1
                continue
            proto, sport, dport = proto_name(pkt)
            if proto is None:
                non_ip[f"ip_proto_{int(ip_layer.proto)}"] += 1
                continue
            # Canonical 5-tuple key (lower-tuple side first → bidirectional)
            a = (src, sport)
            b = (dst, dport)
            lo, hi = sorted([a, b])
            key = (proto, lo[0], lo[1], hi[0], hi[1])
            ts = float(pkt.time)
            f = flows.get(key)
            if f is None:
                flows[key] = {
                    "proto": proto,
                    "src_ip": src,
                    "dst_ip": dst,
                    "src_port": sport,
                    "dst_port": dport,
                    "packets": 1,
                    "bytes": ip_size,
                    "t_first": ts,
                    "t_last": ts,
                }
            else:
                f["packets"] += 1
                f["bytes"] += ip_size
                if ts < f["t_first"]:
                    f["t_first"] = ts
                if ts > f["t_last"]:
                    f["t_last"] = ts
    return flows, pkt_count, byte_count, dict(non_ip)


def load_features_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def features_lookup_key(row: Dict[str, str]) -> Tuple[str, str, str]:
    """Build a 3-tuple (proto, src_ip, dst_ip) for cross-reference (no ports
    if missing). Ports are not always present in the unified features CSV."""
    return (row.get("protocol", ""), row.get("src_ip", ""), row.get("dst_ip", ""))


def fmt_int(n) -> str:
    return f"{int(n):,}"


def main() -> int:
    if not PRIMARY_PCAP.exists():
        print(f"PCAP not found: {PRIMARY_PCAP}", file=sys.stderr)
        return 2

    print(f"[*] Reading {PRIMARY_PCAP} ...")
    flows, total_pkts, total_bytes, non_ip = parse_pcap(PRIMARY_PCAP)
    print(f"[*] Parsed {total_pkts} packets, {total_bytes} bytes, {len(flows)} 5-tuple flows.")
    feat_rows = load_features_csv(FEATURES_CSV)
    print(f"[*] Features CSV rows: {len(feat_rows)}")

    # Build a coarse lookup of feature CSV rows by (proto, ip-pair)
    feat_index: Dict[Tuple[str, frozenset], List[Dict[str, str]]] = defaultdict(list)
    for row in feat_rows:
        proto = row.get("protocol", "")
        s = row.get("src_ip", "")
        d = row.get("dst_ip", "")
        feat_index[(proto, frozenset({s, d}))].append(row)

    # Tabulate
    table_rows: List[Dict[str, Any]] = []
    cat_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: {"flows": 0, "packets": 0, "bytes": 0})
    for key, f in flows.items():
        proto = f["proto"]
        src, dst = f["src_ip"], f["dst_ip"]
        sport, dport = f["src_port"], f["dst_port"]
        category, reason = classify_flow(proto, src, dst, sport, dport)
        dur = f["t_last"] - f["t_first"]
        # Lookup feature inclusion
        match_proto = proto
        included = False
        match_rows = feat_index.get((match_proto, frozenset({src, dst})), [])
        # Be tolerant: ICMP is sometimes "1" or "ICMP"
        if not match_rows and proto == "ICMP":
            match_rows = feat_index.get(("1", frozenset({src, dst})), [])
        included = bool(match_rows)
        # Add to totals
        ct = cat_totals[category]
        ct["flows"] += 1
        ct["packets"] += f["packets"]
        ct["bytes"] += f["bytes"]
        table_rows.append({
            "proto": proto,
            "src_ip": src,
            "dst_ip": dst,
            "src_port": sport,
            "dst_port": dport,
            "packets": f["packets"],
            "bytes": f["bytes"],
            "duration_s": round(dur, 3),
            "category": category,
            "reason": reason,
            "in_features_csv": included,
            "feature_csv_matches": len(match_rows),
        })

    table_rows.sort(key=lambda r: (r["category"], -r["packets"]))

    # Write CSV
    csv_path = OUT_DIR / "openvpn_flow_classification.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "proto", "src_ip", "dst_ip", "src_port", "dst_port",
                "packets", "bytes", "duration_s",
                "category", "reason", "in_features_csv", "feature_csv_matches",
            ],
        )
        writer.writeheader()
        writer.writerows(table_rows)

    # Markdown report
    md = []
    md.append("# OpenVPN Lab PCAP — Flow Classification\n")
    md.append(f"**Generated:** {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")
    md.append(f"**PCAP:** `{PRIMARY_PCAP}`  ")
    sz = PRIMARY_PCAP.stat().st_size
    mt = datetime.fromtimestamp(PRIMARY_PCAP.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
    md.append(f"**PCAP size:** {fmt_int(sz)} bytes  ")
    md.append(f"**PCAP mtime:** {mt}  ")
    md.append(f"**Features CSV cross-referenced:** `{FEATURES_CSV}` ({len(feat_rows)} rows)\n")
    md.append(f"**Total packets parsed:** {fmt_int(total_pkts)}  ")
    md.append(f"**Total bytes parsed:** {fmt_int(total_bytes)}  ")
    md.append(f"**Distinct 5-tuple flows:** {fmt_int(len(flows))}\n")
    if non_ip:
        md.append(f"**Non-IP / unparsed:** {non_ip}\n")

    # Per-category summary
    md.append("## A. Category Summary\n")
    md.append("| Category | Flows | Packets | Bytes | % packets | % bytes |")
    md.append("|---|---:|---:|---:|---:|---:|")
    tot_p = max(1, sum(c["packets"] for c in cat_totals.values()))
    tot_b = max(1, sum(c["bytes"] for c in cat_totals.values()))
    for cat in sorted(cat_totals.keys(), key=lambda k: -cat_totals[k]["packets"]):
        c = cat_totals[cat]
        md.append(
            f"| `{cat}` | {c['flows']} | {fmt_int(c['packets'])} | {fmt_int(c['bytes'])} "
            f"| {100*c['packets']/tot_p:.1f}% | {100*c['bytes']/tot_b:.1f}% |"
        )
    md.append("")

    # Top flows by packets
    md.append("## B. Top 20 Flows by Packet Count\n")
    md.append("| # | proto | src_ip:src_port | dst_ip:dst_port | packets | bytes | dur (s) | category | in_csv |")
    md.append("|--:|---|---|---|---:|---:|---:|---|:---:|")
    by_pkts = sorted(table_rows, key=lambda r: -r["packets"])[:20]
    for i, r in enumerate(by_pkts, 1):
        sp = r["src_port"] if r["src_port"] is not None else "-"
        dp = r["dst_port"] if r["dst_port"] is not None else "-"
        md.append(
            f"| {i} | {r['proto']} | {r['src_ip']}:{sp} | {r['dst_ip']}:{dp} "
            f"| {fmt_int(r['packets'])} | {fmt_int(r['bytes'])} | {r['duration_s']} "
            f"| `{r['category']}` | {'✓' if r['in_features_csv'] else '·'} |"
        )
    md.append("")

    # Top flows by bytes
    md.append("## C. Top 20 Flows by Byte Count\n")
    md.append("| # | proto | src_ip:src_port | dst_ip:dst_port | packets | bytes | dur (s) | category | in_csv |")
    md.append("|--:|---|---|---|---:|---:|---:|---|:---:|")
    by_bytes = sorted(table_rows, key=lambda r: -r["bytes"])[:20]
    for i, r in enumerate(by_bytes, 1):
        sp = r["src_port"] if r["src_port"] is not None else "-"
        dp = r["dst_port"] if r["dst_port"] is not None else "-"
        md.append(
            f"| {i} | {r['proto']} | {r['src_ip']}:{sp} | {r['dst_ip']}:{dp} "
            f"| {fmt_int(r['packets'])} | {fmt_int(r['bytes'])} | {r['duration_s']} "
            f"| `{r['category']}` | {'✓' if r['in_features_csv'] else '·'} |"
        )
    md.append("")

    # Full flow table by category
    md.append("## D. Full Flow Classification\n")
    md.append("All distinct 5-tuple flows, grouped by category, sorted within each category by packet count (descending).\n")
    md.append("| proto | src_ip:src_port | dst_ip:dst_port | packets | bytes | dur (s) | category | reason | in_csv |")
    md.append("|---|---|---|---:|---:|---:|---|---|:---:|")
    for r in table_rows:
        sp = r["src_port"] if r["src_port"] is not None else "-"
        dp = r["dst_port"] if r["dst_port"] is not None else "-"
        md.append(
            f"| {r['proto']} | {r['src_ip']}:{sp} | {r['dst_ip']}:{dp} "
            f"| {fmt_int(r['packets'])} | {fmt_int(r['bytes'])} | {r['duration_s']} "
            f"| `{r['category']}` | {r['reason']} | {'✓' if r['in_features_csv'] else '·'} |"
        )
    md.append("")

    # Verdict
    inner = cat_totals.get("inner_tunnel_http", {"packets": 0, "bytes": 0})["packets"] + \
            cat_totals.get("inner_tunnel_other", {"packets": 0, "bytes": 0})["packets"]
    outer = cat_totals.get("outer_openvpn_transport", {"packets": 0, "bytes": 0})["packets"]
    inner_b = cat_totals.get("inner_tunnel_http", {"packets": 0, "bytes": 0})["bytes"] + \
              cat_totals.get("inner_tunnel_other", {"packets": 0, "bytes": 0})["bytes"]
    outer_b = cat_totals.get("outer_openvpn_transport", {"packets": 0, "bytes": 0})["bytes"]
    other_b = tot_b - inner_b - outer_b

    md.append("## E. Verdict\n")
    md.append(f"- Inner tunnel packets : {fmt_int(inner)} ({100*inner/tot_p:.1f}%)")
    md.append(f"- Inner tunnel bytes   : {fmt_int(inner_b)} ({100*inner_b/tot_b:.1f}%)")
    md.append(f"- Outer OpenVPN packets: {fmt_int(outer)} ({100*outer/tot_p:.1f}%)")
    md.append(f"- Outer OpenVPN bytes  : {fmt_int(outer_b)} ({100*outer_b/tot_b:.1f}%)")
    md.append(f"- Other/control bytes  : {fmt_int(other_b)} ({100*other_b/tot_b:.1f}%)\n")

    # Pick verdict letter
    if outer_b > 0.6 * tot_b:
        verdict = "B. PCAP mainly contains outer encrypted OpenVPN transport."
    elif inner_b > 0.6 * tot_b:
        verdict = "A. PCAP mainly contains inner tunnel traffic (10.8.0.x flows; HTTP only inferable from lab setup, not from L7 in saved features)."
    elif (inner_b + outer_b) > 0.6 * tot_b:
        verdict = "C. PCAP is mixed (inner + outer + control). Cannot support a clean OpenVPN detection claim without further filtering."
    elif inner_b == 0 and outer_b == 0:
        verdict = "D. Evidence insufficient — neither inner tunnel nor outer OpenVPN transport is identifiable in the saved PCAP."
    else:
        verdict = "C. PCAP is mixed (no single category dominates). Cannot support a clean OpenVPN detection claim."
    md.append(f"**Final verdict: {verdict}**\n")

    # Caveats
    md.append("## F. Caveats\n")
    md.append(
        "- Categories are based on packet-header fields only (5-tuple). "
        "HTTP cannot be confirmed without L7 inspection; flows on tunnel IPs are "
        "labelled `inner_tunnel_http` only when a demo HTTP port (8000/80/8080) "
        "appears in the 5-tuple. Otherwise `inner_tunnel_other`.\n"
        "- `outer_openvpn_transport` requires UDP/TCP 1194 (or 1195/443) in the "
        "5-tuple. If the encrypted carrier ran on a non-default port not in this "
        "set, those flows fall to `unknown` or `nat_or_local_control`.\n"
        "- The features CSV is the **unified_relative_shape_v2** schema (12 features, "
        "produced on 2026-06-02). Inclusion check uses (protocol, ip-pair) only; "
        "port-level identity is not always preserved in the CSV.\n"
        "- `tcpdump -i any` on Linux SLL2 may have captured both inner (tun0) and "
        "outer (eth0/ens3) frames in the same file. Where both directions of an inner "
        "flow appear with raw IP headers, they are counted once per 5-tuple.\n"
    )

    out_md = OUT_DIR / "openvpn_flow_classification.md"
    out_md.write_text("\n".join(md), encoding="utf-8")
    print(f"[*] Wrote {out_md}")
    print(f"[*] Wrote {csv_path}")
    print(f"[*] Verdict: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


