import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import WarningBox from './WarningBox.jsx';

/**
 * DemoRunnerPanel
 *
 * Self-contained component that drives the local demo runner backend API
 * (POST /demo/run/<name>, GET /demo/jobs/<id>, POST /demo/jobs/<id>/cancel).
 *
 * Used in two places:
 *   - The standalone "Demo Runner" page (pages/DemoRunner.jsx).
 *   - As an inline card on Live VM > PCAP Monitor (pages/LiveVMMonitor.jsx).
 *
 * Props:
 *   compact:  boolean - if true, use a denser layout suitable for embedding
 *                       inside another page (smaller log box, no recent-jobs
 *                       table by default).
 *   showJobs: boolean - explicitly show/hide the recent-jobs table.
 *   onJobFinished: () => void  - called once when an active job transitions
 *                                to a terminal state. Used by PCAP Monitor
 *                                to auto-refresh ingest state.
 */

const STATUS_TONE = {
  pending:   'neutral',
  running:   'warn',
  succeeded: 'ok',
  failed:    'bad',
  cancelled: 'neutral',
};

const TERMINAL_STATUSES = new Set(['succeeded', 'failed', 'cancelled']);

function fmtDuration(s) {
  if (s === null || s === undefined) return '-';
  if (s < 60) return `${s.toFixed(1)} s`;
  const m = Math.floor(s / 60);
  const r = (s - m * 60).toFixed(0);
  return `${m}m ${r}s`;
}
function fmtTs(ts) {
  if (!ts) return '-';
  try { return new Date(ts * 1000).toLocaleTimeString(); }
  catch { return String(ts); }
}

export default function DemoRunnerPanel({
  compact = false,
  showJobs = true,
  onJobFinished,
}) {
  const [allowed,   setAllowed]   = useState(null);
  const [error,     setError]     = useState(null);
  const [busy,      setBusy]      = useState(false);
  const [activeId,  setActiveId]  = useState(null);
  const [activeJob, setActiveJob] = useState(null);
  const [jobs,      setJobs]      = useState([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const logRef       = useRef(null);
  const finishedRef  = useRef(false);

  // ----- initial load: allowed demos + resume any running job -----
  useEffect(() => {
    (async () => {
      try {
        const a = await api.demoAllowed();
        setAllowed(a);
        const j = await api.demoJobs();
        setJobs(j.jobs || []);
        const running = (j.jobs || []).find((x) => x.status === 'running');
        if (running) setActiveId(running.job_id);
      } catch (e) {
        setError(e.message);
      }
    })();
  }, []);

  // ----- polling loop -----
  useEffect(() => {
    if (!activeId) return;
    let cancelled = false;
    finishedRef.current = false;

    async function tick() {
      try {
        const job = await api.demoJob(activeId);
        if (cancelled) return;
        setActiveJob(job);
        if (job.status === 'running' || job.status === 'pending') {
          setTimeout(tick, 2000);
        } else {
          // Refresh the job list once on completion.
          api.demoJobs().then((j) => setJobs(j.jobs || [])).catch(() => {});
          // Notify the parent exactly once that the job is done.
          if (TERMINAL_STATUSES.has(job.status) && !finishedRef.current) {
            finishedRef.current = true;
            if (typeof onJobFinished === 'function') {
              try { onJobFinished(job); } catch { /* ignore */ }
            }
          }
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    }
    tick();
    return () => { cancelled = true; };
  }, [activeId, onJobFinished]);

  // ----- auto-scroll the log panel -----
  useEffect(() => {
    if (!autoScroll || !logRef.current) return;
    logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [activeJob, autoScroll]);

  async function startDemo(name) {
    setError(null);
    setBusy(true);
    try {
      const started = await api.demoRun(name);
      setActiveId(started.job_id);
      setActiveJob({ ...started, logs: [] });
      const j = await api.demoJobs();
      setJobs(j.jobs || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function cancelActive() {
    if (!activeId) return;
    setBusy(true);
    setError(null);
    try {
      const j = await api.demoCancel(activeId);
      setActiveJob({ ...activeJob, ...j });
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function refreshActive() {
    if (!activeId) return;
    try {
      const j = await api.demoJob(activeId);
      setActiveJob(j);
    } catch (e) {
      setError(e.message);
    }
  }

  const status = activeJob?.status;
  const tone   = STATUS_TONE[status] || 'neutral';
  const isRunning = status === 'running' || status === 'pending';
  const logHeight = compact ? 200 : 320;

  return (
    <div>
      <WarningBox tone="warn">
        <strong>Local demo mode.</strong> These buttons start VirtualBox /
        SSH / tcpdump scripts on this machine via local PowerShell.
        Decisions in the backend remain <em>simulation-only</em> &mdash; no
        packets are blocked.
      </WarningBox>

      {error && <div className="error-box">Error: {error}</div>}

      {/* ---- demo buttons ---- */}
      <div className="button-row" style={{ flexWrap: 'wrap', gap: 8 }}>
        {(allowed?.demos || []).map((d) => (
          <button
            key={d.name}
            onClick={() => startDemo(d.name)}
            disabled={busy || isRunning}
            title={`${d.script} ${d.args.join(' ')}`}
          >
            Run {d.label}
          </button>
        ))}
      </div>

      {/* ---- active job status ---- */}
      {activeJob && (
        <div className="section" style={{ marginTop: 12 }}>
          <div
            className="kv"
            style={{ gridTemplateColumns: 'minmax(110px,140px) 1fr', rowGap: 4 }}
          >
            <div className="k">Profile</div>
            <div className="v">
              <strong>{activeJob.label}</strong>{' '}
              <span className="dim" style={{ fontSize: 12 }}>({activeJob.demo})</span>
            </div>

            <div className="k">Status</div>
            <div className="v">
              <span className={`badge ${tone}`}>
                <span className="dot" />
                {activeJob.status}
              </span>
              {activeJob.exit_code !== null && activeJob.exit_code !== undefined && (
                <span className="dim" style={{ marginLeft: 8, fontSize: 12 }}>
                  exit code: <span className="mono">{activeJob.exit_code}</span>
                </span>
              )}
            </div>

            <div className="k">Started</div>
            <div className="v">
              {fmtTs(activeJob.started_at)}
              <span className="dim" style={{ marginLeft: 8, fontSize: 12 }}>
                duration: {fmtDuration(activeJob.duration_s)}
              </span>
            </div>

            <div className="k">Job id</div>
            <div className="v mono" style={{ fontSize: 12 }}>{activeJob.job_id}</div>
          </div>

          {/* Friendly hint once the job has finished. */}
          {TERMINAL_STATUSES.has(status) && (
            <div className="dim" style={{ fontSize: 12, marginTop: 8 }}>
              Check the PCAP Monitor below for updated ingest results.
            </div>
          )}

          {/* ---- log toolbar ---- */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginTop: 10,
              marginBottom: 6,
            }}
          >
            <strong style={{ fontSize: 13 }}>Live log</strong>
            <div className="button-row" style={{ gap: 6 }}>
              <label
                className="dim"
                style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}
              >
                <input
                  type="checkbox"
                  checked={autoScroll}
                  onChange={(e) => setAutoScroll(e.target.checked)}
                />
                Auto-scroll
              </label>
              <button
                className="secondary"
                onClick={refreshActive}
                disabled={busy}
              >
                Refresh
              </button>
              <button
                className="secondary"
                onClick={cancelActive}
                disabled={busy || !isRunning}
              >
                Cancel job
              </button>
            </div>
          </div>

          {/* ---- terminal-style log panel ---- */}
          <div
            ref={logRef}
            className="mono"
            style={{
              background: '#0b1220',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: 10,
              height: logHeight,
              overflow: 'auto',
              fontSize: 12,
              whiteSpace: 'pre-wrap',
              color: '#cbd5e1',
            }}
          >
            {(activeJob.logs || []).length === 0
              ? <span className="dim">(no log lines yet)</span>
              : activeJob.logs.map((line, i) => <div key={i}>{line}</div>)
            }
          </div>
        </div>
      )}

      {/* ---- recent jobs table (only when showJobs) ---- */}
      {showJobs && jobs.length > 0 && (
        <div className="section" style={{ marginTop: 14 }}>
          <strong style={{ fontSize: 13 }}>Recent jobs</strong>
          <div className="table-wrap" style={{ marginTop: 6 }}>
            <table className="dash">
              <thead>
                <tr>
                  <th>Started</th>
                  <th>Demo</th>
                  <th>Status</th>
                  <th>Exit</th>
                  <th>Duration</th>
                  <th>Job id</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.job_id}>
                    <td>{fmtTs(j.started_at)}</td>
                    <td>
                      {j.label}{' '}
                      <span className="dim" style={{ fontSize: 11 }}>({j.demo})</span>
                    </td>
                    <td>{j.status}</td>
                    <td className="num">{j.exit_code ?? '-'}</td>
                    <td className="num">{fmtDuration(j.duration_s)}</td>
                    <td className="mono" style={{ fontSize: 11 }}>{j.job_id}</td>
                    <td>
                      <button
                        className="secondary"
                        onClick={() => setActiveId(j.job_id)}
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="dim" style={{ fontSize: 11, marginTop: 10 }}>
        Allowed demos and their fixed argument lists are defined in{' '}
        <span className="mono">backend/demo_runner.py</span>. The frontend
        cannot influence which scripts run.
      </div>
    </div>
  );
}


