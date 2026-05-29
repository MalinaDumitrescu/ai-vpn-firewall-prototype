import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import WarningBox from '../components/WarningBox.jsx';

// ─── constants ──────────────────────────────────────────────────────────────

const EXECUTABLE_MODEL_ID = 'full_canonical__lgbm';

const BENCHMARK_COMPATIBLE_IDS = [
  'full_canonical__lgbm',
  'robust9_firewall',
  'balanced_bagging_3ds_reference',
  'balanced_bagging_baseline',
];

function reasonNotSelectable(modelId, entry) {
  if (BENCHMARK_COMPATIBLE_IDS.includes(modelId)) return null;
  const status = entry?.status || '';
  if (['balanced_bagging_xgb_baseline', 'robust13_comparison'].includes(modelId))
    return 'Requires session-derived probability features absent from the raw-feature CSV.';
  if (status === 'negative_control' || modelId.startsWith('lodo_'))
    return 'Negative-control LODO model — not compatible with benchmark CSV.';
  if (status === 'research_only' || modelId.includes('dann'))
    return 'Research-only DANN model — not compatible with benchmark CSV.';
  if (status === 'unsupported' || status === 'alias')
    return 'Unsupported / documentation-only artifact.';
  return 'Not compatible with the shared raw-feature benchmark CSV.';
}

// ─── helpers ─────────────────────────────────────────────────────────────────

function fmt(v, d = 4) {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return v.toString();
    return v.toFixed(d);
  }
  return String(v);
}

// ─── Benchmark results table ─────────────────────────────────────────────────

const BENCH_COLS = [
  { key: 'model_id',           label: 'Model',             cls: 'mono' },
  { key: 'role',               label: 'Role',              cls: '' },
  { key: 'executable',         label: 'Executable',        cls: '' },
  { key: 'benchmark_compatible', label: 'Compat.',         cls: '' },
  { key: 'auc',                label: 'AUC',               cls: 'num' },
  { key: 'tp',                 label: 'TP',                cls: 'num' },
  { key: 'fp',                 label: 'FP',                cls: 'num' },
  { key: 'tn',                 label: 'TN',                cls: 'num' },
  { key: 'fn',                 label: 'FN',                cls: 'num' },
  { key: 'rows_used',          label: 'Rows',              cls: 'num' },
  { key: 'captures_used',      label: 'Captures',          cls: 'num' },
  { key: 'missing_features',   label: 'Missing features',  cls: '' },
  { key: 'skipped_rows',       label: 'Skipped rows',      cls: 'num' },
  { key: 'warning',            label: 'Note',              cls: '' },
];

function BenchmarkResultsTable({ results }) {
  // Show compatible models first (those that are benchmark_compatible)
  const compatRows  = results.filter(r => r.benchmark_compatible);
  const skippedRows = results.filter(r => !r.benchmark_compatible && r.skipped);
  const rows = [...compatRows, ...skippedRows];

  if (rows.length === 0) return <div className="dim">No results to display.</div>;

  return (
    <div className="table-wrap" style={{ marginTop: 16 }}>
      <table className="dash">
        <thead>
          <tr>
            {BENCH_COLS.map(c => <th key={c.key}>{c.label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const isExec    = r.model_id === EXECUTABLE_MODEL_ID;
            const isSkipped = r.skipped && !r.benchmark_compatible;
            // Resolve lowercase or uppercase metric keys
            const auc = r.auc ?? r.AUC;
            const tp  = r.tp  ?? r.TP;
            const fp  = r.fp  ?? r.FP;
            const tn  = r.tn  ?? r.TN;
            const fn  = r.fn  ?? r.FN;
            return (
              <tr
                key={r.model_id}
                style={isExec ? { background: 'rgba(79,157,255,0.06)' } : isSkipped ? { opacity: 0.6 } : {}}
              >
                {BENCH_COLS.map(c => {
                  if (c.key === 'model_id') {
                    return (
                      <td key={c.key} className="mono" style={{ fontWeight: isExec ? 700 : 400 }}>
                        {r.model_id}
                        {isExec && (
                          <span className="badge ok small-badge" style={{ marginLeft: 6 }}>
                            <span className="dot" />FIREWALL
                          </span>
                        )}
                        {isSkipped && (
                          <span className="badge warn small-badge" style={{ marginLeft: 6 }}>
                            <span className="dot" />skipped
                          </span>
                        )}
                      </td>
                    );
                  }
                  if (c.key === 'role') {
                    return <td key={c.key} style={{ fontSize: 12 }}>{r.role || '—'}</td>;
                  }
                  if (c.key === 'executable') {
                    return (
                      <td key={c.key} style={{ color: r.executable ? 'var(--ok)' : 'var(--text-dim)', fontSize: 12 }}>
                        {r.executable ? '✓ yes' : '✗ no'}
                      </td>
                    );
                  }
                  if (c.key === 'benchmark_compatible') {
                    return (
                      <td key={c.key} style={{ color: r.benchmark_compatible ? 'var(--ok)' : 'var(--bad)', fontSize: 12 }}>
                        {r.benchmark_compatible ? '✓ yes' : '✗ no'}
                      </td>
                    );
                  }
                  if (c.key === 'auc') {
                    return (
                      <td key={c.key} className="num" style={{ color: auc != null ? 'var(--ok)' : 'var(--text-dim)', fontWeight: 700 }}>
                        {auc != null ? fmt(auc) : '—'}
                      </td>
                    );
                  }
                  if (c.key === 'tp')  return <td key={c.key} className="num">{tp  != null ? tp  : '—'}</td>;
                  if (c.key === 'fp')  return <td key={c.key} className="num">{fp  != null ? fp  : '—'}</td>;
                  if (c.key === 'tn')  return <td key={c.key} className="num">{tn  != null ? tn  : '—'}</td>;
                  if (c.key === 'fn')  return <td key={c.key} className="num">{fn  != null ? fn  : '—'}</td>;
                  if (c.key === 'missing_features') {
                    const mf = r.missing_features || [];
                    if (mf.length === 0) return <td key={c.key} style={{ color: 'var(--ok)', fontSize: 12 }}>none</td>;
                    return (
                      <td key={c.key} style={{ fontSize: 12, color: 'var(--warn)' }}>
                        {mf.join(', ')}
                      </td>
                    );
                  }
                  if (c.key === 'warning') {
                    return (
                      <td key={c.key} style={{ fontSize: 12, color: 'var(--text-dim)', maxWidth: 220 }}>
                        {r.skipped_reason || r.warning || '—'}
                      </td>
                    );
                  }
                  return (
                    <td key={c.key} className={c.cls || ''}>
                      {fmt(r[c.key])}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Non-compatible models collapsed section ──────────────────────────────────

function NonCompatibleSection({ allModels }) {
  const [open, setOpen] = useState(false);
  const nonCompat = Object.entries(allModels || {}).filter(
    ([id]) => !BENCHMARK_COMPATIBLE_IDS.includes(id)
  );
  if (nonCompat.length === 0) return null;
  return (
    <div className="card" style={{ padding: 0 }}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        style={{
          width: '100%', textAlign: 'left', padding: '12px 16px',
          background: 'transparent', color: 'var(--text)', border: 'none',
          cursor: 'pointer', fontWeight: 600, fontSize: 13,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}
      >
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
              Only models proven compatible with the same raw-feature CSV are selectable here.
              These models remain visible in the registry as comparison-only, research-only,
              negative-control, or documentation-only entries, but <strong>cannot be run in this benchmark</strong>.
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {nonCompat.map(([modelId, entry]) => {
              const reason = reasonNotSelectable(modelId, entry);
              const status = entry?.status || '';
              const roleLabel =
                status === 'negative_control' ? 'NEGATIVE CONTROL' :
                status === 'research_only'    ? 'RESEARCH ONLY' :
                status === 'unsupported'      ? 'UNSUPPORTED' :
                status === 'alias'            ? 'ALIAS' :
                status === 'legacy_baseline'  ? 'LEGACY BASELINE' :
                                                'COMPARISON ONLY';
              return (
                <div key={modelId} style={{
                  display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 10px',
                  borderRadius: 6, background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)',
                  flexWrap: 'wrap',
                }}>
                  <span className="mono" style={{ fontSize: 12, fontWeight: 600, minWidth: 230 }}>{modelId}</span>
                  <span className="badge neutral small-badge" style={{ flexShrink: 0 }}>
                    <span className="dot" />{roleLabel}
                  </span>
                  <span className="badge warn small-badge" style={{ flexShrink: 0 }}>
                    <span className="dot" />NOT SELECTABLE
                  </span>
                  <span className="dim" style={{ fontSize: 12, fontStyle: 'italic' }}>{reason}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── main page ────────────────────────────────────────────────────────────────

export default function MultiModelCsvEvaluation() {
  const [allModels, setAllModels] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [loading,   setLoading]   = useState(true);

  const [results,   setResults]   = useState(null);
  const [running,   setRunning]   = useState(false);
  const [runError,  setRunError]  = useState(null);

  const fileRef = useRef(null);
  const [fileName,         setFileName]         = useState('');
  const [validationError,  setValidationError]  = useState('');

  useEffect(() => {
    (async () => {
      try {
        const models = await api.models();
        setAllModels(models);
      } catch (e) {
        setLoadError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function runBundled() {
    setRunError(null); setResults(null); setRunning(true);
    try {
      setResults(await api.benchmarkBundled());
    } catch (e) {
      if (e.message && e.message.includes('404')) {
        setRunError('Benchmark endpoint not found. Check frontend/backend route names.');
      } else {
        setRunError(e.message);
      }
    } finally {
      setRunning(false);
    }
  }

  async function runUpload() {
    setValidationError('');
    const file = fileRef.current?.files?.[0];
    if (!file) { setValidationError('Please select a CSV file before clicking Analyze.'); return; }
    setRunError(null); setResults(null); setRunning(true);
    try {
      setResults(await api.benchmarkUploadCsv(file));
    } catch (e) {
      if (e.message && e.message.includes('404')) {
        setRunError('Benchmark endpoint not found. Check frontend/backend route names.');
      } else {
        setRunError(e.message);
      }
    } finally {
      setRunning(false);
    }
  }

  // Resolve results array — backend may return `results` or `per_model_results`
  const allResults       = results?.results ?? results?.per_model_results ?? [];
  const compatResults    = allResults.filter(r => r.benchmark_compatible);
  const skippedResults   = (results?.models_skipped ?? []);
  const modelsRun        = results?.models_run?.length ?? 0;
  const modelsSkipped    = skippedResults.length;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Compatible model benchmark</h1>
          <div className="subtitle">
            Simultaneous benchmark of <strong>4 audit-approved compatible models</strong> against the same
            raw-feature CSV. Only audit-approved compatible models are selectable here —
            all other models remain visible in the registry for comparison/documentation only.
            Benchmark results are <strong>read-only</strong> and do not affect firewall decisions.
          </div>
        </div>
      </div>

      <WarningBox tone="warn">
        <strong>Simulation only.</strong>{' '}
        Only <span className="mono">full_canonical__lgbm</span> is the executable firewall model.{' '}
        <span className="mono">robust9_firewall</span>, <span className="mono">balanced_bagging_3ds_reference</span>,
        and <span className="mono">balanced_bagging_baseline</span> are benchmark-compatible but comparison-only —
        their results do not constitute firewall decisions. No real packets are examined or blocked.
      </WarningBox>

      {loading && <div className="loading-line"><span className="spinner" />Loading registry…</div>}
      {loadError && <div className="error-box">Failed to load: {loadError}</div>}

      {!loading && !loadError && (
        <>
          {/* ── single combined Compatible Benchmark card ── */}
          <div className="section card">
            <h2 style={{ marginTop: 0 }}>Compatible benchmark</h2>
            <p className="dim" style={{ marginTop: 0, marginBottom: 12 }}>
              Run the bundled audit benchmark or upload your own compatible CSV.
              This runs only the <strong>4 audit-approved benchmark-compatible models</strong>.
              Results are benchmark-only and do not affect firewall decisions.
              Only <span className="mono">full_canonical__lgbm</span> is executable as the firewall prototype.
            </p>

            <div className="warning-box info" style={{ marginBottom: 16 }}>
              <span className="icon">ℹ</span>
              <div>
                <strong>Static simultaneous benchmark — not runtime firewall inference.</strong>{' '}
                Bundled CSV: <span className="mono">simultaneous_test_selected_models.csv</span>{' '}
                (7,952 flows, 104 captures). Extra columns are ignored; models with missing required
                features are skipped individually.
              </div>
            </div>

            {/* Bundled benchmark button */}
            <div style={{ marginBottom: 16 }}>
              <button type="button" onClick={runBundled} disabled={running}>
                {running ? <><span className="spinner" /> Running…</> : '▶ Run bundled compatible benchmark'}
              </button>
            </div>

            {/* CSV upload */}
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>Upload compatible CSV</div>
              <p className="dim" style={{ marginTop: 0, marginBottom: 10, fontSize: 13 }}>
                Upload a CSV containing the union of required features for the 4 compatible models.
                Each model selects its own required subset — missing features cause only that model to be skipped.
              </p>
              <div className="mm-file-row">
                <label className="mm-file-label">
                  <input
                    ref={fileRef} type="file" accept=".csv"
                    onChange={(e) => setFileName(e.target.files?.[0]?.name || '')}
                    style={{ display: 'none' }}
                  />
                  <span className="button secondary">Choose CSV</span>
                  {fileName
                    ? <span className="mono" style={{ fontSize: 12 }}>{fileName}</span>
                    : <span className="muted" style={{ fontSize: 12 }}>No file selected</span>
                  }
                </label>
                <button type="button" onClick={runUpload} disabled={running}>
                  {running ? <><span className="spinner" /> Analyzing…</> : 'Analyze uploaded compatible CSV'}
                </button>
              </div>
              {validationError && (
                <div className="error-box" style={{ marginTop: 10 }}>{validationError}</div>
              )}
            </div>
          </div>

          {/* non-compatible section (collapsed) */}
          <div className="section">
            <NonCompatibleSection allModels={allModels} />
          </div>
        </>
      )}

      {runError && (
        <div className="error-box" style={{ marginBottom: 16 }}>
          <strong>Error:</strong> {runError}
        </div>
      )}

      {running && !results && (
        <div className="loading-line"><span className="spinner" />Running benchmark…</div>
      )}

      {results && (
        <div className="section">
          {/* summary bar */}
          <div className="mm-input-summary">
            <span>
              <strong>{results.benchmark_csv_info?.rows ?? '?'}</strong> flows
            </span>
            <span className="dim">·</span>
            <span>
              <strong>{results.benchmark_csv_info?.captures ?? '?'}</strong> captures
            </span>
            <span className="dim">·</span>
            <span>
              <strong>{modelsRun}</strong> model{modelsRun !== 1 ? 's' : ''} run
            </span>
            {modelsSkipped > 0 && (
              <>
                <span className="dim">·</span>
                <span className="badge warn small-badge">
                  <span className="dot" />{modelsSkipped} skipped
                </span>
              </>
            )}
            <span className="badge neutral small-badge"><span className="dot" />benchmark-only</span>
            {results.source && (
              <span className="badge info small-badge"><span className="dot" />{results.source}</span>
            )}
          </div>

          {results.warnings && results.warnings.length > 0 && (
            <WarningBox tone="info">
              {results.warnings.map((w, i) => <div key={i}>{w}</div>)}
            </WarningBox>
          )}

          {/* skipped-model warning */}
          {modelsSkipped > 0 && (
            <WarningBox tone="warn">
              <strong>Skipped models:</strong>{' '}
              {skippedResults.join(', ')}.{' '}
              Check that the CSV contains all required features for those models.
            </WarningBox>
          )}

          {/* results table */}
          <BenchmarkResultsTable results={allResults} />
        </div>
      )}

      <div className="mm-page-footer">
        Compatible model benchmark — only audit-approved models are selectable.{' '}
        Only <code className="mono">full_canonical__lgbm</code> is executable as the firewall prototype.
        All benchmark results are read-only. No real packets are examined or blocked.
        Prototype is not production-ready.
      </div>
    </div>
  );
}
