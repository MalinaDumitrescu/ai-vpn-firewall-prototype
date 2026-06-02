"""Split captures/vm_openvpn_lab_auto.pcap into three capture-point subsets.

Subsets mimic the three capture interfaces a real demo would use:

  A. broad:  captures/vm_openvpn_lab_split_any.pcap     (all packets — equivalent to tcpdump -i any)
  B. inner:  captures/vm_openvpn_lab_split_tun.pcap     (10.8.0.0/24 only — equivalent to tcpdump -i tun0)
  C. outer:  captures/vm_openvpn_lab_split_outer.pcap   (UDP/1194 only — equivalent to
                                                          tcpdump -i ens3 udp port 1194)

Read-only relative to the original PCAP. No network capture, no shell calls.
"""
from __future__ import annotations
from pathlib import Path
from scapy.all import PcapReader, PcapWriter, IP, UDP, TCP  # type: ignore

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "captures" / "vm_openvpn_lab_auto.pcap"
OUT_ANY   = ROOT / "captures" / "vm_openvpn_lab_split_any.pcap"
OUT_INNER = ROOT / "captures" / "vm_openvpn_lab_split_tun.pcap"
OUT_OUTER = ROOT / "captures" / "vm_openvpn_lab_split_outer.pcap"


def is_inner(pkt) -> bool:
    if IP not in pkt:
        return False
    s, d = str(pkt[IP].src), str(pkt[IP].dst)
    return s.startswith("10.8.0.") and d.startswith("10.8.0.")


def is_outer_openvpn(pkt) -> bool:
    if IP not in pkt:
        return False
    if UDP in pkt:
        if pkt[UDP].sport == 1194 or pkt[UDP].dport == 1194:
            return True
    if TCP in pkt:
        if pkt[TCP].sport == 1194 or pkt[TCP].dport == 1194:
            return True
    return False


def main() -> None:
    if not SRC.exists():
        raise SystemExit(f"missing source pcap: {SRC}")

    n_total = n_any = n_inner = n_outer = 0
    w_any   = PcapWriter(str(OUT_ANY), append=False, sync=True)
    w_inner = PcapWriter(str(OUT_INNER), append=False, sync=True)
    w_outer = PcapWriter(str(OUT_OUTER), append=False, sync=True)
    try:
        with PcapReader(str(SRC)) as reader:
            for pkt in reader:
                n_total += 1
                w_any.write(pkt); n_any += 1
                if is_inner(pkt):
                    w_inner.write(pkt); n_inner += 1
                elif is_outer_openvpn(pkt):
                    w_outer.write(pkt); n_outer += 1
    finally:
        w_any.close(); w_inner.close(); w_outer.close()

    for label, path, count in [
        ("ANY",   OUT_ANY,   n_any),
        ("INNER", OUT_INNER, n_inner),
        ("OUTER", OUT_OUTER, n_outer),
    ]:
        sz = path.stat().st_size if path.exists() else 0
        print(f"[{label:5}] {count:6} pkts  size={sz:>12,} bytes  -> {path}")
    print(f"[TOTAL] {n_total} packets read from source.")


if __name__ == "__main__":
    main()

