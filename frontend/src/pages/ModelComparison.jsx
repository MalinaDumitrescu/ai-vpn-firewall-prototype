import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import WarningBox from '../components/WarningBox.jsx';

// ─── helpers ──────────────────────────────────────────────────────────────────

function fmt(v, d = 4) {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return v.toString();
    return v.toFixed(d);
  }
  return String(v);
}

function BoolBadge({ value }) {
  if (value === true)  return <span style={{ color: 'var(--ok)', fontSize: 12 }}>✓ yes</span>;
  if (value === false) return <span style={{ color: 'var(--bad)', fontSize: 12 }}>✗ no</span>;
  return <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>—</span>;
}

function ActionPill({ action }) {
  if (!action) return <span style={{ color: 'var(--text-dim)' }}>—</span>;
  const colors = {
    PASS:        { bg: 'rgba(46,204,113,0.15)', color: 'var(--ok)',  label: 'PASS' },
    FLAG_REVIEW: { bg: 'rgba(245,180,0,0.15)',  color: 'var(--warn)', label: 'FLAG' },
    BLOCK:       { bg: 'rgba(239,68,68,0.15)',  color: 'var(--bad)', label: 'SIM.BLOCK' },
  };
  const c = colors[action] || { bg: 'transparent', color: 'var(--text-dim)', label: action };
  return (
    <span style={{
      background: c.bg, color: c.color, fontSize: 11, fontWeight: 700,
      padding: '2px 7px', borderRadius: 4, letterSpacing: '0.04em',
    }}>
      {c.label}
    </span>
  );
}

// ─── model selector card ──────────────────────────────────────────────────────

function ModelSelectCard({ model, checked, onChange }) {
  const disabled = !model.selectable;

  return (
    <div
      className={`mm-model-checkbox-card${checked ? ' checked' : ''}`}
      style={{
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.48 : 1,
        borderColor: checked ? 'rgba(79,157,255,0.55)' : undefined,
        background: disabled ? undefined : checked ? 'rgba(79,157,255,0.04)' : undefined,
      }}
      onClick={() => { if (!disabled) onChange(!checked); }}
    >
      <div className="mm-checkbox-row">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="checkbox"
            checked={checked}
            disabled={disabled}
            onChange={(e) => { if (!disabled) onChange(e.target.checked); }}
            onClick={(e) => e.stopPropagation()}
            style={{ width: 15, height: 15, cursor: disabled ? 'not-allowed' : 'pointer', accentColor: 'var(--accent)' }}
          />
          <span className="mono" style={{ fontWeight: 600, fontSize: 13 }}>
            {model.model_id}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {model.selectable ? (
            <span className="badge neutral small-badge">
              <span className="dot" />benchmark comparison
            </span>
          ) : model.executable ? (
            <span className="badge ok small-badge">
              <span className="dot" />active runtime model · READ-ONLY
            </span>
          ) : (
            <span className="badge bad small-badge">
              <span className="dot" />NOT BENCHMARK-COMPATIBLE
            </span>
          )}
          {model.feature_count > 0 && (
            <span className="badge info small-badge">
              <span className="dot" />{model.feature_count} features
            </span>
          )}
        </div>
      </div>

      {/* reason line */}
      {disabled && model.disabled_reason && (
        <div style={{ fontSize: 11, color: model.executable ? 'var(--info)' : 'var(--text-dim)', marginTop: 5, fontStyle: 'italic' }}>
          {model.disabled_reason}
        </div>
      )}
      {!disabled && model.ui_warning && (
        <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 5 }}>
          {model.ui_warning}
        </div>
      )}
    </div>
  );
}

// ─── required features panel ──────────────────────────────────────────────────

function RequiredFeaturesPanel({ modelInfo, selectedIds }) {
  const [open, setOpen] = useState(false);
  if (!modelInfo) return null;

  const selectedModels = (modelInfo.compatible_models || []).filter(m => selectedIds.has(m.model_id));
  const union = new Set();
  selectedModels.forEach(m => (m.feature_order || []).forEach(f => union.add(f)));
  const unionArr = Array.from(union).sort();

  return (
    <div className="card" style={{ padding: 0 }}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        style={{
          width: '100%', textAlign: 'left', padding: '11px 16px',
          background: 'transparent', color: 'var(--text)', border: 'none',
          cursor: 'pointer', fontWeight: 600, fontSize: 13,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}
      >
        <span>
          {open ? '▾' : '▸'}{' '}
          Required features for selected models
          {' '}({unionArr.length} columns in union)
        </span>
        <span className="badge neutral small-badge" style={{ fontSize: 11 }}>
          {(modelInfo.optional_columns || []).join(' · ')} optional
        </span>
      </button>

      {open && (
        <div style={{ padding: '0 16px 16px' }}>
          <div className="warning-box info" style={{ marginBottom: 10 }}>
            <span className="icon">ℹ</span>
            <div>
              A model is <strong>skipped</strong> (not failed) if the uploaded CSV is
              missing its required features. All other selected models still run.
              <br />
              <span className="mono">label</span> is optional — needed only for AUC and TP/FP/TN/FN.
            </div>
          </div>

          {selectedIds.size === 0 ? (
            <div className="muted" style={{ fontSize: 12 }}>No models selected.</div>
          ) : (
            <>
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontWeight: 600, fontSize: 11, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 5 }}>
                  Union of required features ({unionArr.length}) — for the {selectedIds.size} selected model{selectedIds.size !== 1 ? 's' : ''}
                </div>
                <div className="mm-feature-chips">
                  {unionArr.map(f => <span key={f} className="mm-feature-chip">{f}</span>)}
                </div>
              </div>

              <div style={{ marginBottom: 10 }}>
                <div style={{ fontWeight: 600, fontSize: 11, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 5 }}>
                  Optional pass-through columns
                </div>
                <div className="mm-feature-chips">
                  {(modelInfo.optional_columns || []).map(f =>
                    <span key={f} className="mm-feature-chip optional">{f}</span>
                  )}
                </div>
              </div>

              {selectedModels.map(m => (
                <details key={m.model_id} className="mm-per-model-features" style={{ marginTop: 6 }}>
                  <summary>
                    <span className="mono">{m.model_id}</span>
                    <span className="dim"> — {(m.feature_order || []).length} features</span>
                  </summary>
                  <div className="mm-feature-chips" style={{ marginTop: 6 }}>
                    {(m.feature_order || []).map(f =>
                      <span key={f} className="mm-feature-chip">{f}</span>
                    )}
                  </div>
                </details>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ─── per-model summary table ──────────────────────────────────────────────────

function ModelSummaryTable({ results }) {
  if (!results || results.length === 0) return null;
  const shown = results.filter(r =>
    r.skipped_reason !== 'Not selected for this benchmark run.'
  );
  return (
    <div className="table-wrap" style={{ marginTop: 12 }}>
      <table className="dash" style={{ fontSize: 12 }}>
        <thead>
          <tr>
            <th>Model</th>
            <th>Compatible</th>
            <th>AUC</th>
            <th>TP</th>
            <th>FP</th>
            <th>TN</th>
            <th>FN</th>
            <th>Rows</th>
            <th>Sessions</th>
            <th>P / F / B</th>
            <th>Missing features</th>
            <th>Note</th>
          </tr>
        </thead>
        <tbody>
          {shown.map(r => (
            <tr key={r.model_id} style={{ opacity: r.skipped ? 0.5 : 1 }}>
              <td className="mono" style={{ fontWeight: r.skipped ? 400 : 600 }}>
                {r.model_id}
                {r.skipped && (
                  <span className="badge warn small-badge" style={{ marginLeft: 5 }}>skipped</span>
                )}
              </td>
              <td><BoolBadge value={r.benchmark_compatible} /></td>
              <td className="num">{r.AUC !== undefined ? <strong>{fmt(r.AUC)}</strong> : '—'}</td>
              <td className="num">{r.TP !== undefined ? r.TP : '—'}</td>
              <td className="num">{r.FP !== undefined ? r.FP : '—'}</td>
              <td className="num">{r.TN !== undefined ? r.TN : '—'}</td>
              <td className="num">{r.FN !== undefined ? r.FN : '—'}</td>
              <td className="num">{r.rows_used ?? '—'}</td>
              <td className="num">{r.captures_used ?? '—'}</td>
              <td style={{ fontSize: 11 }}>
                {r.action_counts
                  ? `${r.action_counts.PASS ?? 0} / ${r.action_counts.FLAG_REVIEW ?? 0} / ${r.action_counts.BLOCK ?? 0}`
                  : '—'}
              </td>
              <td style={{ fontSize: 11 }}>
                {r.missing_features && r.missing_features.length > 0
                  ? <span className="mono">{r.missing_features.slice(0, 3).join(', ')}{r.missing_features.length > 3 ? ` +${r.missing_features.length - 3}` : ''}</span>
                  : <span className="muted">—</span>}
              </td>
              <td style={{ fontSize: 10, color: 'var(--text-dim)', maxWidth: 180 }}>
                {r.skipped_reason || r.warning || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── per-session expandable cards ─────────────────────────────────────────────

function SessionResultCard({ modelResult }) {
  const [open, setOpen] = useState(false);
  if (modelResult.skipped || !modelResult.sessions || modelResult.sessions.length === 0) return null;

  return (
    <div className="card" style={{ padding: 0, marginTop: 10 }}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        style={{
          width: '100%', textAlign: 'left', padding: '10px 14px',
          background: 'transparent', color: 'var(--text)', border: 'none',
          cursor: 'pointer', fontWeight: 600, fontSize: 12,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}
      >
        <span>
          {open ? '▾' : '▸'}{' '}
          <span className="mono">{modelResult.model_id}</span>
          {' '}— {modelResult.sessions.length} session{modelResult.sessions.length !== 1 ? 's' : ''}
        </span>
        <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <span style={{ color: 'var(--ok)', fontSize: 11 }}>P:{modelResult.action_counts?.PASS ?? 0}</span>
          <span style={{ color: 'var(--warn)', fontSize: 11 }}>F:{modelResult.action_counts?.FLAG_REVIEW ?? 0}</span>
          <span style={{ color: 'var(--bad)', fontSize: 11 }}>B:{modelResult.action_counts?.BLOCK ?? 0}</span>
          {modelResult.AUC !== undefined && (
            <span className="badge neutral small-badge" style={{ marginLeft: 2 }}>AUC {fmt(modelResult.AUC, 3)}</span>
          )}
        </span>
      </button>
      {open && (
        <div style={{ padding: '0 14px 14px' }}>
          <div className="table-wrap">
            <table className="dash" style={{ fontSize: 11 }}>
              <thead>
                <tr>
                  <th>Session</th>
                  <th>Flows</th>
                  <th>Score</th>
                  <th>Action</th>
                  <th>Strict</th>
                  <th>Balanced</th>
                  {modelResult.sessions[0]?.label !== undefined && <th>Label</th>}
                  {modelResult.sessions[0]?.correct !== undefined && <th>Correct</th>}
                </tr>
              </thead>
              <tbody>
                {modelResult.sessions.map((s, i) => (
                  <tr key={s.session_id || i}>
                    <td className="mono">{s.session_id}</td>
                    <td className="num">{s.n_flows}</td>
                    <td className="num"><strong>{fmt(s.session_score)}</strong></td>
                    <td><ActionPill action={s.action} /></td>
                    <td><BoolBadge value={s.strict_trigger} /></td>
                    <td><BoolBadge value={s.balanced_trigger} /></td>
                    {s.label !== undefined && <td className="num">{s.label !== null ? s.label : '—'}</td>}
                    {s.correct !== undefined && <td><BoolBadge value={s.correct === 1} /></td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── per-flow comparison table ────────────────────────────────────────────────

function PerFlowTable({ benchResult }) {
  const [open, setOpen] = useState(false);
  if (!benchResult) return null;
  const rows = benchResult.per_flow_predictions || [];
  const modelCols = benchResult.per_flow_model_columns || [];
  if (rows.length === 0 || modelCols.length === 0) return null;

  const idCols = ['flow_id', 'session_id', 'capture_id', 'dataset', 'label'].filter(
    k => rows[0] && k in rows[0]
  );
  const hasLabel = 'label' in (rows[0] || {});

  return (
    <div className="card" style={{ padding: 0, marginTop: 12 }}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        style={{
          width: '100%', textAlign: 'left', padding: '11px 16px',
          background: 'transparent', color: 'var(--text)', border: 'none',
          cursor: 'pointer', fontWeight: 600, fontSize: 13,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}
      >
        <span>
          {open ? '▾' : '▸'} Per-flow predictions —{' '}
          {rows.length} flow{rows.length !== 1 ? 's' : ''} × {modelCols.length} model{modelCols.length !== 1 ? 's' : ''}
        </span>
        <span className="badge neutral small-badge">comparison-only · does not affect firewall</span>
      </button>

      {open && (
        <div style={{ padding: '0 16px 16px', overflowX: 'auto' }}>
          <div className="warning-box info" style={{ marginBottom: 10 }}>
            <span className="icon">ℹ</span>
            Per-flow scores from all selected models side-by-side. Does{' '}
            <strong>not</strong> update Live VM or the active firewall model.
          </div>
          <div className="table-wrap">
            <table className="dash" style={{ fontSize: 11 }}>
              <thead>
                <tr>
                  {idCols.map(c => <th key={c}>{c}</th>)}
                  {modelCols.map(mid => (
                    <React.Fragment key={mid}>
                      <th style={{ whiteSpace: 'nowrap' }}>{mid.replace(/__lgbm$/, '').replace(/_/g, ' ')}<br />score</th>
                      <th>action</th>
                      {hasLabel && <th>correct?</th>}
                    </React.Fragment>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.slice(0, 250).map((row, i) => (
                  <tr key={i}>
                    {idCols.map(c => (
                      <td key={c} className={['flow_id','session_id','capture_id'].includes(c) ? 'mono' : ''}>
                        {row[c] !== null && row[c] !== undefined ? String(row[c]) : '—'}
                      </td>
                    ))}
                    {modelCols.map(mid => (
                      <React.Fragment key={mid}>
                        <td className="num">{fmt(row[`${mid}__score`])}</td>
                        <td><ActionPill action={row[`${mid}__action`]} /></td>
                        {hasLabel && (
                          <td>
                            {row[`${mid}__correct`] !== undefined
                              ? <BoolBadge value={row[`${mid}__correct`]} />
                              : '—'}
                          </td>
                        )}
                      </React.Fragment>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length > 250 && (
              <div className="muted" style={{ fontSize: 11, padding: '8px 4px' }}>
                Showing first 250 of {rows.length} rows.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── schema mismatch detector ────────────────────────────────────────────────

function SchemaGroup({ modelId, compatData }) {
  if (!compatData?.models?.[modelId]) return null;
  const m = compatData.models[modelId];
  if (m.can_run_in_unified_runtime) return 'unified';
  if (m.can_run_in_legacy_benchmark) return 'legacy';
  return null;
}

// ─── unified benchmark section ───────────────────────────────────────────────

function UnifiedBenchmarkSection({ compatData }) {
  const [benchResult,  setBenchResult]  = useState(null);
  const [benchRunning, setBenchRunning] = useState(false);
  const [benchError,   setBenchError]   = useState(null);
  const fileRef  = useRef(null);
  const [fileName,  setFileName]  = useState('');
  const [fileError, setFileError] = useState('');

  const unifiedModels = compatData
    ? Object.entries(compatData.models).filter(([, m]) => m.can_run_in_unified_runtime)
    : [];

  async function runBundled() {
    setBenchError(null); setBenchResult(null); setBenchRunning(true);
    try { setBenchResult(await api.unifiedBenchmarkBundled()); }
    catch (e) { setBenchError(e.message); }
    finally { setBenchRunning(false); }
  }

  async function runUpload() {
    setFileError('');
    const file = fileRef.current?.files?.[0];
    if (!file) { setFileError('Please choose a CSV file first.'); return; }
    setBenchError(null); setBenchResult(null); setBenchRunning(true);
    try { setBenchResult(await api.unifiedBenchmarkUploadCsv(file)); }
    catch (e) { setBenchError(e.message); }
    finally { setBenchRunning(false); }
  }

  const executableModelId = 'unified_relative_shape_v2__lgbm';

  return (
    <div>
      <WarningBox tone="info">
        <strong>Unified benchmark mode.</strong>{' '}
        Only <span className="mono">{executableModelId}</span> runs actual inference —
        it is the single executable model. Other unified models (unified_full, unified_size_shape, etc.)
        are documented below but do not run inference here.
        Cross-schema benchmark results are only valid when every selected model uses the same CSV schema.
      </WarningBox>

      {/* Unified model schema table */}
      <div className="section card">
        <h2 style={{ marginTop: 0, fontSize: 16 }}>Unified feature contract v2 — model schemas</h2>
        <p className="dim" style={{ marginTop: 0, marginBottom: 12, fontSize: 13 }}>
          All unified models use <span className="badge ok" style={{ fontSize: 11, verticalAlign: 'middle' }}>unified_feature_contract_v2</span> CSV schemas.
          They are <strong>not</strong> compatible with the legacy benchmark CSV.
        </p>
        <div className="table-wrap">
          <table className="dash" style={{ fontSize: 12 }}>
            <thead>
              <tr>
                <th>Model</th>
                <th>Required CSV schema</th>
                <th># Features</th>
                <th>Executable</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {unifiedModels.map(([id, m]) => (
                <tr key={id}>
                  <td className="mono" style={{ fontWeight: id === executableModelId ? 700 : 400 }}>
                    {id}
                    {id === executableModelId && (
                      <span className="badge ok" style={{ marginLeft: 6, fontSize: 10 }}>CURRENT</span>
                    )}
                  </td>
                  <td className="mono" style={{ fontSize: 11 }}>{m.required_csv_schema}</td>
                  <td style={{ textAlign: 'center' }}>{m.required_feature_count ?? '—'}</td>
                  <td style={{ textAlign: 'center' }}>
                    {id === executableModelId
                      ? <span style={{ color: 'var(--ok)' }}>✓</span>
                      : <span style={{ color: 'var(--text-dim)', fontSize: 11 }}>doc only</span>}
                  </td>
                  <td style={{ fontSize: 11, color: 'var(--text-dim)' }}>{m.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Unified bundled benchmark */}
      <div className="section card">
        <h2 style={{ marginTop: 0, fontSize: 16 }}>Unified bundled benchmark</h2>
        <p className="dim" style={{ marginTop: 0, marginBottom: 10, fontSize: 13 }}>
          Runs <span className="mono">{executableModelId}</span> against the bundled
          <span className="mono"> unified_model_demo_flows.csv</span>.
          Required features: <span className="mono">{
            (compatData?.unified_benchmark_schema?.required_features ?? []).join(', ')
          }</span>.
        </p>
        <div className="warning-box info" style={{ marginBottom: 12 }}>
          <span className="icon">ℹ</span>
          <div>
            Only <strong>{executableModelId}</strong> runs inference.
            Other unified models are returned as comparison-only with metadata.
            Results are benchmark-only — no firewall decisions made.
          </div>
        </div>
        <button type="button" onClick={runBundled} disabled={benchRunning}>
          {benchRunning ? <><span className="spinner" /> Running…</> : '▶ Run unified bundled benchmark'}
        </button>
      </div>

      {/* Unified upload CSV */}
      <div className="section card">
        <h2 style={{ marginTop: 0, fontSize: 16 }}>Analyze unified CSV</h2>
        <p className="dim" style={{ marginTop: 0, marginBottom: 10, fontSize: 13 }}>
          Upload a CSV with unified feature contract v2 columns.
          Required columns: <span className="mono">{(compatData?.unified_benchmark_schema?.required_features ?? []).join(', ')}</span>.
        </p>
        <div className="mm-file-row">
          <label className="mm-file-label">
            <input ref={fileRef} type="file" accept=".csv"
              onChange={(e) => setFileName(e.target.files?.[0]?.name || '')}
              style={{ display: 'none' }} />
            <span className="button secondary">Choose CSV</span>
            {fileName
              ? <span className="mono" style={{ fontSize: 12 }}>{fileName}</span>
              : <span className="muted" style={{ fontSize: 12 }}>No file selected</span>}
          </label>
          <button type="button" onClick={runUpload} disabled={benchRunning}>
            {benchRunning ? <><span className="spinner" /> Analyzing…</> : 'Analyze unified CSV'}
          </button>
        </div>
        {fileError && <div className="error-box" style={{ marginTop: 10 }}>{fileError}</div>}
      </div>

      {benchError && (
        <div className="error-box" style={{ marginBottom: 14 }}>
          <strong>Benchmark error:</strong> {benchError}
        </div>
      )}
      {benchRunning && !benchResult && (
        <div className="loading-line"><span className="spinner" />Running unified benchmark…</div>
      )}

      {benchResult && (
        <div className="section">
          <div className="mm-input-summary" style={{ marginBottom: 12 }}>
            <span><strong>{benchResult.input_summary?.total_flows ?? '?'}</strong> flows</span>
            <span className="dim">·</span>
            <span><strong>{benchResult.input_summary?.total_sessions ?? '?'}</strong> sessions</span>
            <span className="dim">·</span>
            <span>source: <span className="mono">{benchResult.input_summary?.source ?? '—'}</span></span>
            <span className="badge warn small-badge"><span className="dot" />simulation-only</span>
          </div>
          {(benchResult.warnings || []).map((w, i) => (
            <div key={i} className="warning-box info" style={{ marginBottom: 6 }}>
              <span className="icon">ℹ</span>
              <div style={{ fontSize: 12 }}>{w}</div>
            </div>
          ))}
          <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 12, marginBottom: 4 }}>
            Per-model results
          </div>
          <div className="table-wrap">
            <table className="dash" style={{ fontSize: 12 }}>
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Executable</th>
                  <th>Skipped</th>
                  <th>PASS</th>
                  <th>FLAG</th>
                  <th>SIM.BLOCK</th>
                  <th>Sessions</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {(benchResult.model_results || []).map(r => (
                  <tr key={r.model_id} style={{ opacity: r.skipped ? 0.6 : 1 }}>
                    <td className="mono" style={{ fontWeight: r.executable ? 700 : 400 }}>{r.model_id}</td>
                    <td style={{ textAlign: 'center' }}>
                      {r.executable
                        ? <span style={{ color: 'var(--ok)' }}>✓</span>
                        : <span style={{ color: 'var(--text-dim)', fontSize: 11 }}>—</span>}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      {r.skipped
                        ? <span className="badge warn" style={{ fontSize: 10 }}>skipped</span>
                        : <span style={{ color: 'var(--ok)', fontSize: 11 }}>—</span>}
                    </td>
                    <td className="num">{r.counts?.PASS ?? '—'}</td>
                    <td className="num">{r.counts?.FLAG_REVIEW ?? '—'}</td>
                    <td className="num">{r.counts?.BLOCK ?? '—'}</td>
                    <td className="num">{r.total_sessions ?? '—'}</td>
                    <td style={{ fontSize: 10, color: 'var(--text-dim)' }}>
                      {(r.warnings || []).slice(0, 1).join(' ') || r.status || ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── main page ────────────────────────────────────────────────────────────────

export default function ModelComparison() {
  const [benchMode,    setBenchMode]    = useState('legacy'); // 'unified' | 'legacy'
  const [compatData,   setCompatData]   = useState(null);
  const [modelInfo,    setModelInfo]    = useState(null);
  const [loadError,    setLoadError]    = useState(null);
  const [loading,      setLoading]      = useState(true);

  // Checkbox selection — default all 4 compatible models
  const [selected, setSelected] = useState(new Set());

  // Benchmark run state
  const [benchResult,  setBenchResult]  = useState(null);
  const [benchRunning, setBenchRunning] = useState(false);
  const [benchError,   setBenchError]   = useState(null);

  // File upload
  const fileRef = useRef(null);
  const [fileName,  setFileName]  = useState('');
  const [fileError, setFileError] = useState('');

  // ── load model info on mount ──
  useEffect(() => {
    (async () => {
      try {
        const [info, compat] = await Promise.all([
          api.legacyBenchmarkModels(),
          api.modelDetailsBenchmarkCompat().catch(() => null),
        ]);
        setModelInfo(info);
        setCompatData(compat);
        // Default: all 4 compatible models selected
        setSelected(new Set((info.compatible_models || []).map(m => m.model_id)));
      } catch (e) {
        setLoadError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  function toggleModel(id, val) {
    setSelected(prev => {
      const next = new Set(prev);
      if (val) next.add(id); else next.delete(id);
      return next;
    });
  }

  // ── run bundled benchmark ──
  async function runBundled() {
    setBenchError(null);
    setBenchResult(null);
    setBenchRunning(true);
    try {
      const ids = Array.from(selected).join(',');
      const data = await api.legacyBenchmarkBundled(ids || undefined);
      setBenchResult(data);
    } catch (e) {
      setBenchError(e.message);
    } finally {
      setBenchRunning(false);
    }
  }

  // ── run uploaded CSV benchmark ──
  async function runUpload() {
    setFileError('');
    const file = fileRef.current?.files?.[0];
    if (!file) { setFileError('Please choose a CSV file first.'); return; }
    setBenchError(null);
    setBenchResult(null);
    setBenchRunning(true);
    try {
      const ids = Array.from(selected).join(',');
      const data = await api.legacyBenchmarkUploadCsv(file, ids || undefined);
      setBenchResult(data);
    } catch (e) {
      setBenchError(e.message);
    } finally {
      setBenchRunning(false);
    }
  }

  const compatModels         = modelInfo?.compatible_models       || [];
  const incompatModels       = modelInfo?.incompatible_models     || [];
  const disabledRuntimeModels= modelInfo?.disabled_runtime_models || [];
  const nSelected            = selected.size;

  // Schema mismatch detection: check if selected legacy models mix unified/legacy schemas
  const selectedArray = Array.from(selected);
  const schemaGroups  = compatData
    ? [...new Set(selectedArray.map(id => SchemaGroup({ modelId: id, compatData })).filter(Boolean))]
    : [];
  const hasSchemaMismatch = schemaGroups.length > 1;

  const skippedResults = (benchResult?.per_model_results || []).filter(
    r => r.skipped && r.skipped_reason !== 'Not selected for this benchmark run.'
  );

  return (
    <div>
      {/* ── page header ── */}
      <div style={{ marginBottom: 18 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700 }}>Model comparison</h1>
        <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--text-dim)' }}>
          Compare models on a benchmark CSV. Choose Unified or Legacy benchmark mode.
          The two modes use different CSV schemas — cross-schema comparison is not valid.
        </p>
      </div>

      {/* ── schema mismatch global warning ── */}
      <div className="warning-box bad" style={{ marginBottom: 14 }}>
        <span className="icon">⚠</span>
        <div style={{ fontSize: 12 }}>
          <strong>CSV schema separation enforced.</strong>{' '}
          Unified models (<span className="mono">unified_*</span>) use the <strong>unified_feature_contract_v2</strong> CSV schema.
          Legacy models (<span className="mono">full_canonical__lgbm</span>, <span className="mono">robust9_clean__lgbm</span>, etc.)
          use the <strong>legacy benchmark</strong> CSV schema.
          Cross-schema comparison is not valid unless both models can use the same input CSV.
          Use <strong>Unified mode</strong> or <strong>Legacy mode</strong> separately.
        </div>
      </div>

      {/* ── benchmark mode switcher ── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 18, alignItems: 'center' }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', marginRight: 4 }}>Benchmark mode:</span>
        <button
          type="button"
          className={benchMode === 'unified' ? '' : 'secondary'}
          style={{ padding: '6px 16px', fontSize: 13 }}
          onClick={() => { setBenchMode('unified'); setBenchResult(null); setBenchError(null); }}
        >
          Unified models (v2)
        </button>
        <button
          type="button"
          className={benchMode === 'legacy' ? '' : 'secondary'}
          style={{ padding: '6px 16px', fontSize: 13 }}
          onClick={() => { setBenchMode('legacy'); setBenchResult(null); setBenchError(null); }}
        >
          Legacy benchmark
        </button>
      </div>

      {loading && <div className="loading-line"><span className="spinner" />Loading benchmark model info…</div>}
      {loadError && <div className="error-box">Failed to load model info: {loadError}</div>}

      {!loading && !loadError && (
        <>
          {/* ══ UNIFIED BENCHMARK MODE ═══════════════════════════════════════ */}
          {benchMode === 'unified' && (
            <UnifiedBenchmarkSection compatData={compatData} />
          )}

          {/* ══ LEGACY BENCHMARK MODE ════════════════════════════════════════ */}
          {benchMode === 'legacy' && (
            <>
              {/* ── runtime model info note ── */}
              <div className="warning-box info" style={{ marginBottom: 14 }}>
                <span className="icon">ℹ</span>
                <div style={{ fontSize: 12 }}>
                  <strong>Legacy benchmark-only.</strong>{' '}
                  Select and run only the 4 raw-feature compatible legacy benchmark models.
                  The active runtime model{' '}
                  <span className="mono">unified_relative_shape_v2__lgbm</span>{' '}
                  is handled in <strong>Live VM</strong> (unified mode above).
                  Legacy models use a <strong>different CSV schema</strong> — not compatible with unified CSVs.
                </div>
              </div>

              <WarningBox tone="warn">
                <strong>No firewall decisions made here.</strong>{' '}
                All results are simulation-only. BLOCK labels are simulated — no packets are blocked.
              </WarningBox>

              {hasSchemaMismatch && (
                <div className="warning-box bad" style={{ marginBottom: 12 }}>
                  <span className="icon">⚠</span>
                  <div style={{ fontSize: 12 }}>
                    <strong>Schema mismatch detected.</strong>{' '}
                    Selected models require different CSV schemas. Cross-schema comparison may be misleading.
                    Schema groups: <span className="mono">{schemaGroups.join(', ')}</span>.
                  </div>
                </div>
              )}

              {/* ══ MODEL SELECTOR ═══════════════════════════════════════════════ */}
              <div className="section">
                <div style={{
                  fontSize: 12, fontWeight: 600, color: 'var(--text-dim)',
                  textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8,
                }}>
                  Comparison models
                  <span className="badge ok small-badge" style={{ marginLeft: 10 }}>
                    <span className="dot" />4 selectable
                  </span>
                  {nSelected > 0 && (
                    <span className="badge neutral small-badge" style={{ marginLeft: 6 }}>
                      <span className="dot" />{nSelected} selected
                    </span>
                  )}
                  {incompatModels.length + disabledRuntimeModels.length > 0 && (
                    <span className="badge warn small-badge" style={{ marginLeft: 6 }}>
                      <span className="dot" />{incompatModels.length + disabledRuntimeModels.length} read-only
                    </span>
                  )}
                </div>

                <div className="mm-model-selector">
                  {/* ── 4 selectable compatible models ── */}
                  {compatModels.map(m => (
                    <ModelSelectCard
                      key={m.model_id}
                      model={m}
                      checked={selected.has(m.model_id)}
                      onChange={(v) => toggleModel(m.model_id, v)}
                    />
                  ))}

                  {/* ── disabled: active runtime model ── */}
                  {disabledRuntimeModels.map(m => (
                    <ModelSelectCard
                      key={m.model_id}
                      model={m}
                      checked={false}
                      onChange={() => {}}
                    />
                  ))}

                  {/* ── disabled: incompatible models ── */}
                  {incompatModels.map(m => (
                    <ModelSelectCard
                      key={m.model_id}
                      model={m}
                      checked={false}
                      onChange={() => {}}
                    />
                  ))}
                </div>

                {nSelected === 0 && (
                  <div className="warning-box warn" style={{ marginTop: 10 }}>
                    <span className="icon">⚠</span>
                    Select at least one compatible model to run the benchmark.
                  </div>
                )}
              </div>

              {/* ══ REQUIRED FEATURES ════════════════════════════════════════════ */}
              <div className="section">
                <RequiredFeaturesPanel modelInfo={modelInfo} selectedIds={selected} />
              </div>

              {/* ══ BUNDLED BENCHMARK ════════════════════════════════════════════ */}
              <div className="section card">
                <h2 style={{ marginTop: 0, fontSize: 16 }}>Bundled benchmark</h2>
                <p className="dim" style={{ marginTop: 0, marginBottom: 10, fontSize: 13 }}>
                  Runs the selected compatible legacy models against the bundled benchmark CSV.
                  Benchmark-only — does not affect firewall decisions.
                </p>
                <div className="warning-box info" style={{ marginBottom: 12 }}>
                  <span className="icon">ℹ</span>
                  <div>
                    <strong>Bundled CSV:</strong>{' '}
                    <span className="mono">simultaneous_test_selected_models.csv</span> — compatible raw-feature benchmark.
                    Only the <strong>{nSelected} selected</strong> model{nSelected !== 1 ? 's' : ''} will run.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={runBundled}
                  disabled={benchRunning || nSelected === 0}
                >
                  {benchRunning
                    ? <><span className="spinner" /> Running…</>
                    : '▶ Run selected benchmark models'}
                </button>
                {nSelected === 0 && (
                  <span className="muted" style={{ fontSize: 12, marginLeft: 12 }}>
                    Select at least one model above.
                  </span>
                )}
              </div>

              {/* ══ UPLOAD CSV BENCHMARK ═════════════════════════════════════════ */}
              <div className="section card">
                <h2 style={{ marginTop: 0, fontSize: 16 }}>Analyze CSV with selected benchmark models</h2>
                <p className="dim" style={{ marginTop: 0, marginBottom: 10, fontSize: 13 }}>
                  Upload a CSV containing the required features for your selected models.
                  Only the <strong>{nSelected} selected</strong> model{nSelected !== 1 ? 's' : ''} will run.
                  Models missing required features are skipped (not failed) — others still run.
                  Include a <span className="mono">label</span> column for AUC and correctness metrics.
                </p>
                <div className="mm-file-row">
                  <label className="mm-file-label">
                    <input
                      ref={fileRef}
                      type="file"
                      accept=".csv"
                      onChange={(e) => setFileName(e.target.files?.[0]?.name || '')}
                      style={{ display: 'none' }}
                    />
                    <span className="button secondary">Choose CSV</span>
                    {fileName
                      ? <span className="mono" style={{ fontSize: 12 }}>{fileName}</span>
                      : <span className="muted" style={{ fontSize: 12 }}>No file selected</span>}
                  </label>
                  <button
                    type="button"
                    onClick={runUpload}
                    disabled={benchRunning || nSelected === 0}
                  >
                    {benchRunning
                      ? <><span className="spinner" /> Analyzing…</>
                      : `Analyze CSV with ${nSelected} model${nSelected !== 1 ? 's' : ''}`}
                  </button>
                </div>
                {fileError && <div className="error-box" style={{ marginTop: 10 }}>{fileError}</div>}
              </div>

              {/* ── errors ── */}
              {benchError && (
                <div className="error-box" style={{ marginBottom: 14 }}>
                  <strong>Benchmark error:</strong> {benchError}
                </div>
              )}

              {/* ── running indicator ── */}
              {benchRunning && !benchResult && (
                <div className="loading-line"><span className="spinner" />Running benchmark…</div>
              )}

              {/* ══ RESULTS ══════════════════════════════════════════════════════ */}
              {benchResult && (
                <div className="section">
                  {/* summary banner */}
                  <div className="mm-input-summary" style={{ marginBottom: 12 }}>
                    <span><strong>{benchResult.benchmark_csv_info?.rows ?? '?'}</strong> flows</span>
                    <span className="dim">·</span>
                    <span><strong>{benchResult.benchmark_csv_info?.sessions ?? '?'}</strong> sessions</span>
                    <span className="dim">·</span>
                    <span>
                      <strong>{benchResult.models_run?.length ?? 0}</strong>{' '}
                      model{(benchResult.models_run?.length ?? 0) !== 1 ? 's' : ''} run
                    </span>
                    {benchResult.benchmark_csv_info?.has_labels && (
                      <>
                        <span className="dim">·</span>
                        <span className="badge ok small-badge"><span className="dot" />labels present</span>
                      </>
                    )}
                    <span className="badge bad small-badge"><span className="dot" />benchmark-only</span>
                  </div>

                  {/* runtime model note */}
                  {benchResult.runtime_model_note && (
                    <div className="warning-box info" style={{ marginBottom: 12 }}>
                      <span className="icon">ℹ</span>
                      <div style={{ fontSize: 12 }}>{benchResult.runtime_model_note}</div>
                    </div>
                  )}

                  {/* A. model-level summary */}
                  <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
                    A. Model-level summary
                  </div>
                  <ModelSummaryTable results={benchResult.per_model_results} />

                  {/* B. per-session cards */}
                  <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 20, marginBottom: 4 }}>
                    B. Per-session decisions (expand per model)
                  </div>
                  {(benchResult.per_model_results || [])
                    .filter(r => !r.skipped && r.sessions && r.sessions.length > 0)
                    .map(r => <SessionResultCard key={r.model_id} modelResult={r} />)
                  }
                  {(benchResult.per_model_results || []).filter(r => !r.skipped).length === 0 && (
                    <div className="muted" style={{ fontSize: 12 }}>
                      No models ran successfully — check that the CSV contains the required features.
                    </div>
                  )}

                  {/* skipped warnings */}
                  {skippedResults.length > 0 && (
                    <div style={{ marginTop: 10 }}>
                      {skippedResults.map(r => (
                        <div key={r.model_id} className="warning-box warn" style={{ marginBottom: 6 }}>
                          <span className="icon">⚠</span>
                          <div>
                            <span className="mono">{r.model_id}</span> skipped — {r.skipped_reason}
                            {r.missing_features && r.missing_features.length > 0 && (
                              <span className="mono" style={{ marginLeft: 6, fontSize: 11 }}>
                                ({r.missing_features.slice(0, 5).join(', ')}{r.missing_features.length > 5 ? ` +${r.missing_features.length - 5}` : ''})
                              </span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* C. per-flow comparison table */}
                  <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 20, marginBottom: 4 }}>
                    C. Per-flow predictions — all selected models side-by-side
                  </div>
                  <PerFlowTable benchResult={benchResult} />
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* ── footer ── */}
      <div className="mm-page-footer" style={{ marginTop: 32 }}>
        Model comparison — read-only benchmarking. These models are{' '}
        <strong>not</strong> the active runtime firewall.
        No packets are blocked. Results do not affect Dashboard or Live VM.
        Unified and legacy models use different CSV schemas — do not mix them.
      </div>
    </div>
  );
}


