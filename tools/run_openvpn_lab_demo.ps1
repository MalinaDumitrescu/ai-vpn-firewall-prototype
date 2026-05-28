<#
.SYNOPSIS
    Two-VM OpenVPN lab demo runner for the AI VPN Firewall Prototype.

.DESCRIPTION
    Coordinates a client VM (OpenVPN client + tcpdump + traffic generator) and
    a server VM (OpenVPN server + Python HTTP server on the tunnel IP). Records
    a PCAP of real OpenVPN tunnel traffic inside the client VM, samples it if
    necessary, copies it to the Windows host, and streams robust9 features
    into the FastAPI backend at /firewall/live-ingest.

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
                                    /usr/bin/dd, /usr/bin/pkill
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
    # Wrap an arbitrary multi-line bash script into a single-line remote
    # command by base64-encoding it. PowerShell + Start-Job + ssh otherwise
    # collapse embedded newlines into spaces on the remote shell, which
    # breaks for-loops and `set +e`.
    param([Parameter(Mandatory)] [string] $Script)
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
        $job = Start-Job -ScriptBlock { param($a) & ssh @a 2>&1 } -ArgumentList (,$args)
        $done = Wait-Job $job -Timeout $TimeoutSec
        if (-not $done) {
            Stop-Job $job | Out-Null
            Remove-Job $job -Force | Out-Null
            return @{ Ok = $false; Out = ''; Code = 124 }
        }
        $out = Receive-Job $job
        $code = if ($job.ChildJobs[0].JobStateInfo.State -eq 'Failed') { 1 } else { 0 }
        Remove-Job $job -Force | Out-Null
        return @{ Ok = ($code -eq 0); Out = ($out -join "`n"); Code = $code }
    }
    $out = & ssh @args 2>&1
    return @{ Ok = ($LASTEXITCODE -eq 0); Out = ($out -join "`n"); Code = $LASTEXITCODE }
}
function Invoke-ClientSsh { param([string]$RemoteCmd,[int]$TimeoutSec=0) Invoke-SshRaw -Opts $ClientSshOpts -Target $ClientSshTarget -RemoteCmd $RemoteCmd -TimeoutSec $TimeoutSec }
function Invoke-ServerSsh { param([string]$RemoteCmd,[int]$TimeoutSec=0) Invoke-SshRaw -Opts $ServerSshOpts -Target $ServerSshTarget -RemoteCmd $RemoteCmd -TimeoutSec $TimeoutSec }

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
Write-Host "  Client VM       : $ClientVmName  ($ClientSshTarget`:$ClientSshPort)"
Write-Host "  Server VM       : $ServerVmName  ($ServerSshTarget`:$ServerSshPort)"
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
            --dry-run
        if ($LASTEXITCODE -ne 0) { Write-Warn2 "pcap_to_live_stream.py exited with code $LASTEXITCODE." }
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

Wait-SshGeneric -Label "$ClientSshTarget`:$ClientSshPort" -TimeoutSec 120 -Probe {
    Invoke-ClientSsh -RemoteCmd 'echo ssh_ready' -TimeoutSec 12
}
Wait-SshGeneric -Label "$ServerSshTarget`:$ServerSshPort" -TimeoutSec 120 -Probe {
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
$prep = @'
set -e
mkdir -p ~/vpn-http
[ -f ~/vpn-http/small.bin ]  || dd if=/dev/urandom of=~/vpn-http/small.bin  bs=100K count=1 status=none
[ -f ~/vpn-http/medium.bin ] || dd if=/dev/urandom of=~/vpn-http/medium.bin bs=1M  count=5 status=none
[ -f ~/vpn-http/large.bin ]  || dd if=/dev/urandom of=~/vpn-http/large.bin  bs=1M  count=30 status=none
ls -lh ~/vpn-http/
'@
$r = Invoke-ServerSsh -RemoteCmd $prep -TimeoutSec 60
Write-Host $r.Out
if (-not $r.Ok) { throw 'Failed to prepare ~/vpn-http on server.' }

$startHttp = @'
pkill -f "python3 -m http.server 8000" 2>/dev/null || true
rm -f /tmp/openvpn_lab_http.pid /tmp/openvpn_lab_http.log
cd ~/vpn-http
setsid python3 -m http.server 8000 --bind 10.8.0.1 > /tmp/openvpn_lab_http.log 2>&1 < /dev/null &
echo $! > /tmp/openvpn_lab_http.pid
sleep 2
if ps -p "$(cat /tmp/openvpn_lab_http.pid)" >/dev/null 2>&1; then
  echo "HTTP_READY pid=$(cat /tmp/openvpn_lab_http.pid)"
else
  echo "HTTP_FAILED"
  cat /tmp/openvpn_lab_http.log
  exit 31
fi
'@
$r = Invoke-ServerSsh -RemoteCmd $startHttp -TimeoutSec 30
Write-Host $r.Out
if ($r.Out -notmatch 'HTTP_READY') { throw 'HTTP server failed to start on the server VM.' }
Write-Ok 'HTTP server is up on 10.8.0.1:8000.'

# ---------------------------------------------------------------------------
# 3. Prepare client + OpenVPN connect
# ---------------------------------------------------------------------------

Write-Section 'Client: preflight (config, tcpdump)'
$r = Invoke-ClientSsh -RemoteCmd "test -f '$ClientOpenVpnConfig' && echo cfg_ok || echo cfg_missing" -TimeoutSec 10
if ($r.Out -notmatch 'cfg_ok') { throw "OpenVPN client config missing on client VM: $ClientOpenVpnConfig" }
$r = Invoke-ClientSsh -RemoteCmd 'command -v tcpdump >/dev/null 2>&1 && echo td_ok || echo td_missing' -TimeoutSec 10
if ($r.Out -notmatch 'td_ok') { throw 'tcpdump not found on client VM.' }
Write-Ok 'Client preflight ok.'

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

$r = Invoke-ClientSsh -RemoteCmd 'ping -c 4 10.8.0.1 || true' -TimeoutSec 20
Write-Host $r.Out
if ($r.Out -notmatch '0% packet loss|1 received|2 received|3 received|4 received') {
    $log = Invoke-ClientSsh -RemoteCmd 'sudo -n cat /tmp/openvpn_lab_client.log 2>/dev/null || true' -TimeoutSec 10
    Write-Host $log.Out
    throw 'Client cannot ping VPN gateway 10.8.0.1.'
}
Write-Ok 'Client reaches 10.8.0.1 over the tunnel.'

# ---------------------------------------------------------------------------
# 4. tcpdump + traffic on client
# ---------------------------------------------------------------------------

Write-Section "Starting tcpdump on client (background, ${CaptureSeconds}s)"
Invoke-ClientSsh -RemoteCmd "rm -f '$RemotePcap'" -TimeoutSec 10 | Out-Null
$tcpdumpCmd  = "sudo -n timeout $CaptureSeconds tcpdump -i any -w '$RemotePcap' -q"
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
if [ -f /tmp/openvpn_lab_http.pid ]; then
  kill "$(cat /tmp/openvpn_lab_http.pid)" 2>/dev/null || true
  rm -f /tmp/openvpn_lab_http.pid
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
    --out-csv      $FeaturesCsv
if ($LASTEXITCODE -ne 0) { Write-Warn2 "pcap_to_live_stream.py exited with code $LASTEXITCODE." }

Write-Section 'Final backend live-ingest state'
try {
    $state = Invoke-RestMethod -Method Get -Uri ("{0}/firewall/live-ingest/state" -f $ApiBase) -TimeoutSec 10
    $state | ConvertTo-Json -Depth 6
} catch { Write-Warn2 "Could not fetch live-ingest state: $($_.Exception.Message)" }

Write-Section 'OpenVPN lab demo complete (simulation only)'
Write-Ok 'All steps finished.'
exit 0


