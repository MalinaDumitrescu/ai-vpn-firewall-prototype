import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import WarningBox from '../components/WarningBox.jsx';

// ─── tiny helpers ────────────────────────────────────────────────────────────

function fmt(v, d = 4) {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(d);
  return String(v);
}

function shortTime(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleTimeString(); } catch { return iso; }
}

/** Label / action → CSS class */
function labelCls(label) {
  if (!label) return 'neutral';
  const u = String(label).toUpperCase();
  if (u.includes('BLOCK') || u === 'BLOCK') return 'bad';
  if (u.includes('FLAG') || u.includes('REVIEW')) return 'warn';
  return 'ok';
}

/** Displayed text for the simulated label */
function labelText(label) {
  if (!label) return '—';
  const u = String(label).toUpperCase();
  if (u === 'BLOCK') return 'SIMULATED BLOCK';
  if (u === 'VPN_LIKE_SIMULATED_BLOCK') return 'VPN_LIKE_SIM.BLOCK';
  return label;
}

/** Single stat tile */
function StatTile({ label, value, tone, mono }) {
  const cls = tone || 'neutral';
  return (
    <div className={`lr-stat-tile ${cls}`}>
      <div className="lr-stat-val">{mono ? <span className="mono">{value}</span> : value}</div>
      <div className="lr-stat-label">{label}</div>
    </div>
  );
}

/** Inline badge */
function Pill({ label, tone }) {
  const cls = tone || labelCls(label);
  return (
    <span className={`badge ${cls} small-badge`}>
      <span className="dot" />
      {labelText(label)}
    </span>
  );
}

/** Progress bar */
function ProgressBar({ pct }) {
  const p = Math.min(100, Math.max(0, pct || 0));
  return (
    <div className="lr-progress-track">
      <div className="lr-progress-fill" style={{ width: `${p}%` }} />
      <span className="lr-progress-label">{p.toFixed(1)}%</span>
    </div>
  );
}

// ─── pipeline diagram ─────────────────────────────────────────────────────────

function PipelineDiagram() {
  const steps = [
    { icon: '🖥', label: 'VM traffic' },
    { icon: '📄', label: 'Feature CSV' },
    { icon: '▶', label: 'Replay batches' },
    { icon: '🔍', label: 'robust9 analysis (legacy)' },
    { icon: '🏷', label: 'Simulated labels' },
  ];
  return (
    <div className="lr-pipeline">
      {steps.map((s, i) => (
        <React.Fragment key={s.label}>
          <div className="lr-pipeline-step">
            <div className="lr-pipeline-icon">{s.icon}</div>
            <div className="lr-pipeline-label">{s.label}</div>
          </div>
          {i < steps.length - 1 && <div className="lr-pipeline-arrow">→</div>}
        </React.Fragment>
      ))}
    </div>
  );
}

// ─── events table ─────────────────────────────────────────────────────────────

const EVENT_COLS = [
  { key: 'event_time',   label: 'Time',       render: (v) => shortTime(v) },
  { key: 'batch_index',  label: 'Batch' },
  { key: 'session_id',   label: 'Session',    mono: true },
  { key: 'flow_id',      label: 'Flow',       mono: true },
  { key: 'src_ip',       label: 'Src IP',     mono: true },
  { key: 'dst_ip',       label: 'Dst IP',     mono: true },
  { key: 'protocol',     label: 'Proto',      mono: true },
  { key: 'dst_port',     label: 'Port',       mono: true },
  { key: 'scenario',     label: 'Scenario',   mono: true },
  { key: 'session_score',label: 'Score',      render: (v) => fmt(v) },
  { key: 'action_label', label: 'Label',      badge: true },
  { key: 'action',       label: 'Action',     badge: true },
  { key: 'simulated',    label: '✓ Sim',
    render: (v) => v ? <span className="badge ok small-badge"><span className="dot"/>yes</span>
                     : <span className="badge bad small-badge"><span className="dot"/>no</span> },
];

function EventsTable({ events }) {
  if (!events || events.length === 0) {
    return <div className="muted" style={{ fontSize: 13 }}>No events yet. Upload a CSV and step through batches.</div>;
  }
  // Show most recent first.
  const rows = [...events].reverse();
  // Determine which optional columns actually have values.
  const optKeys = ['flow_id', 'src_ip', 'dst_ip', 'protocol', 'dst_port', 'scenario'];
  const presentOpts = new Set(optKeys.filter((k) => rows.some((r) => r[k] !== undefined && r[k] !== null)));
  const cols = EVENT_COLS.filter((c) => !optKeys.includes(c.key) || presentOpts.has(c.key));

  return (
    <div className="table-wrap">
      <table className="dash" style={{ fontSize: 12 }}>
        <thead>
          <tr>{cols.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((ev, i) => (
            <tr key={i}>
              {cols.map((c) => {
                const val = ev[c.key];
                if (c.badge) {
                  return (
                    <td key={c.key}>
                      {val ? <Pill label={val} /> : <span className="muted">—</span>}
                    </td>
                  );
                }
                if (c.render) return <td key={c.key}>{c.render(val)}</td>;
                if (val === undefined || val === null) return <td key={c.key} className="muted">—</td>;
                return <td key={c.key} className={c.mono ? 'mono' : ''}>{String(val)}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── active sessions table ───────────────────────────────────────────────────

function ActiveSessions({ sessions }) {
  if (!sessions || sessions.length === 0) {
    return <div className="muted" style={{ fontSize: 13 }}>No active sessions yet.</div>;
  }
  return (
    <div className="table-wrap">
      <table className="dash" style={{ fontSize: 12 }}>
        <thead>
          <tr>
            <th>Session ID</th>
            <th>Flows</th>
            <th>Score</th>
            <th>Label</th>
            <th>Action</th>
            <th>✓ Sim</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr key={s.session_id}>
              <td className="mono">{s.session_id}</td>
              <td className="num">{s.n_flows}</td>
              <td className="num"><strong>{fmt(s.session_score)}</strong></td>
              <td><Pill label={s.label} /></td>
              <td>
                <span className={`action-pill ${s.action}`}>
                  {s.action === 'BLOCK' ? 'SIMULATED BLOCK' : s.action}
                </span>
              </td>
              <td>
                {s.simulated
                  ? <span className="badge ok small-badge"><span className="dot"/>yes</span>
                  : <span className="badge bad small-badge"><span className="dot"/>no</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── main page ────────────────────────────────────────────────────────────────

const POLL_MS    = 2000;  // state poll interval
const AUTO_MS    = 2000;  // auto-play step interval
const MIN_GAP_MS = 1000;  // minimum between any two requests

export default function LiveVMReplay() {
  // Remote state mirror.
  const [state,       setState]       = useState(null);
  const [loadError,   setLoadError]   = useState(null);

  // Upload.
  const fileRef    = useRef(null);
  const [fileName,    setFileName]    = useState('');
  const [uploadMeta,  setUploadMeta]  = useState(null);   // success metadata
  const [uploadError, setUploadError] = useState(null);
  const [uploading,   setUploading]   = useState(false);

  // Replay controls.
  const [batchSize,   setBatchSize]   = useState(5);
  const [stepping,    setStepping]    = useState(false);
  const [autoPlay,    setAutoPlay]    = useState(false);
  const [stateError,  setStateError]  = useState(null);

  // Timestamps to enforce MIN_GAP_MS.
  const lastRequestRef = useRef(0);
  const autoTimerRef   = useRef(null);
  const pollTimerRef   = useRef(null);
  const mountedRef     = useRef(true);

  // ── helpers ──

  function safe(fn) {
    // Wrap fn to only update state if still mounted.
    return (...args) => { if (mountedRef.current) fn(...args); };
  }

  async function throttled(fn) {
    const now = Date.now();
    const gap = now - lastRequestRef.current;
    if (gap < MIN_GAP_MS) await new Promise((r) => setTimeout(r, MIN_GAP_MS - gap));
    lastRequestRef.current = Date.now();
    return fn();
  }

  // ── state poll ──

  const fetchState = useCallback(async () => {
    try {
      const s = await throttled(() => api.liveReplayState());
      safe(setState)(s);
      safe(setLoadError)(null);
    } catch (e) {
      safe(setLoadError)(e.message);
    }
  }, []); // eslint-disable-line

  useEffect(() => {
    mountedRef.current = true;
    fetchState();
    pollTimerRef.current = setInterval(fetchState, POLL_MS);
    return () => {
      mountedRef.current = false;
      clearInterval(pollTimerRef.current);
      clearInterval(autoTimerRef.current);
    };
  }, []); // eslint-disable-line

  // ── auto-play ──

  useEffect(() => {
    clearInterval(autoTimerRef.current);
    if (autoPlay) {
      autoTimerRef.current = setInterval(async () => {
        if (!mountedRef.current) return;
        // Stop auto-play when finished.
        if (state?.finished) { setAutoPlay(false); return; }
        if (!state?.loaded)  { setAutoPlay(false); return; }
        await doStep();
      }, AUTO_MS);
    }
    return () => clearInterval(autoTimerRef.current);
  }, [autoPlay, state?.finished, state?.loaded]); // eslint-disable-line

  // ── actions ──

  async function doUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploadError(null); setUploadMeta(null); setUploading(true);
    try {
      const meta = await throttled(() => api.liveReplayUpload(file));
      setUploadMeta(meta);
      await fetchState();
    } catch (e) {
      setUploadError(e.message);
    } finally { setUploading(false); }
  }

  async function doStep() {
    if (state?.finished) return;
    setStepping(true); setStateError(null);
    try {
      const s = await throttled(() => api.liveReplayStep(batchSize));
      setState(s);
    } catch (e) { setStateError(e.message); }
    finally { setStepping(false); }
  }

  async function doReset() {
    setAutoPlay(false);
    setUploadMeta(null); setUploadError(null); setFileName('');
    if (fileRef.current) fileRef.current.value = '';
    try {
      await throttled(() => api.liveReplayReset());
      await fetchState();
    } catch (e) { setStateError(e.message); }
  }

  // ── derived ──

  const loaded   = state?.loaded   ?? false;
  const running  = state?.running  ?? false;
  const finished = state?.finished ?? false;
  const lc       = state?.labelled_counts ?? { BENIGN_LIKE: 0, FLAGGED_FOR_REVIEW: 0, VPN_LIKE_SIMULATED_BLOCK: 0 };
  const pct      = state?.progress_percent ?? 0;

  // ── render ──────────────────────────────────────────────────────────────────

  return (
    <div>
      {/* ── header ── */}
      <div className="page-header">
        <div>
          <h1>CSV replay</h1>
          <div className="subtitle">
            Replay a VM-exported feature CSV as near-real-time traffic. The app
            labels sessions but does <strong>not</strong> block packets.
          </div>
        </div>
        {loaded && !finished && (
          <span className="badge ok">
            <span className="dot" />
            {autoPlay ? 'AUTO-PLAYING' : 'LOADED'}
          </span>
        )}
        {finished && <span className="badge neutral"><span className="dot" />FINISHED</span>}
      </div>

      {/* ── safety warning ── */}
      <WarningBox tone="warn">
        <strong>Simulation only.</strong> This page replays uploaded feature rows
        and labels them using <span className="mono">robust9_firewall</span>{' '}
        (legacy baseline — compatible with 9-feature PCAP CSV uploads).
        <strong> No packets are captured or blocked.</strong> All results are
        labelled <em>simulated</em> and have no effect on any network.
        The recommended model is <span className="mono">full_canonical__lgbm</span>.
      </WarningBox>

      {/* ── pipeline ── */}
      <div className="section">
        <PipelineDiagram />
      </div>

      {/* ── upload section ── */}
      <div className="section card">
        <h2 style={{ marginTop: 0 }}>Upload replay CSV</h2>

        <div className="lr-upload-row">
          <label className="mm-file-label" style={{ cursor: 'pointer' }}>
            <input
              ref={fileRef}
              type="file"
              accept=".csv"
              style={{ display: 'none' }}
              onChange={(e) => {
                setFileName(e.target.files?.[0]?.name || '');
                setUploadMeta(null);
                setUploadError(null);
              }}
            />
            <span className="button secondary">📂 Choose CSV</span>
            {fileName
              ? <span className="mono" style={{ fontSize: 12 }}>{fileName}</span>
              : <span className="muted" style={{ fontSize: 12 }}>No file selected</span>
            }
          </label>

          <button type="button" onClick={doUpload} disabled={uploading || !fileName}>
            {uploading ? <><span className="spinner" /> Uploading…</> : '⬆ Upload replay CSV'}
          </button>

          <a
            href={api.liveReplayTemplateUrl()}
            download="live_replay_template.csv"
            className="button secondary"
            style={{ textDecoration: 'none', fontSize: 13, padding: '9px 14px' }}
          >
            ⬇ Download template
          </a>
        </div>

        {/* upload success */}
        {uploadMeta && (
          <div className="warning-box ok" style={{ marginTop: 12 }}>
            <span className="icon">✓</span>
            <div>
              <strong>{uploadMeta.uploaded_filename}</strong> — {uploadMeta.total_rows} rows,{' '}
              {uploadMeta.detected_sessions} sessions detected.
              {uploadMeta.optional_columns_detected?.length > 0 && (
                <span className="dim"> Optional cols: {uploadMeta.optional_columns_detected.join(', ')}</span>
              )}
            </div>
          </div>
        )}

        {/* upload error */}
        {uploadError && (
          <div className="error-box" style={{ marginTop: 12 }}>
            <strong>Upload failed:</strong> {uploadError}
          </div>
        )}
      </div>

      {/* ── replay controls ── */}
      <div className="section card">
        <h2 style={{ marginTop: 0 }}>Replay controls</h2>

        <div className="lr-controls-row">
          <div className="lr-batch-ctrl">
            <label style={{ fontSize: 12, color: 'var(--text-dim)' }}>Batch size</label>
            <input
              type="number"
              min={1} max={500}
              value={batchSize}
              onChange={(e) => setBatchSize(Math.max(1, parseInt(e.target.value, 10) || 5))}
              className="lr-batch-input"
            />
          </div>

          <button
            type="button"
            onClick={doStep}
            disabled={stepping || !loaded || finished || autoPlay}
          >
            {stepping ? <><span className="spinner" /> Stepping…</> : '▷ Step next batch'}
          </button>

          <button
            type="button"
            className={autoPlay ? '' : 'secondary'}
            onClick={() => {
              if (!loaded) return;
              setAutoPlay((v) => !v);
            }}
            disabled={!loaded || finished}
            style={autoPlay ? { background: 'var(--ok)', borderColor: 'var(--ok)' } : {}}
          >
            {autoPlay ? '⏸ Pause auto-play' : '⏵ Start auto-play'}
          </button>

          <button type="button" className="secondary" onClick={fetchState}>
            ↺ Refresh
          </button>

          <button type="button" className="secondary" onClick={doReset}
            style={{ borderColor: 'rgba(239,68,68,0.5)', color: '#f87171' }}>
            ✗ Reset
          </button>
        </div>

        {!loaded && (
          <div className="warning-box info" style={{ marginTop: 10 }}>
            <span className="icon">ℹ</span>
            Upload a CSV first, then use the controls above to step through batches.
          </div>
        )}
        {finished && (
          <div className="warning-box ok" style={{ marginTop: 10 }}>
            <span className="icon">✓</span>
            Replay finished — all {state?.total_rows} rows processed. Click Reset to start over.
          </div>
        )}
        {stateError && (
          <div className="error-box" style={{ marginTop: 10 }}>{stateError}</div>
        )}
        {loadError && (
          <div className="error-box" style={{ marginTop: 10 }}>
            API error: {loadError}
          </div>
        )}
      </div>

      {/* ── status cards ── */}
      {state && (
        <div className="section">
          <div
            style={{
              fontSize: 12, fontWeight: 600, color: 'var(--text-dim)',
              textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10,
            }}
          >
            Live status
          </div>

          {/* Progress bar */}
          <div className="card" style={{ marginBottom: 12, padding: '12px 16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 12, color: 'var(--text-dim)' }}>
              <span>Replay progress</span>
              <span>{state.replay_pointer} / {state.total_rows} rows</span>
            </div>
            <ProgressBar pct={pct} />
          </div>

          {/* Stat tiles */}
          <div className="lr-stats-grid">
            <StatTile label="Model"          value={state.model_id}      mono tone="info" />
            <StatTile label="Action mode"    value={state.action_mode}   mono tone="info" />
            <StatTile label="Batches"        value={state.total_batches_processed} />
            <StatTile label="Flows processed"value={state.total_flows_processed} />
            <StatTile label="Sessions seen"  value={state.total_sessions_seen} />
            <StatTile label="BENIGN_LIKE"    value={lc.BENIGN_LIKE}      tone="ok" />
            <StatTile label="FLAGGED_FOR_REVIEW" value={lc.FLAGGED_FOR_REVIEW} tone="warn" />
            <StatTile label="VPN SIM.BLOCK"  value={lc.VPN_LIKE_SIMULATED_BLOCK} tone="bad" />
          </div>

          {/* Warnings from backend */}
          {state.warnings && state.warnings.length > 0 && (
            <div className="dim" style={{ fontSize: 11, marginTop: 8 }}>
              {state.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
            </div>
          )}
        </div>
      )}

      {/* ── active sessions ── */}
      {state?.active_sessions?.length > 0 && (
        <div className="section">
          <div className="page-header" style={{ marginBottom: 8 }}>
            <h1 style={{ fontSize: 15 }}>
              Active sessions ({state.active_sessions.length})
            </h1>
          </div>
          <ActiveSessions sessions={state.active_sessions} />
        </div>
      )}

      {/* ── recent events ── */}
      <div className="section">
        <div className="page-header" style={{ marginBottom: 8 }}>
          <h1 style={{ fontSize: 15 }}>
            Recent events
            {state?.recent_events?.length > 0 && (
              <span className="dim" style={{ fontWeight: 400, fontSize: 12 }}>
                {' '}({Math.min(state.recent_events.length, 200)} shown, newest first)
              </span>
            )}
          </h1>
        </div>
        <EventsTable events={state?.recent_events} />
      </div>

      {/* ── footer ── */}
      <div className="mm-page-footer">
        Live VM Replay is simulation-only. robust9_firewall (legacy baseline) labels are simulated
        and have no effect on network traffic. No packets are captured or blocked.
        Recommended model: full_canonical__lgbm.
      </div>
    </div>
  );
}

