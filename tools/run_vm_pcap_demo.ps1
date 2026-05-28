<#
.SYNOPSIS
    Single-VM PCAP demo runner for the AI VPN Firewall Prototype.

.DESCRIPTION
    Automates traffic generation, tcpdump capture inside an Ubuntu VirtualBox
    VM, scp transfer to the Windows host, and streaming of robust9 features
    into the FastAPI backend's /firewall/live-ingest endpoint.

    Supported -TrafficProfile values: basic, vpnlike, warp.

    SAFETY
    ------
    * LOCAL DEMO MODE ONLY. Not for production / public deployment.
    * Does NOT modify iptables / nftables / Windows Firewall / routes.
    * Does NOT block real packets. Backend decisions are simulation-only.
    * Designed to be launched non-interactively (FastAPI subprocess from the
      frontend Demo Runner). Every SSH call uses BatchMode=yes and
      ConnectTimeout=10; sudo is always called as `sudo -n`.

.NOTES
    Required passwordless sudoers rule on the VM:
      scoti ALL=(root) NOPASSWD: /usr/bin/tcpdump, /usr/bin/timeout, /usr/bin/rm
    Required SSH key login (no password prompt).
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('basic', 'vpnlike', 'warp')]
    [string] $TrafficProfile,

    [string] $VmName        = 'Ubunutu',
    [string] $SshUser       = 'scoti',
    [string] $SshHost       = '127.0.0.1',
    [int]    $SshPort       = 2222,

    [int]    $CaptureSeconds = 60,
    [string] $ApiBase        = 'http://127.0.0.1:8765',
    [int]    $BatchSize      = 5,
    [int]    $DelaySeconds   = 2,

    [switch] $AllowWarpUnverified,
    [switch] $KeepBackendState,
    [switch] $DryRun,
    [switch] $SkipVmStart
)

# ---------------------------------------------------------------------------
# Globals / setup
# ---------------------------------------------------------------------------

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false) } catch {}
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$CapturesDir = Join-Path $ProjectRoot 'captures'
$PcapStreamer = Join-Path $ScriptDir 'pcap_to_live_stream.py'

if (-not (Test-Path $CapturesDir)) {
    New-Item -ItemType Directory -Path $CapturesDir | Out-Null
}

# Per-profile defaults ------------------------------------------------------
$Profiles = @{
    'basic' = @{
        Scenario   = 'vm_basic_benign'
        RemotePcap = '/home/{0}/vm_basic_benign.pcap' -f $SshUser
        LocalPcap  = Join-Path $CapturesDir 'vm_basic_benign.pcap'
        Note       = 'Benign DNS / ICMP / HTTPS browsing sample.'
    }
    'vpnlike' = @{
        Scenario   = 'vm_vpnlike'
        RemotePcap = '/home/{0}/vm_vpnlike.pcap' -f $SshUser
        LocalPcap  = Join-Path $CapturesDir 'vm_vpnlike.pcap'
        Note       = 'High-volume HTTPS only. NOT a real VPN tunnel.'
    }
    'warp' = @{
        Scenario   = 'vm_warp'
        RemotePcap = '/home/{0}/vm_warp.pcap' -f $SshUser
        LocalPcap  = Join-Path $CapturesDir 'vm_warp.pcap'
        Note       = 'Real Cloudflare WARP encrypted tunnel.'
    }
}

$P             = $Profiles[$TrafficProfile]
$Scenario      = $P.Scenario
$RemotePcap    = $P.RemotePcap
$LocalPcap     = $P.LocalPcap
$FeaturesCsv   = Join-Path $CapturesDir ("{0}_features.csv" -f $Scenario)
$SshOpts       = @('-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','ConnectTimeout=10','-p',$SshPort)
$ScpOpts       = @('-o','BatchMode=yes','-o','StrictHostKeyChecking=accept-new','-o','ConnectTimeout=10','-P',$SshPort)
$SshTarget     = ('{0}@{1}' -f $SshUser, $SshHost)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-Section([string]$Title) {
    Write-Host ''
    Write-Host ('=' * 70)
    Write-Host "  $Title"
    Write-Host ('=' * 70)
}

function Write-Info([string]$Msg)  { Write-Host "[info] $Msg" }
function Write-Warn2([string]$Msg) { Write-Host "[warn] $Msg" -ForegroundColor Yellow }
function Write-Err2([string]$Msg)  { Write-Host "[err ] $Msg" -ForegroundColor Red }
function Write-Ok([string]$Msg)    { Write-Host "[ ok ] $Msg" -ForegroundColor Green }

function Invoke-Ssh {
    param([Parameter(Mandatory)] [string] $RemoteCmd, [int] $TimeoutSec = 0)
    $args = @($SshOpts + @($SshTarget, $RemoteCmd))
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
    $code = $LASTEXITCODE
    return @{ Ok = ($code -eq 0); Out = ($out -join "`n"); Code = $code }
}

function Test-VmRunning {
    param([string] $Name)
    try {
        $running = & VBoxManage list runningvms 2>$null
        return ($running -match [regex]::Escape($Name))
    } catch { return $false }
}

function Start-VmIfNeeded {
    param([string] $Name)
    if ($SkipVmStart) { Write-Info "SkipVmStart set, not touching VM '$Name'."; return }
    if (Test-VmRunning -Name $Name) {
        Write-Info "VM '$Name' already running."
        return
    }
    Write-Info "Starting VM '$Name' headless..."
    try {
        & VBoxManage startvm $Name --type headless | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Warn2 "VBoxManage returned $LASTEXITCODE for '$Name'. Continuing." }
    } catch {
        Write-Warn2 "Failed to start VM '$Name': $($_.Exception.Message). Continuing."
    }
}

function Wait-Ssh {
    param([int] $TimeoutSec = 90)
    Write-Info "Waiting up to $TimeoutSec s for SSH on $SshTarget`:$SshPort ..."
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        $r = Invoke-Ssh -RemoteCmd 'echo ssh_ready' -TimeoutSec 12
        if ($r.Ok -and ($r.Out -match 'ssh_ready')) { Write-Ok 'SSH reachable.'; return }
        Start-Sleep -Seconds 3
    }
    throw "SSH did not become reachable on $SshTarget`:$SshPort within $TimeoutSec s."
}

function Confirm-Preflight {
    Write-Section 'Preflight checks (SSH key + tcpdump + passwordless sudo)'

    $r = Invoke-Ssh -RemoteCmd 'echo key_ok' -TimeoutSec 15
    if (-not $r.Ok -or ($r.Out -notmatch 'key_ok')) {
        throw "SSH key login is not configured for this VM. Output: $($r.Out)"
    }
    Write-Ok 'SSH key login ok.'

    $r = Invoke-Ssh -RemoteCmd 'command -v tcpdump >/dev/null 2>&1 && echo tcpdump_ok || echo tcpdump_missing' -TimeoutSec 15
    if ($r.Out -notmatch 'tcpdump_ok') {
        throw "tcpdump not found on VM. Output: $($r.Out)"
    }
    Write-Ok 'tcpdump available.'

    $probe = "sudo -n timeout 1 tcpdump -i any -w /home/$SshUser/tcpdump_sudo_test.pcap >/dev/null 2>&1; echo rc=`$?"
    $r = Invoke-Ssh -RemoteCmd $probe -TimeoutSec 20
    Invoke-Ssh -RemoteCmd "sudo -n rm -f /home/$SshUser/tcpdump_sudo_test.pcap || true" -TimeoutSec 10 | Out-Null
    if ($r.Out -match 'rc=0' -or $r.Out -match 'rc=124') {
        Write-Ok 'Passwordless sudo for tcpdump/timeout ok.'
    } else {
        throw "Passwordless sudo for tcpdump/timeout/rm is not configured. Output: $($r.Out)"
    }
}

# ---------------------------------------------------------------------------
# Traffic generators (single-line bash for CRLF safety)
# ---------------------------------------------------------------------------

function Get-BasicTrafficScript {
    return @'
set +e
for i in $(seq 1 6); do curl --max-time 8 -s -o /dev/null http://example.com/ || true; curl --max-time 8 -s -o /dev/null https://en.wikipedia.org/wiki/Main_Page || true; ping -c 2 8.8.8.8 >/dev/null 2>&1 || true; sleep 1; done
echo basic_traffic_done
'@
}

function Get-VpnlikeTrafficScript {
    return @'
set +e
echo "[vm] vpnlike: encrypted/high-volume HTTPS, NOT a real VPN tunnel."
for i in $(seq 1 25); do curl --max-time 10 -s -o /dev/null https://example.com/ || true; curl --max-time 10 -s -o /dev/null https://en.wikipedia.org/wiki/Main_Page || true; curl --max-time 10 -s -o /dev/null https://github.com/ || true; sleep 0.4; done
curl --max-time 60 -s -o /tmp/dl10.bin https://speed.cloudflare.com/__down?bytes=10485760 || true
rm -f /tmp/dl10.bin || true
echo vpnlike_traffic_done
'@
}

function Get-WarpTrafficScript {
    return @'
set +e
for i in $(seq 1 30); do curl --max-time 8 -s -o /dev/null https://example.com/ || true; curl --max-time 8 -s -o /dev/null https://en.wikipedia.org/wiki/Main_Page || true; curl --max-time 8 -s -o /dev/null https://www.cloudflare.com/ || true; sleep 0.4; done
echo warp_traffic_done
'@
}

function Invoke-WarpConnectAndVerify {
    Write-Info 'Connecting Cloudflare WARP inside VM (warp-cli connect)...'
    Invoke-Ssh -RemoteCmd 'warp-cli --accept-tos connect >/dev/null 2>&1 || warp-cli connect >/dev/null 2>&1 || true' -TimeoutSec 30 | Out-Null

    $connected = $false
    for ($i = 0; $i -lt 10; $i++) {
        $r = Invoke-Ssh -RemoteCmd 'warp-cli status 2>/dev/null || true' -TimeoutSec 10
        if ($r.Out -match 'Connected') { $connected = $true; break }
        Start-Sleep -Seconds 3
    }
    if (-not $connected) {
        Write-Warn2 'warp-cli did not report Connected.'
    } else {
        Write-Ok 'warp-cli reports Connected.'
    }

    $verified = $false
    for ($i = 0; $i -lt 15; $i++) {
        $r = Invoke-Ssh -RemoteCmd 'curl --max-time 5 -s https://www.cloudflare.com/cdn-cgi/trace || true' -TimeoutSec 15
        if ($r.Out -match 'warp=on' -or $r.Out -match 'warp=plus') { $verified = $true; break }
        Start-Sleep -Seconds 3
    }
    if ($verified) {
        Write-Ok 'Cloudflare trace confirms WARP is on.'
    } elseif ($AllowWarpUnverified) {
        Write-Warn2 'WARP could not be verified via cdn-cgi/trace, continuing because -AllowWarpUnverified is set.'
    } else {
        throw 'WARP is not verified (cdn-cgi/trace did not report warp=on). Re-run with -AllowWarpUnverified to bypass.'
    }
}

function Invoke-WarpTeardown {
    try {
        Invoke-Ssh -RemoteCmd 'warp-cli disconnect >/dev/null 2>&1 || true' -TimeoutSec 15 | Out-Null
        Write-Info 'warp-cli disconnect issued.'
    } catch { Write-Warn2 "WARP teardown failed: $($_.Exception.Message)" }
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

Write-Section "AI VPN Firewall Prototype - VM PCAP Demo (LOCAL DEMO MODE)"
Write-Host "  Profile        : $TrafficProfile"
Write-Host "  Note           : $($P.Note)"
Write-Host "  VM             : $VmName  ($SshTarget`:$SshPort)"
Write-Host "  Capture seconds: $CaptureSeconds"
Write-Host "  API base       : $ApiBase"
Write-Host "  Remote PCAP    : $RemotePcap"
Write-Host "  Local  PCAP    : $LocalPcap"
Write-Host "  Features CSV   : $FeaturesCsv"
Write-Host "  KeepBackend    : $($KeepBackendState.IsPresent)"
Write-Host "  DryRun         : $($DryRun.IsPresent)"
Write-Host "  Backend decisions are SIMULATION ONLY. No real packets are blocked."
Write-Host ''

# ---------------------------------------------------------------------------
# DryRun short-circuit
# ---------------------------------------------------------------------------

if ($DryRun) {
    Write-Section 'DryRun mode'
    Write-Info 'DryRun: skipping VM start, SSH, tcpdump, scp, and live-ingest.'
    if (Test-Path $LocalPcap) {
        Write-Info "Found existing local PCAP at $LocalPcap; invoking pcap_to_live_stream.py --dry-run."
        & python $PcapStreamer `
            --pcap        $LocalPcap `
            --scenario    $Scenario `
            --out-csv     $FeaturesCsv `
            --batch-size  $BatchSize `
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
# Real flow
# ---------------------------------------------------------------------------

Start-VmIfNeeded -Name $VmName
Wait-Ssh -TimeoutSec 90
Confirm-Preflight

Write-Section 'Cleaning up old remote PCAP'
Invoke-Ssh -RemoteCmd "rm -f '$RemotePcap'" -TimeoutSec 10 | Out-Null

# WARP setup (must precede tcpdump so verification packets are not in the pcap)
if ($TrafficProfile -eq 'warp') {
    Write-Section 'WARP connect + verify'
    Invoke-WarpConnectAndVerify
}

Write-Section "Starting tcpdump on VM (background, ${CaptureSeconds}s)"
$tcpdumpCmd = "sudo -n timeout $CaptureSeconds tcpdump -i any -w '$RemotePcap' -q"
$tcpdumpArgs = @($SshOpts + @($SshTarget, $tcpdumpCmd))
$tcpdumpJob = Start-Job -ScriptBlock { param($a) & ssh @a 2>&1 } -ArgumentList (,$tcpdumpArgs)
Start-Sleep -Seconds 3

$check = Invoke-Ssh -RemoteCmd 'pgrep -a tcpdump || true' -TimeoutSec 10
if ($check.Out -match 'tcpdump') { Write-Ok 'tcpdump confirmed running on VM.' }
else { Write-Warn2 "tcpdump not visible via pgrep yet (continuing). Output: $($check.Out)" }

Write-Section "Generating $TrafficProfile traffic on VM"
$trafficScript = switch ($TrafficProfile) {
    'basic'   { Get-BasicTrafficScript }
    'vpnlike' { Get-VpnlikeTrafficScript }
    'warp'    { Get-WarpTrafficScript }
}
$trafR = Invoke-Ssh -RemoteCmd $trafficScript -TimeoutSec ($CaptureSeconds + 60)
Write-Host $trafR.Out

Write-Section 'Waiting for tcpdump to finish'
$waitMargin = 20
$done = Wait-Job $tcpdumpJob -Timeout ($CaptureSeconds + $waitMargin)
if (-not $done) {
    Write-Warn2 'tcpdump job did not finish in time, stopping it.'
    Stop-Job $tcpdumpJob | Out-Null
}
$tcpdumpOut = Receive-Job $tcpdumpJob 2>&1
Remove-Job $tcpdumpJob -Force | Out-Null
if ($tcpdumpOut) { Write-Host ($tcpdumpOut -join "`n") }

if ($TrafficProfile -eq 'warp') {
    Write-Section 'WARP teardown'
    Invoke-WarpTeardown
}

Write-Section 'Verifying remote PCAP'
$ls = Invoke-Ssh -RemoteCmd "ls -lh '$RemotePcap' 2>/dev/null || echo MISSING" -TimeoutSec 10
Write-Host $ls.Out
if ($ls.Out -match 'MISSING') { throw "Remote PCAP missing: $RemotePcap" }
$sz = Invoke-Ssh -RemoteCmd "stat -c %s '$RemotePcap' 2>/dev/null || echo 0" -TimeoutSec 10
$bytes = 0
[int]::TryParse(($sz.Out.Trim() -split "`n")[-1], [ref]$bytes) | Out-Null
if ($bytes -lt 200) { throw "Remote PCAP is empty or too small ($bytes bytes)." }
Write-Ok "Remote PCAP size: $bytes bytes."

Write-Section 'Copying PCAP to host (scp)'
$scpArgs = @($ScpOpts + @(('{0}:{1}' -f $SshTarget, $RemotePcap), $LocalPcap))
& scp @scpArgs
if ($LASTEXITCODE -ne 0) { throw "scp failed (exit $LASTEXITCODE)." }
Write-Ok "Local PCAP: $LocalPcap"

if (-not $KeepBackendState) {
    Write-Section 'Resetting backend live-ingest state'
    try {
        Invoke-RestMethod -Method Post -Uri ("{0}/firewall/live-ingest/reset" -f $ApiBase) -TimeoutSec 10 | Out-Null
        Write-Ok 'Backend live-ingest state reset.'
    } catch {
        Write-Warn2 "Could not reset backend state: $($_.Exception.Message)"
    }
}

Write-Section 'Streaming features into backend'
& python $PcapStreamer `
    --pcap         $LocalPcap `
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
} catch {
    Write-Warn2 "Could not fetch live-ingest state: $($_.Exception.Message)"
}

Write-Section "Demo '$TrafficProfile' complete (simulation only)"
Write-Ok 'All steps finished.'
exit 0

