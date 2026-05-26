import React, { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import WarningBox from '../components/WarningBox.jsx';

// ─── helpers ────────────────────────────────────────────────────────────────

function fmt(v, d = 4) {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(d);
  return String(v);
}

function shortTime(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleTimeString(); } catch { return iso; }
}

function labelText(label) {
  if (!label) return '—';
  const u = String(label).toUpperCase();
  if (u === 'BLOCK') return 'SIMULATED BLOCK';
  if (u === 'VPN_LIKE_SIMULATED_BLOCK') return 'VPN_LIKE_SIM.BLOCK';
  return label;
}

function labelCls(label) {
  if (!label) return 'neutral';
  const u = String(label).toUpperCase();
  if (u.includes('BLOCK')) return 'bad';
  if (u.includes('FLAG') || u.includes('REVIEW')) return 'warn';
  return 'ok';
}

function StatTile({ label, value, tone, mono }) {
  return (
    <div className={`lr-stat-tile ${tone || 'neutral'}`}>
      <div className="lr-stat-val">{mono ? <span className="mono">{value}</span> : value}</div>
      <div className="lr-stat-label">{label}</div>
    </div>
  );
}

function Pill({ label }) {
  return (
    <span className={`badge ${labelCls(label)} small-badge`}>
      <span className="dot" />
      {labelText(label)}
    </span>
  );
}

// ─── events table ───────────────────────────────────────────────────────────

const EVENT_COLS = [
  { key: 'event_time',    label: 'Time',     render: (v) => shortTime(v) },
  { key: 'batch_index',   label: 'Batch' },
  { key: 'session_id',    label: 'Session',  mono: true },
  { key: 'flow_id',       label: 'Flow',     mono: true },
  { key: 'src_ip',        label: 'Src IP',   mono: true },
  { key: 'dst_ip',        label: 'Dst IP',   mono: true },
  { key: 'protocol',      label: 'Proto',    mono: true },
  { key: 'dst_port',      label: 'Port',     mono: true },
  { key: 'scenario',      label: 'Scenario', mono: true },
  { key: 'session_score', label: 'Score',    render: (v) => fmt(v) },
  { key: 'action_label',  label: 'Label',    badge: true },
  { key: 'action',        label: 'Action',   badge: true },
];

function EventsTable({ events }) {
  if (!events || events.length === 0) {
    return (
      <div className="muted" style={{ fontSize: 13 }}>
        No events yet. Run the PCAP streamer:
        <code className="mono" style={{ marginLeft: 6 }}>
          python tools/pcap_to_live_stream.py --pcap captures\vm_test.pcap --api http://127.0.0.1:8765
        </code>
      </div>
    );
  }
  const rows = [...events].reverse();
  const optKeys = ['flow_id', 'src_ip', 'dst_ip', 'protocol', 'dst_port', 'scenario'];
  const present = new Set(optKeys.filter((k) => rows.some((r) => r[k] !== undefined && r[k] !== null)));
  const cols = EVENT_COLS.filter((c) => !optKeys.includes(c.key) || present.has(c.key));

  return (
    <div className="table-wrap">
      <table className="dash" style={{ fontSize: 12 }}>
        <thead><tr>{cols.map((c) => <th key={c.key}>{c.label}</th>)}</tr></thead>
        <tbody>
          {rows.map((ev, i) => (
            <tr key={i}>
              {cols.map((c) => {
                const val = ev[c.key];
                if (c.badge) {
                  return <td key={c.key}>{val ? <Pill label={val} /> : <span className="muted">—</span>}</td>;
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

// ─── active sessions ────────────────────────────────────────────────────────

function ActiveSessions({ sessions }) {
  if (!sessions || sessions.length === 0) {
    return <div className="muted" style={{ fontSize: 13 }}>No active sessions yet.</div>;
  }
  return (
    <div className="table-wrap">
      <table className="dash" style={{ fontSize: 12 }}>
        <thead>
          <tr>
            <th>Session ID</th><th>Flows</th><th>Score</th>
            <th>Label</th><th>Action</th><th>✓ Sim</th>
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

// ─── main page ──────────────────────────────────────────────────────────────

const POLL_MS = 2000;

export default function LiveVMMonitor() {
  const [state, setState]         = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [resetting, setResetting] = useState(false);

  const mountedRef = useRef(true);
  const timerRef   = useRef(null);

  const fetchState = useCallback(async () => {
    try {
      const s = await api.liveIngestState();
      if (mountedRef.current) {
        setState(s);
        setLoadError(null);
      }
    } catch (e) {
      if (mountedRef.current) setLoadError(e.message);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    fetchState();
    timerRef.current = setInterval(fetchState, POLL_MS);
    return () => {
      mountedRef.current = false;
      clearInterval(timerRef.current);
    };
  }, [fetchState]);

  async function doReset() {
    if (!window.confirm('Clear all ingested PCAP batches and session state?')) return;
    setResetting(true);
    try {
      await api.liveIngestReset();
      await fetchState();
    } catch (e) {
      setLoadError(e.message);
    } finally {
      setResetting(false);
    }
  }

  const counts    = state?.counts ?? { PASS: 0, FLAG_REVIEW: 0, BLOCK: 0 };
  const lc        = state?.labelled_counts ?? { BENIGN_LIKE: 0, FLAGGED_FOR_REVIEW: 0, VPN_LIKE_SIMULATED_BLOCK: 0 };
  const hasData   = (state?.total_batches ?? 0) > 0;

  return (
    <div>
      {/* ── header ── */}
      <div className="page-header">
        <div>
          <h1>Live VM Monitor</h1>
          <div className="subtitle">
            Near-real-time view of PCAP-derived flow features streamed by
            <code className="mono" style={{ margin: '0 4px' }}>tools/pcap_to_live_stream.py</code>
            into <code className="mono">POST /firewall/live-ingest</code>.
          </div>
        </div>
        {hasData && (
          <span className="badge ok">
            <span className="dot" />
            INGESTING ({state.total_batches} batch{state.total_batches === 1 ? '' : 'es'})
          </span>
        )}
      </div>

      {/* ── safety ── */}
      <WarningBox tone="warn">
        <strong>Simulation only.</strong> This page displays results from a host-side
        script that reads <strong>existing PCAP files only</strong>. The web app does not
        sniff live traffic and <strong>no packets are blocked</strong>. All labels are
        from <span className="mono">robust9_firewall</span> and are simulated.
      </WarningBox>

      {/* ── controls ── */}
      <div className="section card">
        <h2 style={{ marginTop: 0 }}>Controls</h2>
        <div className="lr-controls-row">
          <button type="button" className="secondary" onClick={fetchState}>
            ↺ Refresh now
          </button>
          <button
            type="button"
            className="secondary"
            onClick={doReset}
            disabled={resetting || !hasData}
            style={{ borderColor: 'rgba(239,68,68,0.5)', color: '#f87171' }}
          >
            {resetting ? <><span className="spinner" /> Resetting…</> : '✗ Reset ingest state'}
          </button>
          <span className="muted" style={{ fontSize: 12 }}>
            Auto-refreshes every {POLL_MS / 1000}s
          </span>
        </div>

        {loadError && (
          <div className="error-box" style={{ marginTop: 10 }}>
            API error: {loadError}
          </div>
        )}
        {!hasData && !loadError && (
          <div className="warning-box info" style={{ marginTop: 10 }}>
            <span className="icon">ℹ</span>
            No batches received yet. Start streaming with:
            <pre className="mono" style={{ marginTop: 6, fontSize: 11 }}>
{`python tools/pcap_to_live_stream.py \\
  --pcap captures\\vm_test.pcap \\
  --api http://127.0.0.1:8765 \\
  --batch-size 5 --delay-seconds 2 \\
  --scenario vm_test`}
            </pre>
          </div>
        )}
      </div>

      {/* ── stat tiles ── */}
      {state && (
        <div className="section">
          <div
            style={{
              fontSize: 12, fontWeight: 600, color: 'var(--text-dim)',
              textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 10,
            }}
          >
            Ingest status
          </div>

          <div className="lr-stats-grid">
            <StatTile label="Model"          value={state.model_id || 'robust9_firewall'} mono tone="info" />
            <StatTile label="Action mode"    value={state.action_mode || 'simulation'}     mono tone="info" />
            <StatTile label="Total batches"  value={state.total_batches ?? 0} />
            <StatTile label="Total flows"    value={state.total_flows ?? 0} />
            <StatTile label="Total sessions" value={state.total_sessions ?? 0} />
            <StatTile label="PASS"           value={counts.PASS}        tone="ok" />
            <StatTile label="FLAG_REVIEW"    value={counts.FLAG_REVIEW} tone="warn" />
            <StatTile label="BLOCK"          value={counts.BLOCK}       tone="bad" />
            <StatTile label="BENIGN_LIKE"           value={lc.BENIGN_LIKE}              tone="ok" />
            <StatTile label="FLAGGED_FOR_REVIEW"    value={lc.FLAGGED_FOR_REVIEW}       tone="warn" />
            <StatTile label="VPN SIM.BLOCK"         value={lc.VPN_LIKE_SIMULATED_BLOCK} tone="bad" />
          </div>

          <div className="dim" style={{ fontSize: 11, marginTop: 10 }}>
            Started: <span className="mono">{state.started_at || '—'}</span>
            {' · '}
            Updated: <span className="mono">{state.updated_at || '—'}</span>
          </div>

          {state.warnings && state.warnings.length > 0 && (
            <div className="dim" style={{ fontSize: 11, marginTop: 6 }}>
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
                {' '}({state.recent_events.length} shown, newest first)
              </span>
            )}
          </h1>
        </div>
        <EventsTable events={state?.recent_events} />
      </div>

      <div className="mm-page-footer">
        Live VM Monitor is simulation-only. Decisions come from
        <code className="mono" style={{ margin: '0 4px' }}>robust9_firewall</code>
        and have no effect on network traffic. No packets are captured or blocked
        by the web application.
      </div>
    </div>
  );
}

