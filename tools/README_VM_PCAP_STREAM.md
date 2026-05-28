# VM PCAP Streaming Workflow — AI VPN Firewall Prototype

---

## 1. Purpose

This workflow demonstrates VM-generated traffic being captured as a PCAP file, converted into **robust9-compatible flow features**, and streamed to the prototype FastAPI backend for simulated live labels.

**Important:**

- ❌ No packets are blocked at any point.
- ❌ The web application does not sniff live network traffic.
- ✅ The Python streamer (`pcap_to_live_stream.py`) reads an **existing PCAP file only**.
- ✅ All model decisions are **simulation-only** — for thesis demonstration purposes.

---

## 2. Start the Ubuntu Server VM from Windows CMD

Open a Windows Command Prompt and run:

```cmd
"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" startvm "Ubunutu" --type headless
```

> **VM setup reminder:**
> - Platform: Oracle VirtualBox
> - Guest OS: Ubuntu Server
> - Network mode: **NAT** (no Bridged Adapter required)
> - VM internal IP: `10.0.2.15`
> - SSH port forwarding: `127.0.0.1:2222` (Windows) → port `22` (VM)

Wait ~15–20 seconds for the VM to fully boot before SSH-ing in.

---

## 3. SSH into the VM from Windows CMD

```cmd
ssh scoti@127.0.0.1 -p 2222
```

If prompted to accept a host key fingerprint, type `yes`.

---

## 4. Install tcpdump Inside the VM (if not already installed)

Once logged in over SSH:

```bash
sudo apt update
sudo apt install tcpdump -y
```

Verify it is installed:

```bash
tcpdump --version
```

---

## 5. Capture Traffic Inside the VM

In the SSH session, start a capture on all interfaces and write to a file:

```bash
sudo tcpdump -i any -w vm_test.pcap
```

- **Keep this running** while you generate traffic (see Section 6).
- Stop it with **Ctrl+C** when done.
- The file `vm_test.pcap` will be saved in your home directory (`~/vm_test.pcap`).

> **Tip:** Open a second SSH session (`ssh scoti@127.0.0.1 -p 2222`) to generate traffic while tcpdump keeps running in the first.

---

## 6. Generate Harmless Traffic Inside the VM

Open a **second SSH session** into the VM and run any of the following:

### Basic HTTP/HTTPS requests

```bash
curl https://example.com
curl https://www.wikipedia.org
ping -c 5 8.8.8.8
```

### Repeated browsing-like traffic loop

```bash
for i in {1..20}; do
  curl -L https://example.com > /dev/null 2>&1
  sleep 1
done
```

### Download a larger file for more packets

```bash
curl -L -o /dev/null https://releases.ubuntu.com/22.04/ubuntu-22.04.5-live-server-amd64.iso.zsync
```

> **Note on traffic classification:**
> If all traffic is HTTPS/TLS-encrypted, this is referred to as an **"encrypted / VPN-like traffic scenario"** — the model sees packet-size statistics, not payload content. This does **not** mean a VPN client is running; it is simply encrypted web traffic that may structurally resemble VPN flows. To simulate actual VPN traffic, you would need to run a VPN client (e.g., WireGuard or OpenVPN) inside the VM.

Once you have enough traffic, go back to the first session and press **Ctrl+C** to stop tcpdump.

---

## 7. Copy the PCAP File from the VM to the Windows Host

### Step 1 — Create the captures folder on Windows (if it does not exist)

Open a new **Windows CMD** window:

```cmd
mkdir C:\Users\scoti\PycharmProjects\ai-vpn-firewall-prototype\captures
```

### Step 2 — SCP the PCAP from the VM

```cmd
scp -P 2222 scoti@127.0.0.1:~/vm_test.pcap C:\Users\scoti\PycharmProjects\ai-vpn-firewall-prototype\captures\vm_test.pcap
```

Verify the file arrived:

```cmd
dir C:\Users\scoti\PycharmProjects\ai-vpn-firewall-prototype\captures\
```

---

## 8. Start the Backend on Windows

Open a new **Windows CMD** or **PowerShell** window:

```cmd
cd C:\Users\scoti\PycharmProjects\ai-vpn-firewall-prototype\backend
python -m uvicorn main:app --host 127.0.0.1 --port 8765
```

Leave this window open. The backend must be running before streaming.

> Check it is alive: open `http://127.0.0.1:8765/docs` in a browser — you should see the FastAPI Swagger UI.

---

## 9. Start the Frontend on Windows

Open another **Windows CMD** or **PowerShell** window:

```cmd
cd C:\Users\scoti\PycharmProjects\ai-vpn-firewall-prototype\frontend
npm run dev
```

Open the URL shown (usually `http://localhost:5173`) in your browser.

---

## 10. Run the PCAP Streamer on Windows

All commands are run from the project root in PowerShell or CMD.

### Step 1 — Install dependencies (first time only)

```cmd
pip install -r tools/requirements_tools.txt
```

### Step 2 — Dry-run (no API calls, exports features to CSV only)

```cmd
cd C:\Users\scoti\PycharmProjects\ai-vpn-firewall-prototype
python tools/pcap_to_live_stream.py ^
  --pcap captures\vm_test.pcap ^
  --dry-run ^
  --out-csv captures\vm_test_features.csv ^
  --scenario vm_test
```

Inspect `captures\vm_test_features.csv` to verify flows were extracted correctly.

### Step 3 — Stream to the backend (live simulation)

```cmd
python tools/pcap_to_live_stream.py ^
  --pcap captures\vm_test.pcap ^
  --api http://127.0.0.1:8765 ^
  --batch-size 5 ^
  --delay-seconds 2 ^
  --scenario vm_test ^
  --out-csv captures\vm_test_features.csv
```

**CLI argument reference:**

| Argument | Default | Description |
|---|---|---|
| `--pcap` | *(required)* | Path to the `.pcap` file |
| `--api` | `http://127.0.0.1:8765` | Backend base URL |
| `--batch-size` | `5` | Number of flows per POST request |
| `--delay-seconds` | `2` | Wait time between batches (seconds) |
| `--scenario` | `vm_pcap` | Label prefix used in session IDs |
| `--dry-run` | off | Extract features only, skip API calls |
| `--out-csv` | *(optional)* | Save extracted features to CSV |
| `--min-packets` | `3` | Minimum packets required to keep a flow |

---

## 11. Watch the Frontend

1. Open `http://localhost:5173` in your browser.
2. Navigate to the **Live VM Monitor** page.
3. Batches should appear gradually as the streamer POSTs them.
4. Each session is labelled: `BENIGN_LIKE`, `FLAGGED_FOR_REVIEW`, or `VPN_LIKE_SIMULATED_BLOCK`.

> The frontend polls the backend every 2 seconds and updates the sessions table in real time.

---

## 12. Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: scapy` | Run `pip install -r tools/requirements_tools.txt` |
| Backend unreachable / `ConnectionRefusedError` | Verify uvicorn is running on `127.0.0.1:8765` (Section 8) |
| No valid flows extracted from PCAP | Capture longer, generate more traffic in the VM, or lower `--min-packets` |
| SCP fails / `Connection refused` | Verify SSH works first: `ssh scoti@127.0.0.1 -p 2222` |
| PCAP copied to wrong path | Check `captures\vm_test.pcap` exists with `dir captures\` |
| VM does not start | Check VirtualBox is installed and the VM name is exactly `"Ubunutu"` |
| SSH host key warning | Accept the fingerprint or clear `~/.ssh/known_hosts` for `[127.0.0.1]:2222` |
| Frontend shows no data | Confirm the backend is running and the streamer has posted at least one batch |

---

## 13. Safety Statement

> **This does not block packets. It only labels exported/captured flow features. All decisions are simulated.**

The streamer and backend operate entirely in user-space. No kernel modules, no iptables/nftables rules, and no VirtualBox network policies are modified at any point.

---

## 14. Limitation Statement

> **The lightweight PCAP feature extractor may not exactly match the original training pipeline, so VM PCAP labels are demonstration labels, not production validation.**

The robust9 model was trained on a specific CIC dataset pre-processing pipeline. The host-side scapy extractor is a best-effort approximation of the same 9 packet-size statistics. Differences in flow windowing, TCP reassembly, and sub-flow boundaries may cause label drift relative to a full-pipeline deployment.

---

## 15. Thesis Statement

> The VM PCAP streaming demo demonstrates an integration path from captured traffic to simulated firewall decisions. Traffic is captured inside an isolated Ubuntu Server VM using tcpdump, copied to the host, converted into robust9-compatible feature rows, and streamed to the FastAPI backend. The prototype labels sessions as BENIGN_LIKE, FLAGGED_FOR_REVIEW, or VPN_LIKE_SIMULATED_BLOCK, but it does not enforce packet blocking or claim production readiness.

---

## Quick-Start Cheat Sheet

```
[Windows CMD]  "C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" startvm "Ubunutu" --type headless
[Windows CMD]  ssh scoti@127.0.0.1 -p 2222

[VM SSH #1]    sudo tcpdump -i any -w vm_test.pcap          ← keep running
[VM SSH #2]    for i in {1..20}; do curl -L https://example.com > /dev/null 2>&1; sleep 1; done
[VM SSH #1]    Ctrl+C                                         ← stop capture

[Windows CMD]  scp -P 2222 scoti@127.0.0.1:~/vm_test.pcap captures\vm_test.pcap

[Windows PS]   cd backend  &&  python -m uvicorn main:app --host 127.0.0.1 --port 8765
[Windows PS]   cd frontend &&  npm run dev

[Windows PS]   python tools/pcap_to_live_stream.py --pcap captures\vm_test.pcap --dry-run --scenario vm_test
[Windows PS]   python tools/pcap_to_live_stream.py --pcap captures\vm_test.pcap --api http://127.0.0.1:8765 --batch-size 5 --delay-seconds 2 --scenario vm_test

[Browser]      http://localhost:5173  →  Live VM Monitor
```

---

*Last updated: 2026-05-27 | AI VPN Firewall Prototype — thesis demo only*

