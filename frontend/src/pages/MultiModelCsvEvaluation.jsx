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

// ─── Compatible model info card ───────────────────────────────────────────────

const COMPAT_BADGES = {
  full_canonical__lgbm:          { label: 'EXECUTABLE · FINAL MODEL', tone: 'ok' },
  robust9_firewall:              { label: 'LEGACY BASELINE',           tone: 'neutral' },
  balanced_bagging_3ds_reference:{ label: 'BENCHMARK COMPARISON',      tone: 'info' },
  balanced_bagging_baseline:     { label: 'BENCHMARK COMPARISON',      tone: 'info' },
};

function CompatibleModelCard({ modelId, entry }) {
  const badge = COMPAT_BADGES[modelId] || { label: 'BENCHMARK COMPATIBLE', tone: 'info' };
  const isExec = modelId === EXECUTABLE_MODEL_ID;
  return (
    <div
      className="card mm-model-checkbox-card"
      style={{ borderColor: isExec ? 'rgba(79,157,255,0.5)' : 'var(--border)', cursor: 'default' }}
    >
      <div className="mm-checkbox-row">
        <span className="mono" style={{ fontWeight: 700, fontSize: 13 }}>{modelId}</span>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className={`badge ${badge.tone} small-badge`}>
            <span className="dot" />{badge.label}
          </span>
          <span className="badge ok small-badge">
            <span className="dot" />benchmark compatible
          </span>
        </div>
      </div>
      <div className="mm-model-meta">
        {entry?.n_features && <span>{entry.n_features} features</span>}
        {entry?.feature_family && <span className="mono">{entry.feature_family}</span>}
        {entry?.selected_probability_column && <span className="mono">{entry.selected_probability_column}</span>}
        {entry?.selected_aggregation && <span className="mono">{entry.selected_aggregation}</span>}
      </div>
      {isExec ? (
        <div className="mm-model-warning" style={{ color: 'var(--ok)', fontStyle: 'italic', fontSize: 12 }}>
          Executable firewall model — also included in benchmark comparison.
        </div>
      ) : (
        <div className="mm-model-warning" style={{ color: 'var(--text-dim)', fontStyle: 'italic', fontSize: 12 }}>
          Comparison-only. Benchmark results do not affect firewall decisions.
        </div>
      )}
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

// ─── Benchmark result card ───────────────────────────────────────────────────

function BenchmarkResultCard({ result }) {
  const [expanded, setExpanded] = useState(true);
  const isExec    = result.executable;
  const isSkipped = result.skipped;
  const role      = result.role || (isExec ? 'recommended_firewall' : 'benchmark_comparison');
  const counts    = result.action_counts || {};

  const roleBadge =
    isExec          ? { label: 'EXECUTABLE · FINAL MODEL', tone: 'ok' } :
    role === 'legacy_baseline'
                    ? { label: 'LEGACY BASELINE',           tone: 'neutral' } :
                      { label: 'BENCHMARK COMPARISON',      tone: 'info' };

  return (
    <div className="card mm-result-card" style={{ borderColor: isExec ? 'rgba(79,157,255,0.4)' : 'var(--border)' }}>
      <div className="mm-result-header">
        <div className="mm-result-title-row">
          <span className="mono" style={{ fontWeight: 700, fontSize: 14 }}>{result.model_id}</span>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
            <span className={`badge ${roleBadge.tone} small-badge`}>
              <span className="dot" />{roleBadge.label}
            </span>
            {result.benchmark_compatible && !isSkipped && (
              <span className="badge ok small-badge"><span className="dot" />benchmark compatible</span>
            )}
            {isSkipped && <span className="badge warn small-badge"><span className="dot" />skipped</span>}
            <span className="badge neutral small-badge"><span className="dot" />benchmark-only</span>
          </div>
        </div>
        <button
          type="button" className="secondary"
          style={{ padding: '4px 10px', fontSize: 12 }}
          onClick={() => setExpanded(v => !v)}
        >
          {expanded ? '▾ Collapse' : '▸ Expand'}
        </button>
      </div>

      {isSkipped && (
        <div className="warning-box warn" style={{ margin: '10px 0 0' }}>
          <span className="icon">⚠</span>
          <div>
            <strong>Skipped</strong> — {result.skipped_reason || 'Missing required features.'}
            {result.missing_features && result.missing_features.length > 0 && (
              <ul className="clean" style={{ marginTop: 4 }}>
                {result.missing_features.map(f => (
                  <li key={f} className="mono" style={{ fontSize: 12 }}>{f}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {expanded && !isSkipped && (
        <div className="mm-result-body">
          <div className="mm-meta-grid">
            <div className="mm-meta-item">
              <div className="mm-meta-label">Prob column</div>
              <div className="mm-meta-val mono">{result.probability_column || '—'}</div>
            </div>
            <div className="mm-meta-item">
              <div className="mm-meta-label">Aggregation</div>
              <div className="mm-meta-val mono">{result.aggregation || '—'}</div>
            </div>
            <div className="mm-meta-item">
              <div className="mm-meta-label">Block thr.</div>
              <div className="mm-meta-val">{fmt(result.block_threshold_used, 6)}</div>
            </div>
            <div className="mm-meta-item">
              <div className="mm-meta-label">Rows used</div>
              <div className="mm-meta-val">{result.rows_used ?? '—'}</div>
            </div>
            <div className="mm-meta-item">
              <div className="mm-meta-label">Captures</div>
              <div className="mm-meta-val">{result.captures_used ?? '—'}</div>
            </div>
            {result.AUC !== undefined && (
              <div className="mm-meta-item">
                <div className="mm-meta-label">AUC</div>
                <div className="mm-meta-val" style={{ color: 'var(--ok)', fontWeight: 700 }}>
                  {fmt(result.AUC)}
                </div>
              </div>
            )}
            <div className="mm-meta-item">
              <div className="mm-meta-label">Benchmark</div>
              <div className="mm-meta-val"><span className="badge info small-badge">result only</span></div>
            </div>
            <div className="mm-meta-item">
              <div className="mm-meta-label">Prod-ready</div>
              <div className="mm-meta-val"><span className="badge bad small-badge">false</span></div>
            </div>
          </div>

          <div className="mm-count-row">
            <div className="mm-count-tile ok">
              <div className="mm-count-num">{counts.PASS ?? 0}</div>
              <div className="mm-count-label">PASS</div>
            </div>
            <div className="mm-count-tile warn">
              <div className="mm-count-num">{counts.FLAG_REVIEW ?? 0}</div>
              <div className="mm-count-label">FLAG_REVIEW</div>
            </div>
            <div className="mm-count-tile bad">
              <div className="mm-count-num">{counts.BLOCK ?? 0}</div>
              <div className="mm-count-label">SIM. BLOCK</div>
            </div>
          </div>

          {(result.TP !== undefined || result.FP !== undefined) && (
            <div className="mm-meta-grid" style={{ marginTop: 10 }}>
              {[['TP', result.TP], ['FP', result.FP], ['TN', result.TN], ['FN', result.FN]].map(([k, v]) => (
                <div className="mm-meta-item" key={k}>
                  <div className="mm-meta-label">{k}</div>
                  <div className="mm-meta-val">{v ?? '—'}</div>
                </div>
              ))}
            </div>
          )}

          <div className="warning-box info" style={{ margin: '10px 0 0' }}>
            <span className="icon">ℹ</span>
            Benchmark result only — does not affect firewall decisions.
          </div>
          {result.warning && (
            <div className="mm-warnings" style={{ marginTop: 6 }}>
              <div className="mm-warning-line">⚠ {result.warning}</div>
            </div>
          )}
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

  const compatibleEntries = BENCHMARK_COMPATIBLE_IDS.map(id => ({
    id, entry: allModels?.[id] || {},
  }));

  async function runBundled() {
    setRunError(null); setResults(null); setRunning(true);
    try { setResults(await api.benchmarkBundled()); }
    catch (e) { setRunError(e.message); }
    finally { setRunning(false); }
  }

  async function runUpload() {
    setValidationError('');
    const file = fileRef.current?.files?.[0];
    if (!file) { setValidationError('Please select a CSV file before clicking Analyze.'); return; }
    setRunError(null); setResults(null); setRunning(true);
    try { setResults(await api.benchmarkUploadCsv(file)); }
    catch (e) { setRunError(e.message); }
    finally { setRunning(false); }
  }

  const modelsRun     = results?.models_run?.length ?? 0;
  const modelsSkipped = results?.models_skipped?.length ?? 0;

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
          {/* compatible models */}
          <div className="section">
            <div style={{
              fontSize: 12, fontWeight: 600, color: 'var(--text-dim)',
              textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8,
            }}>
              Audit-approved benchmark-compatible models
              <span className="badge ok small-badge" style={{ marginLeft: 10 }}>
                <span className="dot" />{BENCHMARK_COMPATIBLE_IDS.length} selectable
              </span>
            </div>
            <div className="mm-model-selector">
              {compatibleEntries.map(({ id, entry }) => (
                <CompatibleModelCard key={id} modelId={id} entry={entry} />
              ))}
            </div>
          </div>

          {/* non-compatible section (collapsed) */}
          <div className="section">
            <NonCompatibleSection allModels={allModels} />
          </div>

          {/* bundled benchmark */}
          <div className="section card">
            <h2 style={{ marginTop: 0 }}>Bundled benchmark</h2>
            <p className="dim" style={{ marginTop: 0, marginBottom: 8 }}>
              Uses <span className="mono">simultaneous_test_selected_models.csv</span> (7,952 flows, 104 captures).
              Runs all 4 compatible models simultaneously.
            </p>
            <div className="warning-box info" style={{ marginBottom: 12 }}>
              <span className="icon">ℹ</span>
              <strong>Static simultaneous benchmark — not runtime firewall inference.</strong>{' '}
              Only <span className="mono">full_canonical__lgbm</span> results represent executable inference.
              All others are benchmark comparison only.
            </div>
            <button type="button" onClick={runBundled} disabled={running}>
              {running ? <><span className="spinner" /> Running…</> : '▶ Run compatible benchmark'}
            </button>
          </div>

          {/* CSV upload */}
          <div className="section card">
            <h2 style={{ marginTop: 0 }}>Analyze CSV with benchmark-compatible models</h2>
            <p className="dim" style={{ marginTop: 0, marginBottom: 12 }}>
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
                <span className="button secondary">Choose CSV file</span>
                {fileName
                  ? <span className="mono" style={{ fontSize: 12 }}>{fileName}</span>
                  : <span className="muted" style={{ fontSize: 12 }}>No file selected</span>
                }
              </label>
              <button type="button" onClick={runUpload} disabled={running}>
                {running ? <><span className="spinner" /> Analyzing…</> : 'Analyze CSV with benchmark-compatible models'}
              </button>
            </div>
            {validationError && (
              <div className="error-box" style={{ marginTop: 10 }}>{validationError}</div>
            )}
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

          <div className="mm-results-grid">
            {(results.per_model_results || []).map(r => (
              <BenchmarkResultCard key={r.model_id} result={r} />
            ))}
          </div>
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
