import React, { useEffect, useRef, useState, useMemo } from 'react';
import { api } from '../api.js';
import WarningBox from '../components/WarningBox.jsx';

// ─── constants ────────────────────────────────────────────────────────────────

const EXECUTABLE_ID = 'full_canonical__lgbm';

const BENCHMARK_COMPATIBLE_IDS = [
  'full_canonical__lgbm',
  'robust9_firewall',
  'balanced_bagging_3ds_reference',
  'balanced_bagging_baseline',
];

const FLOW_PAGE_SIZE    = 50;
const SESSION_PAGE_SIZE = 50;

// ─── helpers ──────────────────────────────────────────────────────────────────

function fmt(v, d = 4) {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return v.toString();
    return v.toFixed(d);
  }
  return String(v);
}

function pct(v) {
  if (v === null || v === undefined) return '—';
  return (v * 100).toFixed(1) + '%';
}

function roleBadgeLabel(modelId, role, status) {
  if (modelId === EXECUTABLE_ID) return 'EXECUTABLE FIREWALL';
  if (BENCHMARK_COMPATIBLE_IDS.includes(modelId)) return 'BENCHMARK COMPAT';
  if (status === 'negative_control') return 'NEGATIVE CONTROL';
  if (status === 'research_only') return 'RESEARCH ONLY';
  if (status === 'unsupported') return 'UNSUPPORTED';
  if (status === 'alias') return 'ALIAS';
  return 'COMPARISON ONLY';
}

function roleBadgeTone(modelId, role, status) {
  if (modelId === EXECUTABLE_ID) return 'ok';
  if (BENCHMARK_COMPATIBLE_IDS.includes(modelId)) return 'info';
  if (status === 'negative_control') return 'warn';
  if (status === 'research_only') return 'warn';
  return 'neutral';
}

function reasonNotSelectable(modelId, entry) {
  if (BENCHMARK_COMPATIBLE_IDS.includes(modelId)) return null;
  const status = entry?.status || '';
  if (['balanced_bagging_xgb_baseline', 'robust13_comparison'].includes(modelId))
    return 'Requires session-derived probability features absent from raw-feature CSV.';
  if (status === 'negative_control' || modelId.startsWith('lodo_'))
    return 'Negative-control LODO model — different feature schema.';
  if (status === 'research_only' || modelId.includes('dann'))
    return 'Research-only DANN model — not compatible with benchmark CSV.';
  if (status === 'unsupported' || status === 'alias')
    return 'Unsupported/documentation-only artifact.';
  return 'Not compatible with the shared raw-feature benchmark CSV.';
}

// ─── CSV download helper ──────────────────────────────────────────────────────

function downloadCsv(rows, filename) {
  if (!rows || rows.length === 0) return;
  const keys = Object.keys(rows[0]);
  const escape = (v) => {
    if (v === null || v === undefined) return '';
    const s = String(v);
    if (s.includes(',') || s.includes('"') || s.includes('\n'))
      return '"' + s.replace(/"/g, '""') + '"';
    return s;
  };
  const csv = [keys.join(','), ...rows.map(r => keys.map(k => escape(r[k])).join(','))].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

// ─── ErrorTypeBadge ───────────────────────────────────────────────────────────

function ErrorTypeBadge({ et }) {
  if (!et) return <span className="dim">—</span>;
  const toneMap = { TP: 'ok', TN: 'ok', FP: 'bad', FN: 'bad', unknown_label: 'neutral' };
  const tone = toneMap[et] || 'neutral';
  return (
    <span className={`badge ${tone} small-badge`} style={{ fontSize: 10 }}>
      <span className="dot" />{et === 'unknown_label' ? 'unkn' : et}
    </span>
  );
}

// ─── ModelCard ────────────────────────────────────────────────────────────────

function ModelCard({ modelId, entry, permissions, selected, onToggle }) {
  const isCompat   = BENCHMARK_COMPATIBLE_IDS.includes(modelId);
  const isExec     = modelId === EXECUTABLE_ID;
  const perm       = permissions?.[modelId] || {};
  const status     = perm.status || entry?.status || '';
  const role       = perm.role   || entry?.role   || '';
  const reason     = perm.reason_not_selectable || reasonNotSelectable(modelId, entry);
  const featureCount = perm.feature_count ?? perm.n_features ?? entry?.n_features ?? '?';
  const probCol    = perm.probability_column || entry?.selected_probability_column || '?';
  const agg        = perm.aggregation || entry?.selected_aggregation || '?';

  const badgeLabel = roleBadgeLabel(modelId, role, status);
  const badgeTone  = roleBadgeTone(modelId, role, status);

  return (
    <div style={{
      background: isCompat ? 'var(--bg-1)' : 'var(--bg-0)',
      border: `1px solid ${isCompat ? (isExec ? 'rgba(79,157,255,0.4)' : 'var(--border-strong)') : 'var(--border)'}`,
      borderRadius: 10, padding: '12px 14px',
      display: 'flex', flexDirection: 'column', gap: 7,
      opacity: isCompat ? 1 : 0.6,
    }}>
      {/* Header: checkbox + model ID */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        <label style={{ display: 'flex', alignItems: 'center', paddingTop: 2, cursor: isCompat ? 'pointer' : 'not-allowed', flexShrink: 0 }}>
          <input
            type="checkbox"
            checked={isCompat ? selected : false}
            disabled={!isCompat}
            onChange={() => isCompat && onToggle(modelId)}
            style={{ cursor: isCompat ? 'pointer' : 'not-allowed', width: 14, height: 14 }}
          />
        </label>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div className="mono" style={{ fontSize: 12, fontWeight: 700, wordBreak: 'break-all', color: isCompat ? 'var(--text)' : 'var(--text-dim)', lineHeight: 1.3 }}>
            {modelId}
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 5 }}>
            <span className={`badge ${badgeTone} small-badge`} style={{ fontSize: 10 }}>
              <span className="dot" />{badgeLabel}
            </span>
            {!isCompat && (
              <span className="badge neutral small-badge" style={{ fontSize: 10 }}>
                <span className="dot" />READ-ONLY
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Metadata */}
      <div style={{ fontSize: 11, color: 'var(--text-dim)', display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span><span style={{ color: 'var(--text-mute)' }}>features:</span> {featureCount}</span>
        <span><span style={{ color: 'var(--text-mute)' }}>prob col:</span> <span className="mono">{probCol}</span></span>
        <span><span style={{ color: 'var(--text-mute)' }}>aggregation:</span> <span className="mono">{agg}</span></span>
      </div>

      {/* Reason not selectable */}
      {!isCompat && reason && (
        <div style={{ fontSize: 11, color: 'var(--text-mute)', fontStyle: 'italic', borderTop: '1px solid var(--border)', paddingTop: 6 }}>
          {reason}
        </div>
      )}
    </div>
  );
}

// ─── ModelSummaryTable ────────────────────────────────────────────────────────

const SUMMARY_COLS = [
  { key: 'model_id',      label: 'Model' },
  { key: 'role',          label: 'Role' },
  { key: 'exec',          label: 'Exec' },
  { key: 'features',      label: 'Feats' },
  { key: 'prob_col',      label: 'Prob col' },
  { key: 'agg',           label: 'Agg' },
  { key: 'threshold',     label: 'Threshold' },
  { key: 'auc',           label: 'AUC' },
  { key: 'tp',            label: 'TP' },
  { key: 'fp',            label: 'FP' },
  { key: 'tn',            label: 'TN' },
  { key: 'fn',            label: 'FN' },
  { key: 'precision',     label: 'Precision' },
  { key: 'recall',        label: 'Recall' },
  { key: 'fpr',           label: 'FPR' },
  { key: 'accuracy',      label: 'Accuracy' },
  { key: 'rows_used',     label: 'Rows' },
  { key: 'captures_used', label: 'Captures' },
  { key: 'warning',       label: 'Note' },
];

function ModelSummaryTable({ results }) {
  if (!results || results.length === 0) return <div className="dim">No results.</div>;
  return (
    <div className="table-wrap">
      <table className="dash" style={{ minWidth: 1100 }}>
        <thead>
          <tr>{SUMMARY_COLS.map(c => <th key={c.key}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {results.map(r => {
            const isExec    = r.model_id === EXECUTABLE_ID;
            const isSkipped = r.skipped;
            const auc = r.auc ?? r.AUC;
            return (
              <tr
                key={r.model_id}
                style={isExec ? { background: 'rgba(79,157,255,0.06)' } : isSkipped ? { opacity: 0.55 } : {}}
              >
                {SUMMARY_COLS.map(c => {
                  if (c.key === 'model_id') return (
                    <td key={c.key} className="mono" style={{ fontWeight: isExec ? 700 : 400, whiteSpace: 'nowrap' }}>
                      {r.model_id}
                      {isExec && <span className="badge ok small-badge" style={{ marginLeft: 5, fontSize: 9 }}><span className="dot" />FIREWALL</span>}
                      {isSkipped && <span className="badge warn small-badge" style={{ marginLeft: 5, fontSize: 9 }}><span className="dot" />skipped</span>}
                    </td>
                  );
                  if (c.key === 'role')      return <td key={c.key} style={{ fontSize: 11 }}>{r.role || '—'}</td>;
                  if (c.key === 'exec')      return <td key={c.key} style={{ color: r.executable ? 'var(--ok)' : 'var(--text-dim)', fontSize: 11 }}>{r.executable ? '✓' : '✗'}</td>;
                  if (c.key === 'features')  return <td key={c.key} className="num">{r.feature_count ?? '—'}</td>;
                  if (c.key === 'prob_col')  return <td key={c.key} className="mono" style={{ fontSize: 11 }}>{r.probability_column || '—'}</td>;
                  if (c.key === 'agg')       return <td key={c.key} className="mono" style={{ fontSize: 11 }}>{r.aggregation || '—'}</td>;
                  if (c.key === 'threshold') return <td key={c.key} className="num">{r.block_threshold_used != null ? fmt(r.block_threshold_used) : '—'}</td>;
                  if (c.key === 'auc') return (
                    <td key={c.key} className="num" style={{ color: auc != null ? 'var(--ok)' : 'var(--text-dim)', fontWeight: 700 }}>
                      {auc != null ? fmt(auc) : '—'}
                    </td>
                  );
                  if (c.key === 'tp') return <td key={c.key} className="num" style={{ color: r.tp > 0 ? 'var(--ok)' : undefined }}>{r.tp ?? '—'}</td>;
                  if (c.key === 'tn') return <td key={c.key} className="num" style={{ color: r.tn > 0 ? 'var(--ok)' : undefined }}>{r.tn ?? '—'}</td>;
                  if (c.key === 'fp') return <td key={c.key} className="num" style={{ color: r.fp > 0 ? 'var(--bad)' : undefined }}>{r.fp ?? '—'}</td>;
                  if (c.key === 'fn') return <td key={c.key} className="num" style={{ color: r.fn > 0 ? 'var(--bad)' : undefined }}>{r.fn ?? '—'}</td>;
                  if (c.key === 'precision') return <td key={c.key} className="num">{pct(r.precision)}</td>;
                  if (c.key === 'recall')    return <td key={c.key} className="num">{pct(r.recall)}</td>;
                  if (c.key === 'fpr')       return <td key={c.key} className="num">{pct(r.fpr)}</td>;
                  if (c.key === 'accuracy')  return <td key={c.key} className="num">{pct(r.accuracy)}</td>;
                  if (c.key === 'warning')   return <td key={c.key} style={{ fontSize: 11, color: 'var(--text-mute)', maxWidth: 180 }}>{r.skipped_reason || r.warning || '—'}</td>;
                  return <td key={c.key} className="num">{fmt(r[c.key])}</td>;
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── FlowPredictionsTable ─────────────────────────────────────────────────────

const FLOW_COLS = [
  { key: 'row_index',           label: 'Row' },
  { key: 'model_id',            label: 'Model' },
  { key: 'dataset',             label: 'Dataset' },
  { key: 'capture_id',          label: 'Capture' },
  { key: 'session_id',          label: 'Session' },
  { key: 'flow_id',             label: 'Flow' },
  { key: 'true_class_text',     label: 'True' },
  { key: 'probability_score',   label: 'Score' },
  { key: 'predicted_class_text',label: 'Predicted' },
  { key: 'correct',             label: 'Correct?' },
  { key: 'error_type',          label: 'Type' },
];

function FlowPredictionsTable({ flows, modelsRun }) {
  const [modelFilter,   setModelFilter]   = useState('all');
  const [typeFilter,    setTypeFilter]    = useState('all');
  const [datasetFilter, setDatasetFilter] = useState('all');
  const [searchText,    setSearchText]    = useState('');
  const [mistakesOnly,  setMistakesOnly]  = useState(false);
  const [page,          setPage]          = useState(0);

  const datasets = useMemo(() => {
    const s = new Set(flows.map(f => f.dataset || '').filter(Boolean));
    return Array.from(s).sort();
  }, [flows]);

  const filtered = useMemo(() => {
    let out = flows;
    if (modelFilter !== 'all')   out = out.filter(f => f.model_id === modelFilter);
    if (typeFilter !== 'all')    out = out.filter(f => f.error_type === typeFilter);
    if (datasetFilter !== 'all') out = out.filter(f => f.dataset === datasetFilter);
    if (mistakesOnly)             out = out.filter(f => f.correct === false);
    if (searchText.trim()) {
      const q = searchText.trim().toLowerCase();
      out = out.filter(f =>
        (f.session_id && String(f.session_id).toLowerCase().includes(q)) ||
        (f.capture_id && String(f.capture_id).toLowerCase().includes(q)) ||
        (f.flow_id    && String(f.flow_id).toLowerCase().includes(q))
      );
    }
    return out;
  }, [flows, modelFilter, typeFilter, datasetFilter, mistakesOnly, searchText]);

  const totalPages = Math.ceil(filtered.length / FLOW_PAGE_SIZE);
  const pageRows   = filtered.slice(page * FLOW_PAGE_SIZE, (page + 1) * FLOW_PAGE_SIZE);

  const selectStyle = { padding: '5px 8px', background: 'var(--bg-2)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 6, fontSize: 12 };

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12, alignItems: 'center' }}>
        <select value={modelFilter} onChange={e => { setModelFilter(e.target.value); setPage(0); }} style={selectStyle}>
          <option value="all">All models</option>
          {(modelsRun || BENCHMARK_COMPATIBLE_IDS).map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <select value={typeFilter} onChange={e => { setTypeFilter(e.target.value); setPage(0); }} style={selectStyle}>
          <option value="all">All types</option>
          <option value="TP">TP</option><option value="TN">TN</option>
          <option value="FP">FP (false positive)</option><option value="FN">FN (false negative)</option>
          <option value="unknown_label">Unknown label</option>
        </select>
        {datasets.length > 0 && (
          <select value={datasetFilter} onChange={e => { setDatasetFilter(e.target.value); setPage(0); }} style={selectStyle}>
            <option value="all">All datasets</option>
            {datasets.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        )}
        <input
          type="text" placeholder="Search session / capture / flow…"
          value={searchText} onChange={e => { setSearchText(e.target.value); setPage(0); }}
          style={{ ...selectStyle, minWidth: 200 }}
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer', color: 'var(--text-dim)' }}>
          <input type="checkbox" checked={mistakesOnly} onChange={e => { setMistakesOnly(e.target.checked); setPage(0); }} />
          Mistakes only
        </label>
        <span className="dim" style={{ fontSize: 12 }}>{filtered.length.toLocaleString()} rows</span>
      </div>

      <div className="table-wrap">
        <table className="dash" style={{ minWidth: 900 }}>
          <thead>
            <tr>{FLOW_COLS.map(c => <th key={c.key}>{c.label}</th>)}</tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr><td colSpan={FLOW_COLS.length} style={{ textAlign: 'center', color: 'var(--text-mute)', padding: 24 }}>No rows match filters.</td></tr>
            ) : pageRows.map((r, i) => (
              <tr key={`${r.model_id}-${r.row_index}-${i}`}
                style={r.correct === false ? { background: 'rgba(239,68,68,0.04)' } : r.correct === true ? { background: 'rgba(46,204,113,0.03)' } : {}}>
                {FLOW_COLS.map(c => {
                  if (c.key === 'model_id') return <td key={c.key} className="mono" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{r.model_id}</td>;
                  if (c.key === 'row_index') return <td key={c.key} className="num" style={{ fontSize: 11 }}>{r.row_index}</td>;
                  if (c.key === 'true_class_text') return (
                    <td key={c.key} style={{ fontSize: 11, color: r.true_label === 1 ? 'var(--bad)' : r.true_label === 0 ? 'var(--ok)' : 'var(--text-mute)' }}>
                      {r.true_class_text}
                    </td>
                  );
                  if (c.key === 'predicted_class_text') return (
                    <td key={c.key} style={{ fontSize: 11, color: r.predicted_label === 1 ? 'var(--bad)' : 'var(--ok)' }}>
                      {r.predicted_class_text}
                    </td>
                  );
                  if (c.key === 'probability_score') return (
                    <td key={c.key} className="num" style={{ fontSize: 11 }}>{fmt(r.probability_score, 4)}</td>
                  );
                  if (c.key === 'correct') return (
                    <td key={c.key} style={{ fontSize: 12, color: r.correct === true ? 'var(--ok)' : r.correct === false ? 'var(--bad)' : 'var(--text-mute)' }}>
                      {r.correct === true ? '✓' : r.correct === false ? '✗' : '—'}
                    </td>
                  );
                  if (c.key === 'error_type') return <td key={c.key}><ErrorTypeBadge et={r.error_type} /></td>;
                  return <td key={c.key} style={{ fontSize: 11, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r[c.key] ?? '—'}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, fontSize: 12, color: 'var(--text-dim)' }}>
          <button className="secondary" onClick={() => setPage(0)} disabled={page === 0} style={{ padding: '4px 10px', fontSize: 11 }}>«</button>
          <button className="secondary" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} style={{ padding: '4px 10px', fontSize: 11 }}>‹</button>
          <span>Page {page + 1} / {totalPages}</span>
          <button className="secondary" onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} style={{ padding: '4px 10px', fontSize: 11 }}>›</button>
          <button className="secondary" onClick={() => setPage(totalPages - 1)} disabled={page >= totalPages - 1} style={{ padding: '4px 10px', fontSize: 11 }}>»</button>
        </div>
      )}
    </div>
  );
}

// ─── SessionPredictionsTable ──────────────────────────────────────────────────

const SESSION_COLS = [
  { key: 'model_id',           label: 'Model' },
  { key: 'dataset',            label: 'Dataset' },
  { key: 'capture_id',         label: 'Capture' },
  { key: 'session_id',         label: 'Session' },
  { key: 'n_flows',            label: 'Flows' },
  { key: 'aggregation',        label: 'Agg' },
  { key: 'aggregated_score',   label: 'Score' },
  { key: 'threshold_used',     label: 'Threshold' },
  { key: 'true_class_text',    label: 'True' },
  { key: 'predicted_class_text', label: 'Predicted' },
  { key: 'correct',            label: 'Correct?' },
  { key: 'error_type',         label: 'Type' },
  { key: 'action',             label: 'Action' },
  { key: 'simulated',          label: 'Simulated' },
];

function SessionPredictionsTable({ sessions, modelsRun }) {
  const [modelFilter, setModelFilter] = useState('all');
  const [typeFilter,  setTypeFilter]  = useState('all');
  const [page,        setPage]        = useState(0);

  const filtered = useMemo(() => {
    let out = sessions;
    if (modelFilter !== 'all') out = out.filter(s => s.model_id === modelFilter);
    if (typeFilter  !== 'all') out = out.filter(s => s.error_type === typeFilter);
    return out;
  }, [sessions, modelFilter, typeFilter]);

  const totalPages = Math.ceil(filtered.length / SESSION_PAGE_SIZE);
  const pageRows   = filtered.slice(page * SESSION_PAGE_SIZE, (page + 1) * SESSION_PAGE_SIZE);

  const selectStyle = { padding: '5px 8px', background: 'var(--bg-2)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 6, fontSize: 12 };

  function actionColor(a) {
    if (!a) return 'var(--text-dim)';
    if (a.includes('BLOCK')) return 'var(--bad)';
    if (a === 'FLAG_REVIEW') return 'var(--warn)';
    return 'var(--ok)';
  }

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12, alignItems: 'center' }}>
        <select value={modelFilter} onChange={e => { setModelFilter(e.target.value); setPage(0); }} style={selectStyle}>
          <option value="all">All models</option>
          {(modelsRun || BENCHMARK_COMPATIBLE_IDS).map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <select value={typeFilter} onChange={e => { setTypeFilter(e.target.value); setPage(0); }} style={selectStyle}>
          <option value="all">All types</option>
          <option value="TP">TP</option><option value="TN">TN</option>
          <option value="FP">FP</option><option value="FN">FN</option>
          <option value="unknown_label">Unknown</option>
        </select>
        <span className="dim" style={{ fontSize: 12 }}>{filtered.length.toLocaleString()} sessions</span>
      </div>

      <div className="table-wrap">
        <table className="dash" style={{ minWidth: 1000 }}>
          <thead>
            <tr>{SESSION_COLS.map(c => <th key={c.key}>{c.label}</th>)}</tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr><td colSpan={SESSION_COLS.length} style={{ textAlign: 'center', color: 'var(--text-mute)', padding: 24 }}>No sessions match filters.</td></tr>
            ) : pageRows.map((r, i) => (
              <tr key={`${r.model_id}-${r.session_id ?? r.capture_id}-${i}`}
                style={r.correct === false ? { background: 'rgba(239,68,68,0.04)' } : r.correct === true ? { background: 'rgba(46,204,113,0.03)' } : {}}>
                {SESSION_COLS.map(c => {
                  if (c.key === 'model_id') return <td key={c.key} className="mono" style={{ fontSize: 11, whiteSpace: 'nowrap' }}>{r.model_id}</td>;
                  if (c.key === 'true_class_text') return <td key={c.key} style={{ fontSize: 11, color: r.true_label === 1 ? 'var(--bad)' : r.true_label === 0 ? 'var(--ok)' : 'var(--text-mute)' }}>{r.true_class_text}</td>;
                  if (c.key === 'predicted_class_text') return <td key={c.key} style={{ fontSize: 11, color: r.predicted_label === 1 ? 'var(--bad)' : 'var(--ok)' }}>{r.predicted_class_text}</td>;
                  if (c.key === 'aggregated_score') return <td key={c.key} className="num" style={{ fontSize: 11 }}>{fmt(r.aggregated_score, 4)}</td>;
                  if (c.key === 'threshold_used')   return <td key={c.key} className="num" style={{ fontSize: 11 }}>{fmt(r.threshold_used, 4)}</td>;
                  if (c.key === 'correct') return <td key={c.key} style={{ fontSize: 12, color: r.correct === true ? 'var(--ok)' : r.correct === false ? 'var(--bad)' : 'var(--text-mute)' }}>{r.correct === true ? '✓' : r.correct === false ? '✗' : '—'}</td>;
                  if (c.key === 'error_type') return <td key={c.key}><ErrorTypeBadge et={r.error_type} /></td>;
                  if (c.key === 'action') return <td key={c.key} style={{ fontSize: 11, color: actionColor(r.action), fontWeight: 600 }}>{r.action || '—'}</td>;
                  if (c.key === 'simulated') return <td key={c.key} style={{ fontSize: 11, color: 'var(--text-mute)' }}>{r.simulated ? '✓ sim' : '—'}</td>;
                  if (c.key === 'n_flows') return <td key={c.key} className="num" style={{ fontSize: 11 }}>{r.n_flows}</td>;
                  return <td key={c.key} style={{ fontSize: 11, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis' }}>{r[c.key] ?? '—'}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, fontSize: 12, color: 'var(--text-dim)' }}>
          <button className="secondary" onClick={() => setPage(0)} disabled={page === 0} style={{ padding: '4px 10px', fontSize: 11 }}>«</button>
          <button className="secondary" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} style={{ padding: '4px 10px', fontSize: 11 }}>‹</button>
          <span>Page {page + 1} / {totalPages}</span>
          <button className="secondary" onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} style={{ padding: '4px 10px', fontSize: 11 }}>›</button>
          <button className="secondary" onClick={() => setPage(totalPages - 1)} disabled={page >= totalPages - 1} style={{ padding: '4px 10px', fontSize: 11 }}>»</button>
        </div>
      )}
    </div>
  );
}

// ─── ResultsSection ───────────────────────────────────────────────────────────

function ResultsSection({ results }) {
  const [tab, setTab] = useState('summary');

  const allResults   = results?.results ?? results?.per_model_results ?? [];
  const flowPreds    = results?.per_flow_predictions ?? [];
  const sessionPreds = results?.per_session_predictions ?? [];
  const modelsRun    = results?.models_run ?? [];
  const skipped      = results?.models_skipped ?? [];
  const csvInfo      = results?.benchmark_csv_info ?? {};

  function modelSummaryRows() {
    return allResults.filter(r => r.benchmark_compatible).map(r => ({
      model_id: r.model_id, role: r.role ?? '', executable: r.executable ? 'yes' : 'no',
      feature_count: r.feature_count ?? '', probability_column: r.probability_column ?? '',
      aggregation: r.aggregation ?? '', block_threshold: r.block_threshold_used ?? '',
      auc: r.auc ?? r.AUC ?? '',
      tp: r.tp ?? '', fp: r.fp ?? '', tn: r.tn ?? '', fn: r.fn ?? '',
      precision: r.precision ?? '', recall: r.recall ?? '', fpr: r.fpr ?? '', accuracy: r.accuracy ?? '',
      rows_used: r.rows_used ?? '', captures_used: r.captures_used ?? '',
      skipped: r.skipped ? 'yes' : 'no', warning: r.warning ?? '',
    }));
  }

  const tabBtn = (t, label) => (
    <button type="button" onClick={() => setTab(t)} style={{
      padding: '6px 14px', fontSize: 13, fontWeight: 500, borderRadius: 7, cursor: 'pointer',
      background: tab === t ? 'rgba(56,189,248,0.15)' : 'transparent',
      border: `1px solid ${tab === t ? 'rgba(56,189,248,0.35)' : 'transparent'}`,
      color: tab === t ? '#f1f5f9' : '#cbd5e1',
    }}>{label}</button>
  );

  return (
    <div className="section">
      {/* Summary bar */}
      <div className="mm-input-summary" style={{ marginBottom: 16 }}>
        <span><strong>{csvInfo.rows ?? '?'}</strong> flows</span>
        <span className="dim">·</span>
        <span><strong>{csvInfo.captures ?? '?'}</strong> captures</span>
        <span className="dim">·</span>
        <span><strong>{modelsRun.length}</strong> model{modelsRun.length !== 1 ? 's' : ''} run</span>
        {skipped.length > 0 && <><span className="dim">·</span><span className="badge warn small-badge"><span className="dot" />{skipped.length} skipped</span></>}
        <span className="badge neutral small-badge"><span className="dot" />benchmark-only</span>
        {results?.source && <span className="badge info small-badge"><span className="dot" />{results.source}</span>}
      </div>

      {skipped.length > 0 && (
        <WarningBox tone="warn">
          <strong>Skipped:</strong> {skipped.join(', ')}. Check that your CSV contains all required features.
        </WarningBox>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 14, flexWrap: 'wrap' }}>
        {tabBtn('summary', `Model summary (${allResults.filter(r => r.benchmark_compatible).length})`)}
        {tabBtn('flows',   `Per-flow predictions (${flowPreds.length.toLocaleString()})`)}
        {tabBtn('sessions',`Per-session decisions (${sessionPreds.length.toLocaleString()})`)}
      </div>

      {tab === 'summary'  && <ModelSummaryTable results={allResults} />}
      {tab === 'flows'    && (flowPreds.length > 0
        ? <FlowPredictionsTable flows={flowPreds} modelsRun={modelsRun} />
        : <div className="dim" style={{ padding: 16 }}>No per-flow predictions (run benchmark first).</div>)}
      {tab === 'sessions' && (sessionPreds.length > 0
        ? <SessionPredictionsTable sessions={sessionPreds} modelsRun={modelsRun} />
        : <div className="dim" style={{ padding: 16 }}>No per-session predictions.</div>)}

      {/* Download buttons */}
      <div style={{ display: 'flex', gap: 10, marginTop: 18, flexWrap: 'wrap' }}>
        <button type="button" className="secondary" onClick={() => downloadCsv(modelSummaryRows(), 'benchmark_model_summary.csv')} style={{ fontSize: 12, padding: '6px 14px' }}>
          ↓ Model summary CSV
        </button>
        {flowPreds.length > 0 && (
          <button type="button" className="secondary" onClick={() => downloadCsv(flowPreds, 'benchmark_flow_predictions.csv')} style={{ fontSize: 12, padding: '6px 14px' }}>
            ↓ Flow predictions CSV ({flowPreds.length.toLocaleString()} rows)
          </button>
        )}
        {sessionPreds.length > 0 && (
          <button type="button" className="secondary" onClick={() => downloadCsv(sessionPreds, 'benchmark_session_predictions.csv')} style={{ fontSize: 12, padding: '6px 14px' }}>
            ↓ Session decisions CSV ({sessionPreds.length.toLocaleString()} rows)
          </button>
        )}
      </div>

      <div style={{ marginTop: 12, padding: '10px 14px', borderRadius: 8, background: 'rgba(56,189,248,0.04)', border: '1px solid rgba(56,189,248,0.15)', fontSize: 12, color: 'var(--text-mute)' }}>
        Benchmark-only. These results compare model behaviour on the tested CSV. They do not change the active firewall model.<br />
        Only <span className="mono">full_canonical__lgbm</span> is executable as the firewall prototype.
        Comparison-only models benchmarked here are not deployable.
      </div>
    </div>
  );
}

// ─── NonCompatibleSection ─────────────────────────────────────────────────────

function NonCompatibleSection({ allModels, permissions }) {
  const [open, setOpen] = useState(false);
  const nonCompat = Object.entries(allModels || {}).filter(([id]) => !BENCHMARK_COMPATIBLE_IDS.includes(id));
  if (nonCompat.length === 0) return null;
  return (
    <div className="card" style={{ padding: 0, marginBottom: 0 }}>
      <button type="button" onClick={() => setOpen(v => !v)}
        style={{ width: '100%', textAlign: 'left', padding: '12px 16px', background: 'transparent', color: 'var(--text)', border: 'none', cursor: 'pointer', fontWeight: 600, fontSize: 13, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span>
          {open ? '▾' : '▸'} Other registered models — not benchmark-compatible
          <span className="dim" style={{ fontWeight: 400, marginLeft: 8 }}>({nonCompat.length})</span>
        </span>
        <span className="badge neutral small-badge"><span className="dot" />read-only</span>
      </button>
      {open && (
        <div style={{ padding: '0 16px 16px' }}>
          <div className="warning-box info" style={{ marginBottom: 12 }}>
            <span className="icon">ℹ</span>
            <div>
              Only models proven compatible with the same raw-feature CSV are selectable. These models remain
              visible for comparison, research, negative-control, or documentation purposes only,
              but <strong>cannot be run in this benchmark</strong>.
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10 }}>
            {nonCompat.map(([id, entry]) => (
              <ModelCard key={id} modelId={id} entry={entry} permissions={permissions} selected={false} onToggle={() => {}} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function MultiModelCsvEvaluation() {
  const [allModels,   setAllModels]   = useState(null);
  const [permissions, setPermissions] = useState(null);
  const [loadError,   setLoadError]   = useState(null);
  const [loading,     setLoading]     = useState(true);

  const [selectedIds, setSelectedIds] = useState(new Set(BENCHMARK_COMPATIBLE_IDS));

  const [results,  setResults]  = useState(null);
  const [running,  setRunning]  = useState(false);
  const [runError, setRunError] = useState(null);

  const fileRef = useRef(null);
  const [fileName,        setFileName]        = useState('');
  const [validationError, setValidationError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const [models, perms] = await Promise.all([api.models(), api.modelPermissions()]);
        setAllModels(models);
        setPermissions(perms);
      } catch (e) {
        setLoadError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  function toggleModel(id) {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) { if (next.size > 1) next.delete(id); }
      else next.add(id);
      return next;
    });
  }

  async function runBundled() {
    setRunError(null); setResults(null); setRunning(true);
    try {
      setResults(await api.benchmarkBundled(Array.from(selectedIds)));
    } catch (e) {
      setRunError(e.message);
    } finally {
      setRunning(false);
    }
  }

  async function runUpload() {
    setValidationError('');
    const file = fileRef.current?.files?.[0];
    if (!file) { setValidationError('Please select a CSV file.'); return; }
    setRunError(null); setResults(null); setRunning(true);
    try {
      setResults(await api.benchmarkUploadCsv(file, Array.from(selectedIds)));
    } catch (e) {
      setRunError(e.message);
    } finally {
      setRunning(false);
    }
  }

  const allModelIds     = allModels ? Object.keys(allModels) : [];
  const nonCompatModels = allModelIds.filter(id => !BENCHMARK_COMPATIBLE_IDS.includes(id));

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Compatible model benchmark</h1>
          <div className="subtitle">
            Simultaneous benchmark of audit-approved models. Only audit-compatible models are selectable.
            All other models remain visible as comparison/documentation only.
            Results are <strong>read-only</strong> and do not affect firewall decisions.
          </div>
        </div>
      </div>

      <WarningBox tone="warn">
        <strong>Simulation only.</strong>{' '}
        Only <span className="mono">full_canonical__lgbm</span> is the executable firewall model.{' '}
        <span className="mono">robust9_firewall</span>, <span className="mono">balanced_bagging_3ds_reference</span>,
        and <span className="mono">balanced_bagging_baseline</span> are benchmark-compatible but comparison-only.
        No real packets are examined or blocked.
      </WarningBox>

      {loading && <div className="loading-line"><span className="spinner" />Loading registry…</div>}
      {loadError && <div className="error-box">Failed to load: {loadError}</div>}

      {!loading && !loadError && (
        <>
          {/* ── Compatible model cards ── */}
          <div className="section">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
                  Benchmark-compatible models
                </h2>
                <p className="dim" style={{ margin: '4px 0 0', fontSize: 12 }}>
                  Select one or more audit-compatible models to include in the benchmark.
                </p>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button type="button" className="secondary" onClick={() => setSelectedIds(new Set(BENCHMARK_COMPATIBLE_IDS))} style={{ fontSize: 11, padding: '4px 10px' }}>Select all</button>
                <button type="button" className="secondary" onClick={() => setSelectedIds(new Set([BENCHMARK_COMPATIBLE_IDS[0]]))} style={{ fontSize: 11, padding: '4px 10px' }}>Deselect all</button>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12 }}>
              {BENCHMARK_COMPATIBLE_IDS.map(id => (
                <ModelCard key={id} modelId={id} entry={allModels?.[id] || {}} permissions={permissions}
                  selected={selectedIds.has(id)} onToggle={toggleModel} />
              ))}
            </div>

            <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-mute)' }}>
              Selected: <strong style={{ color: 'var(--text)' }}>{selectedIds.size}</strong> of {BENCHMARK_COMPATIBLE_IDS.length} compatible models
            </div>
          </div>

          {/* ── Non-compatible models (collapsed) ── */}
          {nonCompatModels.length > 0 && (
            <div className="section">
              <NonCompatibleSection allModels={allModels} permissions={permissions} />
            </div>
          )}

          {/* ── Benchmark controls card ── */}
          <div className="section card">
            <h2 style={{ marginTop: 0 }}>Compatible benchmark</h2>
            <p className="dim" style={{ marginTop: 0, marginBottom: 12 }}>
              Run the bundled audit benchmark or upload your own compatible CSV against the
              <strong> {selectedIds.size} selected model{selectedIds.size !== 1 ? 's' : ''}</strong>.
              Results are benchmark-only and do not affect firewall decisions.
              Only <span className="mono">full_canonical__lgbm</span> is executable as the firewall prototype.
            </p>

            <div className="warning-box info" style={{ marginBottom: 16 }}>
              <span className="icon">ℹ</span>
              <div>
                <strong>Static simultaneous benchmark — not runtime firewall inference.</strong>{' '}
                Bundled CSV: <span className="mono">simultaneous_test_selected_models.csv</span>{' '}
                (7,952 flows, 104 captures). Extra columns are ignored; models with missing required
                features are skipped individually. Per-flow and per-session predictions are returned.
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <button type="button" onClick={runBundled} disabled={running || selectedIds.size === 0}>
                {running ? <><span className="spinner" /> Running…</> : `▶ Run bundled benchmark (${selectedIds.size} model${selectedIds.size !== 1 ? 's' : ''})`}
              </button>
            </div>

            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>Upload compatible CSV</div>
              <p className="dim" style={{ marginTop: 0, marginBottom: 10, fontSize: 13 }}>
                Upload a CSV containing the union of required features. Each model selects its own required subset.
              </p>
              <div className="mm-file-row">
                <label className="mm-file-label">
                  <input ref={fileRef} type="file" accept=".csv"
                    onChange={e => setFileName(e.target.files?.[0]?.name || '')}
                    style={{ display: 'none' }} />
                  <span className="button secondary">Choose CSV</span>
                  {fileName
                    ? <span className="mono" style={{ fontSize: 12 }}>{fileName}</span>
                    : <span className="muted" style={{ fontSize: 12 }}>No file selected</span>}
                </label>
                <button type="button" onClick={runUpload} disabled={running || selectedIds.size === 0}>
                  {running ? <><span className="spinner" /> Analyzing…</> : `Analyze uploaded CSV (${selectedIds.size} model${selectedIds.size !== 1 ? 's' : ''})`}
                </button>
              </div>
              {validationError && <div className="error-box" style={{ marginTop: 10 }}>{validationError}</div>}
            </div>
          </div>
        </>
      )}

      {runError && (
        <div className="error-box" style={{ marginBottom: 16 }}>
          <strong>Error:</strong> {runError}
        </div>
      )}

      {running && !results && (
        <div className="loading-line"><span className="spinner" />Running benchmark — this may take a few seconds…</div>
      )}

      {results && <ResultsSection results={results} />}

      <div className="mm-page-footer">
        Compatible model benchmark — only audit-approved models are selectable.{' '}
        Only <code className="mono">full_canonical__lgbm</code> is executable as the firewall prototype.
        All results are read-only. No real packets are examined or blocked. Prototype is not production-ready.
      </div>
    </div>
  );
}
