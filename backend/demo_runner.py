"""Local demo job runner for the AI VPN Firewall Prototype.

This module powers the optional ``/demo/...`` HTTP API used by the frontend's
*Demo Runner* page. It launches a small, fixed allowlist of PowerShell demo
scripts as background subprocesses, captures their combined stdout/stderr,
and exposes job status + log streaming via FastAPI endpoints.

SAFETY / SCOPE
==============

* This module is intended **strictly for local thesis demos**.
* It is **NOT** an arbitrary command executor: only the demo names in
  ``ALLOWED_DEMOS`` can be started, and the argument list for each demo is
  hard-coded here. Nothing from the HTTP layer can change the command line.
* It does **NOT** modify firewall rules, run as root, or touch the data
  plane. The PowerShell scripts it launches are the same ones the developer
  would run manually from a terminal.
* The router exposed by ``build_router()`` is mounted by ``main.py`` and is
  meant to be reachable **only over localhost** (the FastAPI CORS allowlist
  already restricts which browsers can reach it). Do not expose this API on
  a public network.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("ai_vpn_firewall.demo_runner")

# --------------------------------------------------------------------------- paths

# Project root = parent of backend/. The PowerShell scripts live under
# ``<project_root>/tools/``. Resolving once at import time keeps every
# subprocess.Popen() call working regardless of which directory uvicorn was
# launched from.
_THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = _THIS_FILE.parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"

# --------------------------------------------------------------------------- allowed demos

# Hard-coded argument vectors. The HTTP layer cannot influence these; it can
# only choose which named demo to start. Keep them in sync with
# tools/run_vm_pcap_demo.ps1 and tools/run_openvpn_lab_demo.ps1.
ALLOWED_DEMOS: Dict[str, Dict[str, Any]] = {
    "basic": {
        "label": "Basic Benign",
        "script": "run_vm_pcap_demo.ps1",
        "args": ["-TrafficProfile", "basic"],
        "description": (
            "Single VM (Ubunutu). DNS/ICMP/HTTPS benign sample, ~30 s capture. "
            "Simulation-only."
        ),
    },
    "vpnlike": {
        "label": "VPN-like HTTPS",
        "script": "run_vm_pcap_demo.ps1",
        "args": ["-TrafficProfile", "vpnlike", "-CaptureSeconds", "60"],
        "description": (
            "Single VM. High-volume encrypted HTTPS scenario (~60 s). NOT a "
            "real VPN tunnel. Simulation-only."
        ),
    },
    "warp": {
        "label": "Cloudflare WARP",
        "script": "run_vm_pcap_demo.ps1",
        "args": [
            "-TrafficProfile",
            "warp",
            "-CaptureSeconds",
            "60",
            "-AllowWarpUnverified",
        ],
        "description": (
            "Single VM. Real Cloudflare WARP encrypted tunnel (~60 s). "
            "Free real tunnel - NOT Proton/Mullvad VPN. Simulation-only."
        ),
    },
    "openvpnlab": {
        "label": "Local OpenVPN Lab",
        "script": "run_openvpn_lab_demo.ps1",
        # SkipClientVmStart + SkipServerVmStart assume both VMs are already
        # running. The lab server VM is named "VPNServer2" in the local setup.
        "args": [
            "-ServerVmName",
            "VPNServer2",
            "-SkipClientVmStart",
            "-SkipServerVmStart",
        ],
        "description": (
            "Two VMs (client + VPNServer2). Real OpenVPN tunnel traffic "
            "captured inside VM. Simulation-only on the backend."
        ),
    },
}

# Maximum number of log lines retained per job (older lines are evicted to
# keep memory bounded for long captures).
MAX_LOG_LINES = 2000


# --------------------------------------------------------------------------- job model


@dataclass
class DemoJob:
    """In-memory record for a single demo invocation."""

    job_id: str
    demo: str
    label: str
    cmd: List[str]
    status: str = "pending"  # pending | running | succeeded | failed | cancelled
    exit_code: Optional[int] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    logs: Deque[str] = field(default_factory=lambda: deque(maxlen=MAX_LOG_LINES))
    _process: Optional[subprocess.Popen] = None
    _reader_thread: Optional[threading.Thread] = None

    def to_dict(self, *, include_logs: bool = True, log_offset: int = 0) -> Dict[str, Any]:
        logs_list = list(self.logs) if include_logs else []
        if log_offset > 0:
            logs_list = logs_list[log_offset:]
        return {
            "job_id": self.job_id,
            "demo": self.demo,
            "label": self.label,
            "cmd": self.cmd,
            "status": self.status,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": (
                (self.finished_at or time.time()) - self.started_at
                if self.started_at is not None
                else None
            ),
            "error": self.error,
            "log_lines_total": len(self.logs),
            "logs": logs_list,
        }


# --------------------------------------------------------------------------- manager


class DemoJobManager:
    """Process-wide manager for demo subprocess jobs.

    Only one demo job may run at a time (unless ``allow_concurrent=True`` is
    passed to ``start``). Job records are kept in memory for the lifetime of
    the FastAPI process so the frontend can poll status + logs.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, DemoJob] = {}

    # ----- helpers ----------------------------------------------------------

    @staticmethod
    def _resolve_powershell() -> str:
        """Return a powershell executable path, preferring Windows PowerShell."""
        for candidate in ("powershell", "pwsh"):
            found = shutil.which(candidate)
            if found:
                return found
        # Hard-coded fallback for typical Windows installs.
        fallback = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        if os.path.exists(fallback):
            return fallback
        raise FileNotFoundError(
            "No PowerShell executable found (powershell.exe or pwsh)."
        )

    def _build_cmd(self, demo: str) -> List[str]:
        spec = ALLOWED_DEMOS[demo]
        script_path = TOOLS_DIR / spec["script"]
        if not script_path.is_file():
            raise FileNotFoundError(f"Demo script not found: {script_path}")
        ps = self._resolve_powershell()
        return [
            ps,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            *list(spec["args"]),
        ]

    def _current_running_job(self) -> Optional[DemoJob]:
        for j in self._jobs.values():
            if j.status == "running":
                return j
        return None

    # ----- public API -------------------------------------------------------

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self._lock:
            jobs = list(self._jobs.values())
        # Most recent first.
        jobs.sort(key=lambda j: j.started_at or 0, reverse=True)
        return [j.to_dict(include_logs=False) for j in jobs]

    def get_job(self, job_id: str, *, log_offset: int = 0) -> Dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job.to_dict(include_logs=True, log_offset=log_offset)

    def start(self, demo: str, *, allow_concurrent: bool = False) -> Dict[str, Any]:
        if demo not in ALLOWED_DEMOS:
            raise ValueError(
                f"Unknown demo '{demo}'. Allowed: {sorted(ALLOWED_DEMOS)}"
            )

        with self._lock:
            if not allow_concurrent:
                running = self._current_running_job()
                if running is not None:
                    raise RuntimeError(
                        f"Another demo job is already running: "
                        f"job_id={running.job_id} demo={running.demo}."
                    )

            cmd = self._build_cmd(demo)
            job_id = uuid.uuid4().hex[:12]
            job = DemoJob(
                job_id=job_id,
                demo=demo,
                label=ALLOWED_DEMOS[demo]["label"],
                cmd=cmd,
            )
            self._jobs[job_id] = job

        # Launch outside the lock to keep startup non-blocking.
        try:
            proc = subprocess.Popen(  # noqa: S603 - fixed cmd, allowlisted
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                bufsize=1,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            job.status = "failed"
            job.error = f"failed to launch process: {exc}"
            job.finished_at = time.time()
            logger.exception("demo_runner: failed to start demo %s", demo)
            return job.to_dict(include_logs=False)

        job._process = proc
        job.status = "running"
        job.started_at = time.time()
        job.logs.append(f"[demo_runner] launching {' '.join(cmd)}")
        job.logs.append(f"[demo_runner] cwd={PROJECT_ROOT}")

        reader = threading.Thread(
            target=self._reader_loop,
            args=(job,),
            name=f"demo-reader-{job_id}",
            daemon=True,
        )
        job._reader_thread = reader
        reader.start()

        logger.info(
            "demo_runner: started demo=%s job_id=%s pid=%s",
            demo,
            job_id,
            proc.pid,
        )
        return job.to_dict(include_logs=False)

    def cancel(self, job_id: str) -> Dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        if job.status != "running" or job._process is None:
            return job.to_dict(include_logs=False)
        try:
            job._process.terminate()
            # Give the script a moment to clean up (it has trap handlers).
            try:
                job._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                job._process.kill()
        except Exception as exc:  # noqa: BLE001
            logger.exception("demo_runner: cancel failed for job %s", job_id)
            job.error = f"cancel error: {exc}"
        job.status = "cancelled"
        job.finished_at = time.time()
        job.logs.append("[demo_runner] job cancelled by user.")
        return job.to_dict(include_logs=False)

    # ----- internal ---------------------------------------------------------

    def _reader_loop(self, job: DemoJob) -> None:
        """Consume the subprocess stdout line by line and update final status."""
        proc = job._process
        assert proc is not None
        try:
            assert proc.stdout is not None
            for raw_line in proc.stdout:
                line = raw_line.rstrip("\r\n")
                job.logs.append(line)
            proc.wait()
        except Exception as exc:  # noqa: BLE001
            job.logs.append(f"[demo_runner] reader error: {exc}")
            logger.exception("demo_runner: reader loop crashed for %s", job.job_id)

        # If cancel() already set status, do not overwrite it.
        if job.status == "running":
            rc = proc.returncode
            job.exit_code = rc
            job.status = "succeeded" if rc == 0 else "failed"
        else:
            job.exit_code = proc.returncode
        job.finished_at = time.time()
        job.logs.append(
            f"[demo_runner] process exited with code={job.exit_code} status={job.status}"
        )


# Singleton used by the router.
_manager = DemoJobManager()


def get_manager() -> DemoJobManager:
    return _manager


# --------------------------------------------------------------------------- router


class StartResponse(BaseModel):
    job_id: str
    demo: str
    label: str
    status: str
    started_at: Optional[float] = None
    cmd: List[str]


def build_router() -> APIRouter:
    """Return an APIRouter exposing the demo runner endpoints under /demo."""
    router = APIRouter(prefix="/demo", tags=["demo-runner"])
    mgr = get_manager()

    @router.get("/allowed")
    def list_allowed() -> Dict[str, Any]:
        """List demos that the frontend is allowed to launch."""
        return {
            "demos": [
                {
                    "name": name,
                    "label": spec["label"],
                    "description": spec["description"],
                    "script": spec["script"],
                    "args": list(spec["args"]),
                }
                for name, spec in ALLOWED_DEMOS.items()
            ],
            "project_root": str(PROJECT_ROOT),
            "tools_dir": str(TOOLS_DIR),
            "warning": (
                "Demo runner executes local PowerShell scripts and is "
                "intended only for local thesis demos."
            ),
        }

    @router.get("/jobs")
    def list_jobs() -> Dict[str, Any]:
        return {"jobs": mgr.list_jobs()}

    @router.get("/jobs/{job_id}")
    def get_job(job_id: str, log_offset: int = 0) -> Dict[str, Any]:
        try:
            return mgr.get_job(job_id, log_offset=log_offset)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from exc

    @router.post("/jobs/{job_id}/cancel", response_model=None)
    def cancel_job(job_id: str) -> Dict[str, Any]:
        try:
            return mgr.cancel(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}") from exc

    def _start(demo: str, allow_concurrent: bool) -> Dict[str, Any]:
        try:
            return mgr.start(demo, allow_concurrent=allow_concurrent)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/run/basic", response_model=StartResponse)
    def run_basic(allow_concurrent: bool = False) -> Dict[str, Any]:
        return _start("basic", allow_concurrent)

    @router.post("/run/vpnlike", response_model=StartResponse)
    def run_vpnlike(allow_concurrent: bool = False) -> Dict[str, Any]:
        return _start("vpnlike", allow_concurrent)

    @router.post("/run/warp", response_model=StartResponse)
    def run_warp(allow_concurrent: bool = False) -> Dict[str, Any]:
        return _start("warp", allow_concurrent)

    @router.post("/run/openvpnlab", response_model=StartResponse)
    def run_openvpnlab(allow_concurrent: bool = False) -> Dict[str, Any]:
        return _start("openvpnlab", allow_concurrent)

    return router

