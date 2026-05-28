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

## 🖱️ Running demos from the frontend

For the thesis demo you don't have to paste PowerShell commands every time.
The backend exposes a small allowlist API under `/demo/...` that the
frontend's **Demo Runner** page uses to start the same scripts you would
otherwise run manually.

### Workflow

1. Start the backend:
   ```cmd
   cd backend
   python -m uvicorn main:app --host 127.0.0.1 --port 8765
   ```
2. Start the frontend:
   ```cmd
   cd frontend
   npm run dev
   ```
3. Open <http://127.0.0.1:5173> and click **Demo Runner** in the navbar.
4. Click one of the four buttons:
   - **Basic Benign** &rarr; `tools\run_vm_pcap_demo.ps1 -TrafficProfile basic`
   - **VPN-like HTTPS** &rarr; `tools\run_vm_pcap_demo.ps1 -TrafficProfile vpnlike -CaptureSeconds 60`
   - **Cloudflare WARP** &rarr; `tools\run_vm_pcap_demo.ps1 -TrafficProfile warp -CaptureSeconds 60 -AllowWarpUnverified`
   - **Local OpenVPN Lab** &rarr; `tools\run_openvpn_lab_demo.ps1 -ServerVmName "VPNServer2" -SkipClientVmStart -SkipServerVmStart`
5. Watch the **Live log** panel for streaming stdout/stderr. The page polls
   `GET /demo/jobs/{job_id}` every 2 seconds while a job is running.
6. When the job reaches **succeeded**, click **Open Live VM &rarr;** to see
   the scenario in the **Live VM &rarr; PCAP Monitor** tab.

### What the backend will and will not do

- ✅ Launch one of the four allowlisted demos from `backend/demo_runner.py`.
- ✅ Stream captured stdout/stderr back to the browser, up to 2000 lines per job.
- ✅ Refuse a second concurrent job by default (set `?allow_concurrent=true`
  on the POST to override; not exposed in the UI on purpose).
- ✅ Let you cancel a running job (`POST /demo/jobs/{job_id}/cancel`).
- ❌ Accept arbitrary shell commands. The HTTP layer can only pick a
  **name** from `ALLOWED_DEMOS`; the script path and argument list are
  hard-coded.
- ❌ Modify firewall rules, run as root, or change backend prediction
  thresholds.

> ⚠️ **Local demo mode only.** The `/demo/...` endpoints execute local
> PowerShell scripts on the developer workstation. Do not expose this
> backend on a public network. CORS already restricts the frontend origin
> to `127.0.0.1`/`localhost` on ports 5173/5174.

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/demo/allowed`            | List allowlisted demo names + descriptions. |
| `POST` | `/demo/run/basic`          | Start the **basic** demo. |
| `POST` | `/demo/run/vpnlike`        | Start the **vpnlike** demo. |
| `POST` | `/demo/run/warp`           | Start the **warp** demo. |
| `POST` | `/demo/run/openvpnlab`     | Start the **openvpnlab** demo. |
| `GET`  | `/demo/jobs`               | List recent jobs (most recent first, no logs). |
| `GET`  | `/demo/jobs/{job_id}`      | Job status + captured logs (supports `?log_offset=`). |
| `POST` | `/demo/jobs/{job_id}/cancel` | SIGTERM the running script (with 5 s grace, then SIGKILL). |

---

## 🚀 One-command local demo

A PowerShell script automates the **entire** thesis demo workflow end-to-end:

```
Ubuntu Server VM generates traffic
  ↓
tcpdump captures PCAP inside the VM
  ↓
PCAP is copied to Windows with scp
  ↓
pcap_to_live_stream.py extracts robust9 features
  ↓
FastAPI /firewall/live-ingest receives batches
  ↓
Frontend Live VM Monitor displays simulated labels
```

### 🔑 Smooth demo setup: avoid repeated password prompts

The runner performs **two preflight checks** at startup and reports their status. If either is missing the demo still works, but you'll be asked for passwords many times. For a smooth thesis demo, configure both **once**.

#### 1. Configure SSH key login from Windows

Generate a key (press Enter for empty passphrase if you want full automation):

```powershell
ssh-keygen -t ed25519
```

Push the public key to the VM (asks for the SSH password **one last time**):

```powershell
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh -p 2222 scoti@127.0.0.1 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

Test passwordless login:

```powershell
ssh scoti@127.0.0.1 -p 2222
```

If you land in the Ubuntu shell without typing a password, you're done.

#### 2. Configure passwordless sudo **only** for `tcpdump` and `timeout`

Inside the Ubuntu VM, open a new sudoers drop-in file:

```bash
sudo visudo -f /etc/sudoers.d/tcpdump-demo
```

Add **exactly** this single line (and nothing else):

```
scoti ALL=(root) NOPASSWD: /usr/bin/tcpdump, /usr/bin/timeout
```

Save and exit. Then test:

```bash
sudo -n timeout 5 tcpdump -i any -w /tmp/test.pcap
ls -lh /tmp/test.pcap
rm /tmp/test.pcap
```

If no password is prompted and `/tmp/test.pcap` is non-empty, you're done.

#### 3. ⚠️ Security warning — do NOT use blanket NOPASSWD

**Do not** add this to sudoers:

```
scoti ALL=(ALL) NOPASSWD: ALL
```

That gives the user complete passwordless root, which is unnecessary and unsafe.  
The demo only needs **two specific binaries** (`tcpdump`, `timeout`). Restricting `NOPASSWD` to those binaries means a stolen account cannot use `sudo` for anything else (no `apt`, no `vim /etc/shadow`, no `su -`, etc.).

#### 4. Normal demo command after setup

Once both preflights pass, every run is fully unattended:

```powershell
powershell -ExecutionPolicy Bypass -File tools\run_vm_pcap_demo.ps1 -TrafficProfile vpnlike -CaptureSeconds 60
```

#### 5. If the script warns you

The runner prints clear warnings when either piece of setup is missing — just follow the on-screen instructions, which match Sections 1 and 2 above.

---

### Current local setup the script targets

| Setting | Value |
|---|---|
| Host OS | Windows |
| VM platform | Oracle VirtualBox |
| VM registered name | `Ubunutu` |
| Guest OS | Ubuntu Server |
| Network mode | NAT |
| SSH port forwarding | `127.0.0.1:2222` → VM port `22` |
| SSH user | `scoti` |
| Backend | `http://127.0.0.1:8765` |
| Frontend | `http://127.0.0.1:5173` |
| State endpoint | `GET /firewall/live-ingest/state` |
| Reset endpoint | `POST /firewall/live-ingest/reset` |

### Usage

**Normal run** (start VM → capture → copy → reset → stream → verify):
```powershell
powershell -ExecutionPolicy Bypass -File tools\run_vm_pcap_demo.ps1
```

**Dry run** (extract features to CSV, no API calls — useful for testing without the backend):
```powershell
powershell -ExecutionPolicy Bypass -File tools\run_vm_pcap_demo.ps1 -DryRun
```

**Longer capture** (60-second tcpdump window inside the VM):
```powershell
powershell -ExecutionPolicy Bypass -File tools\run_vm_pcap_demo.ps1 -CaptureSeconds 60
```

**Skip VM start** (VM is already running):
```powershell
powershell -ExecutionPolicy Bypass -File tools\run_vm_pcap_demo.ps1 -SkipVmStart
```

**Skip backend reset** (keep accumulating in the existing ingest state):
```powershell
powershell -ExecutionPolicy Bypass -File tools\run_vm_pcap_demo.ps1 -SkipBackendReset
```

**Auto-install tcpdump inside the VM** if missing (asks for the VM sudo password once):
```powershell
powershell -ExecutionPolicy Bypass -File tools\run_vm_pcap_demo.ps1 -InstallTcpdump
```

### What the script does — step by step

| Step | Action |
|---|---|
| **[1/8]** | Starts VM via `VBoxManage startvm "Ubunutu" --type headless` (unless `-SkipVmStart`) |
| **[2/8]** | Polls SSH on `127.0.0.1:2222` for up to 60 s |
| **[3/8]** | Launches `sudo -n /usr/bin/timeout N /usr/bin/tcpdump -i any -w /home/scoti/<scenario>.pcap` as a background SSH job (passwordless sudo required) |
| **[4/8]** | Generates traffic inside the VM according to `-TrafficProfile` (`basic` / `mixed` / `vpnlike` / `realvpn`). Use `-RunAllProfiles` to sweep `basic → mixed → vpnlike` automatically. |
| **[5/8]** | Verifies the remote PCAP with `test -s`, then `scp -P 2222` to `captures\<scenario>.pcap` |
| **[6/8]** | `POST /firewall/live-ingest/reset` (unless `-SkipBackendReset` or `-DryRun`) |
| **[7/8]** | Runs `python tools\pcap_to_live_stream.py` with the captured PCAP |
| **[8/8]** | Fetches `/firewall/live-ingest/state` and prints summary + frontend links |

### Prerequisites

| Requirement | How to verify / install |
|---|---|
| VirtualBox installed | `"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe" --version` |
| VM named `Ubunutu` exists | `VBoxManage.exe list vms` |
| Ubuntu Server installed in the VM | (one-time guest OS install) |
| SSH works | `ssh scoti@127.0.0.1 -p 2222` |
| tcpdump inside the VM | `ssh scoti@127.0.0.1 -p 2222 "command -v tcpdump"` — or pass `-InstallTcpdump` |
| Backend running | `cd backend ; python -m uvicorn main:app --host 127.0.0.1 --port 8765` |
| Frontend running | `cd frontend ; npm run dev` |

### Expected verification

After a successful run the script prints a green summary card:

```
+-------------------------------------------------------+
|  Backend ingest state                                 |
+-------------------------------------------------------+
|  model_id       : robust9_firewall                    |
|  action_mode    : simulation                          |
|  total_batches  : > 0                                 |
|  total_flows    : > 0                                 |
|  total_sessions : > 0                                 |
|  BENIGN_LIKE    : > 0                                 |
+-------------------------------------------------------+
```

Then open `http://127.0.0.1:5173` → **Live VM Monitor** and confirm the same values.

### Troubleshooting

| Problem | Fix |
|---|---|
| SSH fails to connect | Confirm VM is running (`VBoxManage list runningvms`); confirm NAT forwarding exists (`127.0.0.1:2222 → 22`); clear stale host key with `ssh-keygen -R "[127.0.0.1]:2222"` |
| `tcpdump: command not found` inside the VM | SSH in and run `sudo apt update && sudo apt install tcpdump -y` — or re-run the script with `-InstallTcpdump` |
| Backend reset returns "connection refused" | Start the backend: `cd backend ; python -m uvicorn main:app --host 127.0.0.1 --port 8765` |
| Frontend does not show results | Check raw state at `http://127.0.0.1:8765/firewall/live-ingest/state`; ensure the **Live VM Monitor** page polls `/firewall/live-ingest/state` (**not** `/firewall/live-replay/state`) |
| Script prompts for the VM password many times | Set up SSH key auth — see Section 🔑 "Smooth demo setup" above (`ssh-keygen -t ed25519`, copy public key to VM `~/.ssh/authorized_keys`) |
| `sudo` keeps asking for the password | Configure a **scoped** sudoers entry inside the VM: `sudo visudo -f /etc/sudoers.d/tcpdump-demo` then add exactly `scoti ALL=(root) NOPASSWD: /usr/bin/tcpdump, /usr/bin/timeout`. Do **not** use `NOPASSWD: ALL`. |

### Safety statement

> **This script is for local thesis / demo automation only. It does not block packets and does not modify firewall rules. It only captures traffic inside the local VM, exports PCAP-derived features, and sends them to the backend for simulation-only labelling.**

The script never touches iptables, nftables, Windows Firewall, routing tables, or any OS-level packet-filtering mechanism. The FastAPI backend itself does not sniff traffic.

### Deployment limitation

> **This does not make the deployed website capable of capturing traffic from other users.** A deployed browser app cannot access a user's VirtualBox VM, run `tcpdump`, or read local PCAP files without a local helper / agent. The demo is therefore **local-only** and demonstrates an *integration path* from captured traffic to simulated labels, not a production capture pipeline.

---

## 🎛️ Traffic profiles

The runner can generate three different traffic profiles inside the VM. Pick one via `-TrafficProfile`:

| Profile | What it generates | Use it for |
|---|---|---|
| `benign` *(default)* | Ordinary harmless DNS / HTTPS / ICMP traffic (`example.com`, `wikipedia.org`, `ping 8.8.8.8`) | Baseline scenario — should be labelled BENIGN_LIKE by `robust9_firewall` |
| `vpnlike` | High-volume **encrypted HTTPS** traffic (30 rounds of curls + optional 10 MB download). **NOT a real VPN tunnel.** | Encrypted / VPN-like traffic scenario — packet-size statistics resemble VPN flows |
| `warp`    | Real **Cloudflare WARP** encrypted tunnel: connect WARP → traffic → disconnect WARP. Free real tunnel — not Proton/Mullvad. | Free real encrypted tunnel scenario for thesis demo when paid VPN providers are unavailable |
| `realvpn` | Real WireGuard or OpenVPN tunnel: bring tunnel UP → traffic → tunnel DOWN | Only when a working VPN is already configured inside the VM |

### Per-profile defaults

When you select a profile, the runner picks sensible defaults so each capture goes to its own file:

| Profile | Scenario (session-id prefix) | Remote PCAP | Local PCAP |
|---|---|---|---|
| `benign`  | `vm_benign`  | `~/vm_benign.pcap`  | `captures\vm_benign.pcap`  |
| `vpnlike` | `vm_vpnlike`      | `~/vm_vpnlike.pcap`      | `captures\vm_vpnlike.pcap`      |
| `warp`    | `vm_warp`         | `~/vm_warp.pcap`         | `captures\vm_warp.pcap`         |
| `realvpn` | `vm_realvpn`      | `~/vm_realvpn.pcap`      | `captures\vm_realvpn.pcap`      |

You can override any of these with `-Scenario`, `-RemotePcap`, or `-LocalPcap` if needed.

### Examples

**Benign traffic** (default — same as not passing `-TrafficProfile`):
```powershell
powershell -ExecutionPolicy Bypass -File tools\run_vm_pcap_demo.ps1 -TrafficProfile benign
```

**VPN-like encrypted traffic** (longer window recommended — ~60 s):
```powershell
powershell -ExecutionPolicy Bypass -File tools\run_vm_pcap_demo.ps1 -TrafficProfile vpnlike -CaptureSeconds 60
```

**Cloudflare WARP encrypted tunnel** (free real tunnel — requires `warp-cli` already installed and registered inside the VM):
```powershell
powershell -ExecutionPolicy Bypass -File tools\run_vm_pcap_demo.ps1 -TrafficProfile warp -CaptureSeconds 60
```

Cloudflare WARP is used as the **free real encrypted tunnel** traffic scenario when paid VPN providers (Proton, Mullvad, NordVPN, etc.) are unavailable. The script will:

1. Verify `warp-cli` exists inside the VM (fails clearly with install instructions if missing).
2. Run `warp-cli status`, then `warp-cli connect`.
3. Poll `warp-cli status` for up to **45 seconds** until it reports `Connected`.
4. Verify the tunnel via `curl -4 https://www.cloudflare.com/cdn-cgi/trace` and check for `warp=on`.
5. Generate ~20 rounds of HTTPS curls plus an optional 10 MB download through the tunnel.
6. Always run `warp-cli disconnect` at the end (also on failure, via a bash `trap`).

One-time setup inside the Ubuntu VM:
```bash
curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg \
  | sudo gpg --yes --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/cloudflare-client.list
sudo apt update && sudo apt install -y cloudflare-warp
warp-cli registration new
warp-cli connect    # confirm it works once interactively
warp-cli disconnect
```

> ⚠️ Thesis-wording note: label this scenario as **"Cloudflare WARP encrypted tunnel traffic"**, **not** as "Proton VPN" / "Mullvad" / "commercial VPN". WARP is a free Cloudflare-operated tunnel — it is a real encrypted tunnel for our purposes, but it is not the same product class as commercial VPN providers.

**Real WireGuard VPN traffic** (requires `myvpn.conf` already installed under `/etc/wireguard/` inside the VM):
```powershell
powershell -ExecutionPolicy Bypass -File tools\run_vm_pcap_demo.ps1 `
    -TrafficProfile realvpn `
    -VpnType wireguard `
    -VpnProfile myvpn `
    -CaptureSeconds 60
```

**Real OpenVPN traffic** (requires a **non-interactive** `.ovpn` profile already installed inside the VM):
```powershell
powershell -ExecutionPolicy Bypass -File tools\run_vm_pcap_demo.ps1 `
    -TrafficProfile realvpn `
    -VpnType openvpn `
    -VpnProfile /etc/openvpn/client/myvpn.ovpn `
    -CaptureSeconds 60
```

**Dry-run any profile** (no API calls — useful when the backend isn't running):
```powershell
powershell -ExecutionPolicy Bypass -File tools\run_vm_pcap_demo.ps1 -TrafficProfile vpnlike -CaptureSeconds 60 -DryRun
```

### How real VPN mode works

For `realvpn`, the script runs an **SSH session that wraps tunnel up → traffic → tunnel down in a single block**. If anything fails the script attempts an automatic safety teardown:

- **WireGuard:** `sudo wg-quick up <profile>` → `sudo wg show` (peer info only — no keys printed) → `curl ifconfig.me` → 20 rounds of HTTPS curls → optional 10 MB download → `sudo wg-quick down <profile>`.
- **OpenVPN:** `sudo openvpn --config <profile> --daemon --writepid /tmp/demo_openvpn.pid` → 10 s wait → traffic → `sudo kill $(cat /tmp/demo_openvpn.pid)`.

If the OpenVPN profile contains a bare `auth-user-pass` directive (without an inline credentials file), the script aborts with:

> *OpenVPN profile requires interactive credentials. Configure a non-interactive lab profile inside the VM or use WireGuard for this demo.*

The runner **never** creates VPN configs, downloads provider files, or stores credentials. You must set up your VPN profile inside the VM yourself before using `-TrafficProfile realvpn`.

### Important thesis wording

> ⚠️ **Do not claim `vpnlike` is real VPN traffic.** In thesis writing, call it the **"encrypted / VPN-like traffic scenario"**. Only call it **real VPN traffic** when a real VPN client is actually connected inside the VM (i.e., when `-TrafficProfile realvpn` succeeds end-to-end).

This honest framing matters because `robust9_firewall` was trained on flow-level packet-size statistics; ordinary high-volume HTTPS traffic can resemble VPN traffic statistically, but that does not make it a real VPN tunnel.

---

## 🧪 Local OpenVPN lab demo

For the thesis demo we also ship a dedicated end-to-end runner that orchestrates a **two-VM local OpenVPN lab** instead of a single VM with public HTTPS:

```powershell
powershell -ExecutionPolicy Bypass -File tools\run_openvpn_lab_demo.ps1
```

This profile creates traffic through a **local OpenVPN tunnel between two VirtualBox VMs** on the host. It is **real OpenVPN traffic**, captured with `tcpdump` inside the client VM and then streamed to the existing backend and frontend. It is **not** an external paid VPN provider.

| VM | Default name | SSH | Role |
|----|--------------|-----|------|
| Client | `Ubunutu` | `127.0.0.1:2222` | OpenVPN client (`~/client1.ovpn`), tcpdump, traffic generator |
| Server | `VPNServer` | `127.0.0.1:2223` | OpenVPN server (`openvpn@server`), `python3 -m http.server` on `10.8.0.1:8000` |

### Skip flags

| Switch | Effect |
|--------|--------|
| `-SkipVmStart` | Skip `VBoxManage startvm` for **both** VMs. |
| `-SkipClientVmStart` | Skip `VBoxManage startvm` for the **client** VM only. |
| `-SkipServerVmStart` | Skip `VBoxManage startvm` for the **server** VM only. |
| `-SkipBackendReset` | Do not `POST /firewall/live-ingest/reset` before streaming. |
| `-DryRun` | Extract features to CSV but skip backend POSTs. |

### VBoxManage path

Both demo scripts auto-resolve `VBoxManage.exe`:

1. They first try the default install path `C:\Program Files\Oracle\VirtualBox\VBoxManage.exe`.
2. Then they fall back to whatever is on `PATH` (via `Get-Command VBoxManage`).
3. If still not found, VM auto-start is **skipped** with a warning instead of failing — the script continues as long as SSH to the VM is already reachable.

If VirtualBox is installed in a non-default location, pass:

```powershell
-VBoxManagePath "D:\Path\To\VBoxManage.exe"
```

to either `run_vm_pcap_demo.ps1` or `run_openvpn_lab_demo.ps1`. This is also the recommended fix when launching the scripts from the frontend Demo Runner under a session whose `PATH` does not include the VirtualBox install directory.

### Example: both VMs are already running, custom server VM name

```powershell
powershell -ExecutionPolicy Bypass -File tools\run_openvpn_lab_demo.ps1 -ServerVmName "VPNServer2" -SkipClientVmStart -SkipServerVmStart
```

### Other parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `-ClientVmName` / `-ServerVmName` | `Ubunutu` / `VPNServer` | VirtualBox VM names. |
| `-ClientSshPort` / `-ServerSshPort` | `2222` / `2223` | Host-side SSH ports. |
| `-SshUser` | `scoti` | SSH user inside both VMs. |
| `-CaptureSeconds` | `90` | tcpdump duration on the client VM. |
| `-ApiBase` | `http://127.0.0.1:8765` | FastAPI backend URL. |
| `-BatchSize` / `-DelaySeconds` | `1` / `1` | Streamer batch size and inter-batch delay. |
| `-MaxPcapMB` | `150` | Above this, a 100k-packet sample is taken (`tcpdump -r ... -w ... -c 100000`) and copied instead. |
| `-Scenario` | `vm_openvpn_lab_auto` | Scenario label sent to the backend. |
| `-ClientOvpnConfig` | `/home/scoti/client1.ovpn` | OpenVPN client config path inside the client VM. |
| `-TunnelServerIp` / `-HttpPort` | `10.8.0.1` / `8000` | OpenVPN server tunnel IP and HTTP file-server port. |

### One-time sudoers setup inside the client VM

```bash
sudo visudo -f /etc/sudoers.d/openvpn-lab-demo
# add:
scoti ALL=(root) NOPASSWD: /usr/bin/tcpdump, /usr/bin/timeout, /usr/bin/openvpn, /bin/kill, /usr/bin/pkill
```

### Thesis wording

> The local OpenVPN lab demo captures **real OpenVPN tunnel traffic between two VirtualBox VMs on the host**. It is **not** an external paid VPN provider (ProtonVPN, Mullvad, NordVPN, etc. are not contacted). Label it in writing as *"local OpenVPN lab traffic captured inside VM"*. Backend behavior is unchanged: all decisions remain **simulation-only**, no firewall rules are modified, and no real packets are blocked.

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

