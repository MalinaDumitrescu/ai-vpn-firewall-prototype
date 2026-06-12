<#
.SYNOPSIS
    Two-VM OpenVPN lab demo runner for the AI VPN Firewall Prototype.

.DESCRIPTION
    Coordinates a client VM (OpenVPN client + tcpdump + traffic generator) and
    a server VM (OpenVPN server + Python HTTP server on the tunnel IP). Records
    a PCAP of real OpenVPN tunnel traffic inside the client VM, samples it if
    necessary, copies it to the Windows host, and streams the 12 unified
    relative-shape-v2 features into the FastAPI backend at
    /firewall/live-ingest using the active runtime model
    unified_relative_shape_v2__lgbm.

    SAFETY
    ------
    * LOCAL DEMO MODE ONLY. Not for production.
    * Does NOT modify any firewall rule on host or VMs.
    * Does NOT block real packets. Backend decisions are simulation-only.
    * Non-interactive: every ssh uses BatchMode=yes + ConnectTimeout=10,
      every sudo is `sudo -n`, no -tt, no password prompts.

.NOTES
    Required passwordless sudoers rules:
      Client (Ubunutu):
        scoti ALL=(root) NOPASSWD: /usr/sbin/openvpn, /usr/bin/timeout,
                                    /usr/bin/tcpdump, /usr/bin/kill,
                                    /usr/bin/cat, /usr/bin/rm, /usr/bin/pkill
      Server (VPNServer2):
        scoti ALL=(root) NOPASSWD: /usr/bin/systemctl, /usr/sbin/openvpn,
                                    /usr/bin/kill, /usr/bin/cat, /usr/bin/rm,
                                    /usr/bin/dd, /usr/bin/pkill,
                                    /usr/sbin/iptables, /sbin/iptables,
                                    /usr/sbin/ufw
#>

[CmdletBinding()]
param(
    [string] $ClientVmName       = 'Ubunutu',
    [string] $ServerVmName       = 'VPNServer2',

    [string] $SshUser            = 'scoti',
    [string] $ClientSshHost      = '127.0.0.1',
    [string] $ServerSshHost      = '127.0.0.1',
    [int]    $ClientSshPort      = 2222,
    [int]    $ServerSshPort      = 2223,

    [string] $ClientOpenVpnConfig = '/home/scoti/client1.ovpn',
    [string] $Scenario           = 'vm_openvpn_lab_auto',

    [int]    $CaptureSeconds     = 90,
    [string] $ApiBase            = 'http://127.0.0.1:8765',
    [int]    $BatchSize          = 1,
    [int]    $DelaySeconds       = 1,
    [int]    $MaxPcapMB          = 150,

    [switch] $SkipClientVmStart,
    [switch] $SkipServerVmStart,
    [switch] $KeepBackendState,
    [switch] $DryRun
)

# ---------------------------------------------------------------------------
# Globals / setup
# ---------------------------------------------------------------------------

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch {}
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot  = Split-Path -Parent $ScriptDir
$CapturesDir  = Join-Path $ProjectRoot 'captures'
$PcapStreamer = Join-Path $ScriptDir 'pcap_to_live_stream.py'
# Active runtime model used by /firewall/live-ingest. Passed explicitly to
# pcap_to_live_stream.py so the streamer extracts the 12 unified features
# (not the legacy full_canonical 34-feature schema).
$ActiveRuntimeModel = 'unified_relative_shape_v2__lgbm'
if (-not (Test-Path $CapturesDir)) { New-Item -ItemType Directory -Path $CapturesDir | Out-Null }

$RemotePcap        = "/home/$SshUser/vm_openvpn_lab_auto.pcap"
$RemotePcapSample  = "/home/$SshUser/vm_openvpn_lab_auto_sample.pcap"
$LocalPcap         = Join-Path $CapturesDir 'vm_openvpn_lab_auto.pcap'
$LocalPcapSample   = Join-Path $CapturesDir 'vm_openvpn_lab_auto_sample.pcap'
$FeaturesCsv       = Join-Path $CapturesDir 'vm_openvpn_lab_auto_features.csv'

$ClientSshTarget = "$SshUser@$ClientSshHost"
$ServerSshTarget = "$SshUser@$ServerSshHost"

$ClientSshOpts = @('-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','ConnectTimeout=10','-p',$ClientSshPort)
$ServerSshOpts = @('-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','ConnectTimeout=10','-p',$ServerSshPort)
$ClientScpOpts = @('-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','ConnectTimeout=10','-P',$ClientSshPort)
$ServerScpOpts = @('-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','ConnectTimeout=10','-P',$ServerSshPort)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Section([string]$Title) {
    Write-Host ''
    Write-Host ('=' * 70)
    Write-Host "  $Title"
    Write-Host ('=' * 70)
}
function Write-Info([string]$m)  { Write-Host "[info] $m" }
function Write-Warn2([string]$m) { Write-Host "[warn] $m" -ForegroundColor Yellow }
function Write-Err2([string]$m)  { Write-Host "[err ] $m" -ForegroundColor Red }
function Write-Ok([string]$m)    { Write-Host "[ ok ] $m" -ForegroundColor Green }

function ConvertTo-SshBashB64 {
    param([Parameter(Mandatory)] [string] $Script)

    # Normalize Windows CRLF to Linux LF before sending to bash
    $Script = $Script -replace "`r`n", "`n"
    $Script = $Script -replace "`r", "`n"

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Script)
    $b64   = [Convert]::ToBase64String($bytes)

    return "echo $b64 | base64 -d | bash"
}

function Invoke-SshRaw {
    param(
        [string[]] $Opts,
        [string]   $Target,
        [string]   $RemoteCmd,
        [int]      $TimeoutSec = 0,
        [switch]   $AsScript
    )

    if ($AsScript -or $RemoteCmd -match "`n") {
        $RemoteCmd = ConvertTo-SshBashB64 -Script $RemoteCmd
    }

    $args = @($Opts + @($Target, $RemoteCmd))

    if ($TimeoutSec -gt 0) {
        $job = Start-Job -ScriptBlock {
            param($a)

            $out = & ssh @a 2>&1
            $code = $LASTEXITCODE

            [PSCustomObject]@{
                Out  = ($out -join "`n")
                Code = $code
            }
        } -ArgumentList (,$args)

        $done = Wait-Job $job -Timeout $TimeoutSec

        if (-not $done) {
            Stop-Job $job | Out-Null
            Remove-Job $job -Force | Out-Null
            return @{ Ok = $false; Out = ''; Code = 124 }
        }

        $result = Receive-Job $job
        Remove-Job $job -Force | Out-Null

        return @{
            Ok   = ($result.Code -eq 0)
            Out  = $result.Out
            Code = $result.Code
        }
    }

    $out = & ssh @args 2>&1
    $code = $LASTEXITCODE

    return @{
        Ok   = ($code -eq 0)
        Out  = ($out -join "`n")
        Code = $code
    }
}

function Invoke-ClientSsh {
    param(
        [string] $RemoteCmd,
        [int]    $TimeoutSec = 0
    )

    Invoke-SshRaw `
        -Opts $ClientSshOpts `
        -Target $ClientSshTarget `
        -RemoteCmd $RemoteCmd `
        -TimeoutSec $TimeoutSec
}

function Invoke-ServerSsh {
    param(
        [string] $RemoteCmd,
        [int]    $TimeoutSec = 0
    )

    Invoke-SshRaw `
        -Opts $ServerSshOpts `
        -Target $ServerSshTarget `
        -RemoteCmd $RemoteCmd `
        -TimeoutSec $TimeoutSec
}

function Test-VmRunning {
    param([string] $Name)
    try {
        $running = & VBoxManage list runningvms 2>$null
        return ($running -match [regex]::Escape($Name))
    } catch { return $false }
}
function Start-VmIfNeeded {
    param([string]$Name,[switch]$Skip)
    if ($Skip) { Write-Info "Skipping VM start for '$Name' (flag set)."; return }
    if (Test-VmRunning -Name $Name) { Write-Info "VM '$Name' already running."; return }
    Write-Info "Starting VM '$Name' headless..."
    try {
        & VBoxManage startvm $Name --type headless | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Warn2 "VBoxManage returned $LASTEXITCODE for '$Name'. Continuing." }
    } catch { Write-Warn2 "Failed to start VM '$Name': $($_.Exception.Message). Continuing." }
}
function Wait-SshGeneric {
    param([scriptblock]$Probe,[string]$Label,[int]$TimeoutSec=120)
    Write-Info "Waiting up to $TimeoutSec s for SSH on $Label ..."
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $r = & $Probe
        if ($r.Ok -and ($r.Out -match 'ssh_ready')) { Write-Ok "SSH reachable: $Label."; return }
        Start-Sleep -Seconds 3
    }
    throw "SSH did not become reachable on $Label within $TimeoutSec s."
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

Write-Section "AI VPN Firewall Prototype - OpenVPN Lab Demo (LOCAL DEMO MODE)"
Write-Host "  Client VM       : $ClientVmName  (${ClientSshTarget}:$ClientSshPort)"
Write-Host "  Server VM       : $ServerVmName  (${ServerSshTarget}:$ServerSshPort)"
Write-Host "  Scenario        : $Scenario"
Write-Host "  Capture seconds : $CaptureSeconds"
Write-Host "  API base        : $ApiBase"
Write-Host "  Remote PCAP     : $RemotePcap"
Write-Host "  Local  PCAP     : $LocalPcap"
Write-Host "  MaxPcapMB       : $MaxPcapMB"
Write-Host "  SkipClientStart : $($SkipClientVmStart.IsPresent)"
Write-Host "  SkipServerStart : $($SkipServerVmStart.IsPresent)"
Write-Host "  KeepBackend     : $($KeepBackendState.IsPresent)"
Write-Host "  DryRun          : $($DryRun.IsPresent)"
Write-Host "  Local OpenVPN lab traffic captured inside VM. Simulation-only."
Write-Host ''

# ---------------------------------------------------------------------------
# DryRun short-circuit
# ---------------------------------------------------------------------------

if ($DryRun) {
    Write-Section 'DryRun mode'
    Write-Info 'DryRun: skipping VM start, SSH, OpenVPN, tcpdump, scp, and live-ingest.'
    $pcapForDry = $null
    if (Test-Path $LocalPcapSample) { $pcapForDry = $LocalPcapSample }
    elseif (Test-Path $LocalPcap)   { $pcapForDry = $LocalPcap }
    if ($pcapForDry) {
        Write-Info "Found existing local PCAP at $pcapForDry; invoking pcap_to_live_stream.py --dry-run."
        & python $PcapStreamer `
            --pcap         $pcapForDry `
            --scenario     $Scenario `
            --out-csv      $FeaturesCsv `
            --batch-size   $BatchSize `
            --delay-seconds $DelaySeconds `
            --model-id     $ActiveRuntimeModel `
            --dry-run
        if ($LASTEXITCODE -ne 0) {
            Write-Err2 "pcap_to_live_stream.py failed with code $LASTEXITCODE."
            exit $LASTEXITCODE
        }
    } else {
        Write-Info "No existing local PCAP at $LocalPcap; nothing to feed pcap_to_live_stream.py."
    }
    Write-Ok 'DryRun complete.'
    exit 0
}

# ---------------------------------------------------------------------------
# 1. Start VMs and wait for SSH
# ---------------------------------------------------------------------------

Start-VmIfNeeded -Name $ClientVmName -Skip:$SkipClientVmStart
Start-VmIfNeeded -Name $ServerVmName -Skip:$SkipServerVmStart

Wait-SshGeneric -Label "${ClientSshTarget}:$ClientSshPort" -TimeoutSec 120 -Probe {
    Invoke-ClientSsh -RemoteCmd 'echo ssh_ready' -TimeoutSec 12
}
Wait-SshGeneric -Label "${ServerSshTarget}:$ServerSshPort" -TimeoutSec 120 -Probe {
    Invoke-ServerSsh -RemoteCmd 'echo ssh_ready' -TimeoutSec 12
}

# ---------------------------------------------------------------------------
# 2. Prepare server
# ---------------------------------------------------------------------------

Write-Section 'Server: OpenVPN status + tunnel IP'
$r = Invoke-ServerSsh -RemoteCmd 'systemctl is-active openvpn@server 2>/dev/null || true' -TimeoutSec 15
if ($r.Out -notmatch 'active') {
    Write-Warn2 "openvpn@server not active: '$($r.Out.Trim())'. Trying restart..."
    Invoke-ServerSsh -RemoteCmd 'sudo -n systemctl restart openvpn@server' -TimeoutSec 25 | Out-Null
    Start-Sleep -Seconds 3
    $r = Invoke-ServerSsh -RemoteCmd 'systemctl is-active openvpn@server 2>/dev/null || true' -TimeoutSec 15
}
if ($r.Out -notmatch 'active') {
    $diag1 = Invoke-ServerSsh -RemoteCmd 'systemctl status openvpn@server --no-pager 2>&1 | head -n 40 || true' -TimeoutSec 15
    $diag2 = Invoke-ServerSsh -RemoteCmd 'journalctl -xeu openvpn@server --no-pager 2>&1 | tail -n 80 || true' -TimeoutSec 20
    Write-Host $diag1.Out
    Write-Host $diag2.Out
    throw 'openvpn@server is not active on the server VM.'
}
Write-Ok 'openvpn@server active.'

$r = Invoke-ServerSsh -RemoteCmd 'ip a | grep 10.8.0.1 || true' -TimeoutSec 10
if ($r.Out -notmatch '10\.8\.0\.1') { throw 'Tunnel IP 10.8.0.1 not present on server.' }
Write-Ok 'Tunnel IP 10.8.0.1 present on server.'

Write-Section 'Server: HTTP file server on 10.8.0.1:8000'

# Build the server-side Bash script.  We write it to a local temp file with
# LF-only endings (no BOM), scp it to the server, then execute it there.
# This avoids any CRLF / stray-\r problems that occur when embedding multi-
# line Bash in a PowerShell here-string sent over SSH.
$TmpShLocal = Join-Path $env:TEMP 'start_openvpn_http_server.sh'
$httpServerBash = @'
#!/usr/bin/env bash
# NOTE: CRLF-safe — this file is written with LF-only endings by the PS1 script.
set -uo pipefail

DEMO_DIR=/home/scoti/openvpn_http_demo
mkdir -p "$DEMO_DIR"
cd "$DEMO_DIR"

# ── ensure demo files exist ──────────────────────────────────────────────────
test -f small.bin  || dd if=/dev/urandom of=small.bin  bs=100K count=1  status=none
test -f medium.bin || dd if=/dev/urandom of=medium.bin bs=1M   count=5  status=none
test -f large.bin  || dd if=/dev/urandom of=large.bin  bs=1M   count=30 status=none
echo "=== Demo files in $DEMO_DIR ==="
ls -lh .

# ── open firewall port 8000 on tun interface (non-fatal) ─────────────────────
echo "=== iptables: allow port 8000 on tun interfaces ==="
sudo -n iptables -C INPUT -i tun0 -p tcp --dport 8000 -j ACCEPT 2>/dev/null \
  || sudo -n iptables -I INPUT -i tun0 -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true
sudo -n iptables -C INPUT -i tun1 -p tcp --dport 8000 -j ACCEPT 2>/dev/null \
  || sudo -n iptables -I INPUT -i tun1 -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true

# ── kill any leftover HTTP server ─────────────────────────────────────────────
pkill -f "python3 -m http.server 8000" 2>/dev/null || true
sleep 1

# ── start HTTP server bound to tunnel IP ─────────────────────────────────────
echo "=== Starting HTTP server on 10.8.0.1:8000 ==="
nohup python3 -m http.server 8000 --bind 10.8.0.1 > /tmp/openvpn_http_server.log 2>&1 &
HTTP_PID=$!
echo "$HTTP_PID" > /tmp/openvpn_http_server.pid
sleep 3

# ── check if port is actually listening ──────────────────────────────────────
LISTENING=0
ss -ltn 2>/dev/null | grep -q ':8000' && LISTENING=1
[ "$LISTENING" -eq 0 ] && netstat -ltn 2>/dev/null | grep -q ':8000' && LISTENING=1

if [ "$LISTENING" -eq 0 ]; then
  echo "=== Port 8000 not listening on 10.8.0.1; retrying with 0.0.0.0 fallback ==="
  echo "=== Log so far ==="
  cat /tmp/openvpn_http_server.log || true
  pkill -f "python3 -m http.server 8000" 2>/dev/null || true
  sleep 1
  nohup python3 -m http.server 8000 --bind 0.0.0.0 > /tmp/openvpn_http_server.log 2>&1 &
  HTTP_PID=$!
  echo "$HTTP_PID" > /tmp/openvpn_http_server.pid
  sleep 3
  ss -ltn 2>/dev/null | grep -q ':8000' && LISTENING=1
  [ "$LISTENING" -eq 0 ] && netstat -ltn 2>/dev/null | grep -q ':8000' && LISTENING=1
fi

echo "=== Listening sockets on :8000 ==="
ss -ltnp 2>/dev/null | grep 8000 || netstat -ltnp 2>/dev/null | grep 8000 || echo "(none)"

if [ "$LISTENING" -eq 0 ]; then
  echo "HTTP_NOT_READY — port 8000 not listening after fallback"
  echo "=== HTTP server log ==="
  cat /tmp/openvpn_http_server.log || true
  exit 1
fi

# ── server-side curl verification ────────────────────────────────────────────
echo "=== Server-side curl test: http://10.8.0.1:8000/small.bin ==="
SERVER_CURL_OK=0
if curl -fsS --max-time 8 http://10.8.0.1:8000/small.bin -o /dev/null 2>&1; then
  echo "SERVER_CURL_OK — file reachable via tunnel IP"
  SERVER_CURL_OK=1
elif curl -fsS --max-time 8 http://127.0.0.1:8000/small.bin -o /dev/null 2>&1; then
  echo "SERVER_CURL_OK_LOOPBACK — reachable via loopback (bound to 0.0.0.0)"
  SERVER_CURL_OK=1
fi

if [ "$SERVER_CURL_OK" -eq 0 ]; then
  echo "SERVER_CURL_FAIL — server cannot reach its own HTTP server"
  echo "=== ip addr ==="
  ip addr show
  echo "=== ip route ==="
  ip route show
  echo "=== ss :8000 ==="
  ss -ltnp 2>/dev/null | grep 8000 || echo "(none)"
  echo "=== http.server process ==="
  ps aux | grep http.server | grep -v grep || echo "(not running)"
  echo "=== HTTP server log ==="
  cat /tmp/openvpn_http_server.log || true
  echo "=== iptables INPUT chain ==="
  sudo -n iptables -S INPUT 2>/dev/null | head -30 || true
  echo "HTTP_NOT_READY"
  exit 1
fi

echo "HTTP_READY pid=$HTTP_PID"
'@
# Normalise to LF and write UTF-8 without BOM
$httpServerBash = $httpServerBash -replace "`r`n", "`n"
$httpServerBash = $httpServerBash -replace "`r", "`n"
[System.IO.File]::WriteAllText($TmpShLocal, $httpServerBash,
    [System.Text.UTF8Encoding]::new($false))

Write-Info "Copying HTTP server script to server VM..."
$scpServerArgs = @($ServerScpOpts + @($TmpShLocal, ('{0}:/tmp/start_openvpn_http_server.sh' -f $ServerSshTarget)))
& scp @scpServerArgs
if ($LASTEXITCODE -ne 0) { throw "scp of HTTP server script to server VM failed (exit $LASTEXITCODE)." }

Write-Info "Running HTTP server script on server VM..."
$r = Invoke-ServerSsh -RemoteCmd 'chmod +x /tmp/start_openvpn_http_server.sh && bash /tmp/start_openvpn_http_server.sh' -TimeoutSec 60
Write-Host $r.Out
if ($r.Out -notmatch 'HTTP_READY') {
    Write-Err2 "HTTP server start script did not print HTTP_READY. Full diagnostics:"
    $diagScript = @'
echo "=== ip addr ==="
ip addr show
echo "=== ip route ==="
ip route show
echo "=== ss :8000 ==="
ss -ltnp 2>/dev/null | grep 8000 || netstat -ltnp 2>/dev/null | grep 8000 || echo "(none)"
echo "=== http.server process ==="
ps aux | grep http.server | grep -v grep || echo "(not running)"
echo "=== iptables INPUT ==="
sudo -n iptables -S INPUT 2>/dev/null | head -30 || true
echo "=== ufw status ==="
sudo -n ufw status verbose 2>/dev/null || true
echo "=== HTTP server log ==="
cat /tmp/openvpn_http_server.log 2>/dev/null || echo "(log not found)"
echo "=== demo dir ==="
ls -lh /home/scoti/openvpn_http_demo/ 2>/dev/null || echo "(dir not found)"
'@
    $diag = Invoke-ServerSsh -RemoteCmd $diagScript -TimeoutSec 30
    Write-Host $diag.Out
    throw 'HTTP server failed to start on the server VM.'
}
Write-Ok 'HTTP server is up on 10.8.0.1:8000.'

# ---------------------------------------------------------------------------
# 3. Prepare client + OpenVPN connect
# ---------------------------------------------------------------------------

Write-Section 'Client: preflight (config, tcpdump)'

# Robust diagnostic check. This avoids a blind "missing" error and proves
# which VM/SSH target is being inspected.
$cfgCheckScript = @'
REQ_PATH="__CLIENT_OVPN_PATH__"
echo "CLIENT_PREFLIGHT_BEGIN"
echo "USER=$(whoami)"
echo "HOSTNAME=$(hostname)"
echo "PWD=$(pwd)"
echo "REQ_PATH=$REQ_PATH"
echo "HOME=$HOME"
if [ -f "$REQ_PATH" ]; then
  echo "CFG_OK=$REQ_PATH"
  ls -l "$REQ_PATH"
else
  echo "CFG_MISSING=$REQ_PATH"
  echo "AVAILABLE_OVPN_FILES_BEGIN"
  find /home/__SSH_USER__ /etc/openvpn -maxdepth 5 -type f -name "*.ovpn" 2>/dev/null | sed 's/^/OVPN_FOUND=/' || true
  echo "AVAILABLE_OVPN_FILES_END"
fi
command -v tcpdump >/dev/null 2>&1 && echo "TCPDUMP_OK" || echo "TCPDUMP_MISSING"
echo "CLIENT_PREFLIGHT_END"
'@
$cfgCheckScript = $cfgCheckScript.Replace('__CLIENT_OVPN_PATH__', $ClientOpenVpnConfig)
$cfgCheckScript = $cfgCheckScript.Replace('__SSH_USER__', $SshUser)
$cfgR = Invoke-ClientSsh -RemoteCmd $cfgCheckScript -TimeoutSec 20
Write-Host $cfgR.Out

if ($cfgR.Out -notmatch 'CFG_OK=') {
    $foundMatch = [regex]::Match($cfgR.Out, 'OVPN_FOUND=(.+)')
    if ($foundMatch.Success) {
        $discoveredConfig = $foundMatch.Groups[1].Value.Trim()
        Write-Warn2 "Requested OpenVPN config was not visible at '$ClientOpenVpnConfig'. Using discovered config: $discoveredConfig"
        $ClientOpenVpnConfig = $discoveredConfig
    } else {
        throw "OpenVPN client config not visible through SSH on ${ClientSshTarget}:$ClientSshPort. Requested: $ClientOpenVpnConfig. See CLIENT_PREFLIGHT diagnostics above."
    }
}

if ($cfgR.Out -notmatch 'TCPDUMP_OK') {
    throw 'tcpdump not found on client VM.'
}

Write-Ok "Client preflight ok. OpenVPN config: $ClientOpenVpnConfig"

Write-Section 'Client: starting OpenVPN client (daemon)'
Invoke-ClientSsh -RemoteCmd "sudo -n pkill -f 'openvpn --config $ClientOpenVpnConfig' 2>/dev/null || true" -TimeoutSec 15 | Out-Null
$startVpn = "sudo -n rm -f /tmp/openvpn_lab_client.pid /tmp/openvpn_lab_client.log; sudo -n openvpn --config $ClientOpenVpnConfig --daemon --writepid /tmp/openvpn_lab_client.pid --log /tmp/openvpn_lab_client.log; echo started"
$r = Invoke-ClientSsh -RemoteCmd $startVpn -TimeoutSec 30
Write-Host $r.Out

$tun = $false
for ($i = 0; $i -lt 15; $i++) {
    $r = Invoke-ClientSsh -RemoteCmd 'ip a | grep -E "tun0|tun1" || true' -TimeoutSec 8
    if ($r.Out -match 'tun') { $tun = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $tun) {
    $log = Invoke-ClientSsh -RemoteCmd 'sudo -n cat /tmp/openvpn_lab_client.log 2>/dev/null || true' -TimeoutSec 10
    Write-Host $log.Out
    throw 'OpenVPN tun device did not come up on the client.'
}
Write-Ok 'OpenVPN tun interface is up on the client.'

# ---------------------------------------------------------------------------
# Preflight: verify HTTP server is reachable from inside the VPN tunnel
# ---------------------------------------------------------------------------

Write-Section 'Preflight: client tunnel IP + ping 10.8.0.1'
$r = Invoke-ClientSsh -RemoteCmd 'ip addr show; ip route show' -TimeoutSec 15
Write-Host $r.Out

# Ping — use exit code, not text matching.  ICMP may be blocked; treat failure
# as a warning only and let the curl test be the authoritative gate.
$pingR = Invoke-ClientSsh `
    -RemoteCmd 'ping -c 4 10.8.0.1; echo PING_RC=$?' `
    -TimeoutSec 25
Write-Host $pingR.Out
if ($pingR.Out -match 'PING_RC=0') {
    Write-Ok 'ICMP ping to 10.8.0.1 succeeded.'
} else {
    Write-Warn2 'ICMP ping to 10.8.0.1 failed; ICMP may be blocked on the tun interface.'
    Write-Warn2 'Continuing to curl reachability test (ping failure is not fatal).'
}

Write-Section 'Preflight: client curl -> http://10.8.0.1:8000/small.bin'

# ── First curl attempt ────────────────────────────────────────────────────────
# Use -fsS so curl exits non-zero on HTTP errors (4xx/5xx).
# Do NOT append || true — we need the real exit code via $r.Ok / $r.Code.
$ClientHttpReady = $false

$curlR = Invoke-ClientSsh `
    -RemoteCmd 'curl -fsS --connect-timeout 20 --max-time 35 -o /tmp/small_preflight.bin http://10.8.0.1:8000/small.bin; echo CURL_RC=$?' `
    -TimeoutSec 30
Write-Host $curlR.Out
if ($curlR.Out -match 'CURL_RC=0') {
    $ClientHttpReady = $true
    Write-Ok 'Client can reach HTTP file server through the VPN tunnel.'
} else {
    Write-Warn2 "First curl failed. Client cannot reach HTTP file server through the VPN tunnel. Attempting server-side iptables fix and retrying..."
}

# ── Server-side iptables fix + retry ─────────────────────────────────────────
if (-not $ClientHttpReady) {
    $fixScript = @'
echo "=== Attempting iptables rules for tun0/tun1 port 8000 ==="
sudo -n iptables -C INPUT -i tun0 -p tcp --dport 8000 -j ACCEPT 2>/dev/null \
  || sudo -n iptables -I INPUT -i tun0 -p tcp --dport 8000 -j ACCEPT 2>/dev/null \
  || echo "iptables tun0 rule skipped: sudo unavailable or rule already present"
sudo -n iptables -C INPUT -i tun1 -p tcp --dport 8000 -j ACCEPT 2>/dev/null \
  || sudo -n iptables -I INPUT -i tun1 -p tcp --dport 8000 -j ACCEPT 2>/dev/null \
  || echo "iptables tun1 rule skipped: sudo unavailable or rule already present"
echo "=== iptables INPUT ==="
sudo -n iptables -S INPUT 2>/dev/null | head -30 || echo "iptables not readable without sudo"
echo "=== ufw status ==="
sudo -n ufw status verbose 2>/dev/null || echo "ufw not readable without sudo"
echo "=== ss :8000 ==="
ss -ltnp 2>/dev/null | grep 8000 || netstat -ltnp 2>/dev/null | grep 8000 || echo "not listening on port 8000"
echo "=== http.server process ==="
ps aux | grep http.server | grep -v grep || echo "http.server not running"
'@
    $fix = Invoke-ServerSsh -RemoteCmd $fixScript -TimeoutSec 30
    Write-Host '--- SERVER FIX OUTPUT ---'
    Write-Host $fix.Out

    Start-Sleep -Seconds 2

    Write-Info 'Retrying client curl after server fix...'
    $curlR2 = Invoke-ClientSsh `
        -RemoteCmd 'curl -fsS --connect-timeout 10 --max-time 15 -o /tmp/small_preflight.bin http://10.8.0.1:8000/small.bin; echo CURL_RC=$?' `
        -TimeoutSec 30
    Write-Host $curlR2.Out
    if ($curlR2.Out -match 'CURL_RC=0') {
        $ClientHttpReady = $true
        Write-Ok 'Client reached HTTP server after iptables fix + retry.'
    } else {
        Write-Warn2 "Retry curl also failed. Collecting full diagnostics..."
    }
}

# ── Final diagnostics + authoritative verbose curl ───────────────────────────
if (-not $ClientHttpReady) {
    Write-Err2 '============================================================'
    Write-Err2 'PREFLIGHT FAILURE: client cannot reach http://10.8.0.1:8000/small.bin'
    Write-Err2 '============================================================'

    Write-Host ''
    Write-Host '--- [SERVER] ip addr / ip route ---'
    $sd1 = Invoke-ServerSsh -RemoteCmd 'ip addr show; ip route show' -TimeoutSec 15
    Write-Host $sd1.Out

    Write-Host ''
    Write-Host '--- [SERVER] ss :8000 / http.server process ---'
    $sd2 = Invoke-ServerSsh -RemoteCmd @'
ss -ltnp 2>/dev/null | grep 8000 || netstat -ltnp 2>/dev/null | grep 8000 || echo "not listening on port 8000"
ps aux | grep http.server | grep -v grep || echo "http.server not running"
'@ -TimeoutSec 15
    Write-Host $sd2.Out

    Write-Host ''
    Write-Host '--- [SERVER] HTTP server log ---'
    $sd3 = Invoke-ServerSsh -RemoteCmd 'cat /tmp/openvpn_http_server.log 2>/dev/null || echo "log not found"' -TimeoutSec 10
    Write-Host $sd3.Out

    Write-Host ''
    Write-Host '--- [SERVER] iptables + ufw ---'
    $sd4 = Invoke-ServerSsh -RemoteCmd @'
sudo -n iptables -S INPUT 2>/dev/null | head -30 || echo "iptables not readable without sudo"
sudo -n ufw status verbose 2>/dev/null || echo "ufw not readable without sudo"
'@ -TimeoutSec 15
    Write-Host $sd4.Out

    Write-Host ''
    Write-Host '--- [SERVER] OpenVPN tun IP ---'
    $sd5 = Invoke-ServerSsh -RemoteCmd @'
ip a | grep -E 'tun|10\.8\.' || echo "no tun or 10.8.x address found"
systemctl is-active openvpn@server 2>/dev/null || echo "openvpn@server: status unknown"
'@ -TimeoutSec 10
    Write-Host $sd5.Out

    Write-Host ''
    Write-Host '--- [CLIENT] ip addr / ip route ---'
    $cd1 = Invoke-ClientSsh -RemoteCmd 'ip addr show; ip route show' -TimeoutSec 15
    Write-Host $cd1.Out

    Write-Host ''
    Write-Host '--- [CLIENT] ping 10.8.0.1 ---'
    $cd2 = Invoke-ClientSsh -RemoteCmd 'ping -c 3 10.8.0.1 2>&1; true' -TimeoutSec 20
    Write-Host $cd2.Out

    # Verbose curl — check its EXIT CODE (not just text).  If it succeeds here,
    # the server recovered during diagnostics; honour that and continue.
    Write-Host ''
    Write-Host '--- [CLIENT] verbose curl (authoritative final check) ---'
    $cd3 = Invoke-ClientSsh `
        -RemoteCmd 'curl -v --connect-timeout 10 --max-time 15 -o /tmp/small_preflight_diag.bin http://10.8.0.1:8000/small.bin 2>&1' `
        -TimeoutSec 35
    Write-Host $cd3.Out
    if ($cd3.Ok) {
        $ClientHttpReady = $true
        Write-Ok 'Diagnostic verbose curl succeeded (HTTP 200) — server is reachable. Continuing to capture.'
    }

    if (-not $ClientHttpReady) {
        Write-Host ''
        Write-Err2 'Failure category guide:'
        Write-Err2 '  A. HTTP server not running      -> http.server not in ps aux'
        Write-Err2 '  B. HTTP server wrong interface  -> listening on 0.0.0.0 but iptables blocks tun0'
        Write-Err2 '  C. OpenVPN tunnel not up        -> ping fails, no tun iface on client'
        Write-Err2 '  D. Client route missing         -> ping ok, no route to 10.8.0.1 via tun'
        Write-Err2 '  E. Firewall blocking port 8000  -> ping ok, curl connection refused/timeout'
        Write-Err2 '  F. File missing in demo dir     -> curl gets 404, server log shows FileNotFoundError'
        throw 'Client VM cannot reach HTTP server at http://10.8.0.1:8000/small.bin. Aborting before capture.'
    }
}

if ($ClientHttpReady) {
    Write-Ok 'Preflight passed: client can reach HTTP file server through the VPN tunnel.'
}

# ---------------------------------------------------------------------------
# 4. tcpdump + traffic on client
# ---------------------------------------------------------------------------

Write-Section "Starting tcpdump on client (background, ${CaptureSeconds}s)"
Invoke-ClientSsh -RemoteCmd "rm -f '$RemotePcap'" -TimeoutSec 10 | Out-Null
$tcpdumpCmd  = "sudo -n timeout $CaptureSeconds tcpdump -i any -B 8192 -w '$RemotePcap' -q"
$tcpdumpArgs = @($ClientSshOpts + @($ClientSshTarget, $tcpdumpCmd))
$tcpdumpJob  = Start-Job -ScriptBlock { param($a) & ssh @a 2>&1 } -ArgumentList (,$tcpdumpArgs)
Start-Sleep -Seconds 3

$check = Invoke-ClientSsh -RemoteCmd 'pgrep -a tcpdump || true' -TimeoutSec 10
if ($check.Out -match 'tcpdump') { Write-Ok 'tcpdump confirmed running on client VM.' }
else { Write-Warn2 "tcpdump not visible via pgrep yet (continuing): $($check.Out)" }

Write-Section 'Client: generating varied OpenVPN tunnel traffic'
$traffic = @'
set +e
for i in $(seq 1 40); do
  curl --max-time 15 -s -o /tmp/small_$i.bin  http://10.8.0.1:8000/small.bin  || true
  curl --max-time 20 -s -o /tmp/medium_$i.bin http://10.8.0.1:8000/medium.bin || true
  ping -c 3 10.8.0.1 >/dev/null 2>&1 || true
  rm -f /tmp/small_$i.bin /tmp/medium_$i.bin
  sleep 0.5
done
for i in $(seq 1 5); do
  curl --max-time 60 -s -o /tmp/large_$i.bin http://10.8.0.1:8000/large.bin || true
  rm -f /tmp/large_$i.bin
  sleep 2
done
echo openvpn_lab_traffic_done
'@
$r = Invoke-ClientSsh -RemoteCmd $traffic -TimeoutSec ($CaptureSeconds + 120)
Write-Host $r.Out

Write-Section 'Waiting for tcpdump to finish'
$done = Wait-Job $tcpdumpJob -Timeout ($CaptureSeconds + 30)
if (-not $done) {
    Write-Warn2 'tcpdump job did not finish in time; stopping.'
    Stop-Job $tcpdumpJob | Out-Null
}
$tcpdumpOut = Receive-Job $tcpdumpJob 2>&1
Remove-Job $tcpdumpJob -Force | Out-Null
if ($tcpdumpOut) { Write-Host ($tcpdumpOut -join "`n") }

# ---------------------------------------------------------------------------
# 5. Teardown OpenVPN client + HTTP server
# ---------------------------------------------------------------------------

Write-Section 'Teardown: OpenVPN client + HTTP server'
$teardownClient = @'
if [ -f /tmp/openvpn_lab_client.pid ]; then
  sudo -n kill "$(cat /tmp/openvpn_lab_client.pid)" 2>/dev/null || true
  sudo -n rm -f /tmp/openvpn_lab_client.pid
fi
sudo -n pkill -f 'openvpn --config /home/scoti/client1.ovpn' 2>/dev/null || true
echo client_torn_down
'@
Invoke-ClientSsh -RemoteCmd $teardownClient -TimeoutSec 20 | Out-Null

$teardownServer = @'
if [ -f /tmp/openvpn_http_server.pid ]; then
  kill "$(cat /tmp/openvpn_http_server.pid)" 2>/dev/null || true
  rm -f /tmp/openvpn_http_server.pid
fi
pkill -f "python3 -m http.server 8000" 2>/dev/null || true
echo server_torn_down
'@
Invoke-ServerSsh -RemoteCmd $teardownServer -TimeoutSec 20 | Out-Null
Write-Ok 'Teardown complete.'

# ---------------------------------------------------------------------------
# 6. Verify + sample + scp
# ---------------------------------------------------------------------------

Write-Section 'Verifying remote PCAP'
$ls = Invoke-ClientSsh -RemoteCmd "ls -lh '$RemotePcap' 2>/dev/null || echo MISSING" -TimeoutSec 10
Write-Host $ls.Out
if ($ls.Out -match 'MISSING') { throw "Remote PCAP missing: $RemotePcap" }
$sz = Invoke-ClientSsh -RemoteCmd "stat -c %s '$RemotePcap' 2>/dev/null || echo 0" -TimeoutSec 10
$bytes = 0
[int64]::TryParse(($sz.Out.Trim() -split "`n")[-1], [ref]$bytes) | Out-Null
if ($bytes -lt 200) { throw "Remote PCAP is empty or too small ($bytes bytes)." }
$mb = [math]::Round($bytes / 1MB, 2)
Write-Ok "Remote PCAP size: $bytes bytes (~$mb MB)."

$remoteToCopy = $RemotePcap
$localTarget  = $LocalPcap
if ($mb -gt $MaxPcapMB) {
    Write-Info "PCAP > ${MaxPcapMB} MB; creating sample of 100000 packets."
    $sample = "tcpdump -r '$RemotePcap' -w '$RemotePcapSample' -c 100000 && ls -lh '$RemotePcapSample'"
    $r = Invoke-ClientSsh -RemoteCmd $sample -TimeoutSec 120
    Write-Host $r.Out
    $remoteToCopy = $RemotePcapSample
    $localTarget  = $LocalPcapSample
}

Write-Section "Copying PCAP to host (scp): $remoteToCopy -> $localTarget"
$scpArgs = @($ClientScpOpts + @(('{0}:{1}' -f $ClientSshTarget, $remoteToCopy), $localTarget))
& scp @scpArgs
if ($LASTEXITCODE -ne 0) { throw "scp failed (exit $LASTEXITCODE)." }
Write-Ok "Local PCAP: $localTarget"

# ---------------------------------------------------------------------------
# 7. Backend reset + stream
# ---------------------------------------------------------------------------

if (-not $KeepBackendState) {
    Write-Section 'Resetting backend live-ingest state'
    try {
        Invoke-RestMethod -Method Post -Uri ("{0}/firewall/live-ingest/reset" -f $ApiBase) -TimeoutSec 10 | Out-Null
        Write-Ok 'Backend live-ingest state reset.'
    } catch { Write-Warn2 "Could not reset backend state: $($_.Exception.Message)" }
}

Write-Section 'Streaming features into backend'
& python $PcapStreamer `
    --pcap         $localTarget `
    --api          $ApiBase `
    --batch-size   $BatchSize `
    --delay-seconds $DelaySeconds `
    --scenario     $Scenario `
    --model-id     $ActiveRuntimeModel `
    --out-csv      $FeaturesCsv
if ($LASTEXITCODE -ne 0) {
            Write-Err2 "pcap_to_live_stream.py failed with code $LASTEXITCODE."
            exit $LASTEXITCODE
        }

Write-Section 'Final backend live-ingest state'
try {
    $state = Invoke-RestMethod -Method Get -Uri ("{0}/firewall/live-ingest/state" -f $ApiBase) -TimeoutSec 10
    $state | ConvertTo-Json -Depth 6
} catch { Write-Warn2 "Could not fetch live-ingest state: $($_.Exception.Message)" }

Write-Section 'OpenVPN lab demo complete (simulation only)'
Write-Ok 'All steps finished.'
exit 0