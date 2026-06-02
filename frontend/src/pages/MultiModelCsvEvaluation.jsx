import React, { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import WarningBox from '../components/WarningBox.jsx';
import StatusBadge from '../components/StatusBadge.jsx';

// ─── helpers ─────────────────────────────────────────────────────────────────

function fmt(v, d = 4) {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return v.toString();
    return v.toFixed(d);
  }
  return String(v);
}

function Bool({ value }) {
  if (value === true)  return <span className="badge ok small-badge"><span className="dot" />yes</span>;
  if (value === false) return <span className="badge neutral small-badge"><span className="dot" />no</span>;
  return <span className="muted">—</span>;
}

/** Render an action label. BLOCK always says "SIMULATED BLOCK". */
function ActionPill({ action }) {
  const cls = action === 'BLOCK' ? 'BLOCK' : action;
  const label = action === 'BLOCK' ? 'SIMULATED BLOCK' : action;
  return <span className={`action-pill ${cls}`}>{label}</span>;
}

/** Inline count tiles: PASS / FLAG_REVIEW / SIMULATED BLOCK */
function CountTiles({ counts }) {
  const p   = counts?.PASS        ?? 0;
  const f   = counts?.FLAG_REVIEW ?? 0;
  const b   = counts?.BLOCK       ?? 0;
  return (
    <div className="mm-count-row">
      <div className="mm-count-tile ok">
        <div className="mm-count-num">{p}</div>
        <div className="mm-count-label">PASS</div>
      </div>
      <div className="mm-count-tile warn">
        <div className="mm-count-num">{f}</div>
        <div className="mm-count-label">FLAG_REVIEW</div>
      </div>
      <div className="mm-count-tile bad">
        <div className="mm-count-num">{b}</div>
        <div className="mm-count-label">SIM. BLOCK</div>
      </div>
    </div>
  );
}

// ─── compatible benchmark components ─────────────────────────────────────────

const COMPATIBLE_MODEL_IDS = [
  'full_canonical__lgbm',
  'robust9_firewall',
  'balanced_bagging_3ds_reference',
  'balanced_bagging_baseline',
];

const INCOMPATIBLE_MODEL_IDS = [
  'balanced_bagging_xgb_baseline',
  'robust13_comparison',
];

/** Read-only list of the 4 compatible models for the benchmark section. */
function BenchmarkModelRoster() {
  return (
    <div className="mm-model-selector" style={{ marginBottom: 12 }}>
      {COMPATIBLE_MODEL_IDS.map((id) => {
        const isFirewall = id === 'full_canonical__lgbm';
        return (
          <div
            key={id}
            className={`mm-model-checkbox-card ${isFirewall ? 'checked default-fw' : ''}`}
            style={{ cursor: 'default' }}
          >
            <div className="mm-checkbox-row">
              <span className="mono" style={{ fontWeight: 600, fontSize: 13 }}>{id}</span>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {isFirewall ? (
                  <span className="badge ok small-badge"><span className="dot" />executable · final model</span>
                ) : (
                  <span className="badge neutral small-badge"><span className="dot" />benchmark comparison</span>
                )}
                <span className="badge info small-badge"><span className="dot" />benchmark-compatible</span>
              </div>
            </div>
            {!isFirewall && (
              <div className="mm-model-warning" style={{ color: 'var(--text-dim)', fontStyle: 'italic', fontSize: 11 }}>
                Benchmark-only — does not affect firewall decisions.
              </div>
            )}
          </div>
        );
      })}
      {INCOMPATIBLE_MODEL_IDS.map((id) => (
        <div
          key={id}
          className="mm-model-checkbox-card"
          style={{ cursor: 'default', opacity: 0.45 }}
        >
          <div className="mm-checkbox-row">
            <span className="mono" style={{ fontWeight: 600, fontSize: 13, textDecoration: 'line-through' }}>{id}</span>
            <span className="badge bad small-badge"><span className="dot" />incompatible</span>
          </div>
          <div className="mm-model-warning" style={{ color: 'var(--text-dim)', fontSize: 11 }}>
            Requires session-derived probability features — excluded from raw-feature simultaneous benchmark.
          </div>
        </div>
      ))}
    </div>
  );
}

/** Comparison table for benchmark results. */
function BenchmarkResultsTable({ benchmarkResult }) {
  if (!benchmarkResult) return null;
  const rows = benchmarkResult.per_model_results || [];

  return (
    <div style={{ marginTop: 16 }}>
      {/* summary banner */}
      <div className="mm-input-summary" style={{ marginBottom: 12 }}>
        <span>
          <strong>{benchmarkResult.benchmark_csv_info?.rows ?? '?'}</strong> flows
        </span>
        <span className="dim">·</span>
        <span>
          <strong>{benchmarkResult.benchmark_csv_info?.captures ?? '?'}</strong> captures
        </span>
        <span className="dim">·</span>
        <span>
          <strong>{benchmarkResult.models_run?.length ?? 0}</strong> model{(benchmarkResult.models_run?.length ?? 0) !== 1 ? 's' : ''} run
        </span>
        {(benchmarkResult.models_skipped?.length ?? 0) > 0 && (
          <>
            <span className="dim">·</span>
            <span className="badge warn small-badge">
              <span className="dot" />{benchmarkResult.models_skipped.length} skipped
            </span>
          </>
        )}
        <span className="badge bad small-badge"><span className="dot" />benchmark-only</span>
      </div>

      {/* global warnings */}
      <div className="warning-box warn" style={{ marginBottom: 12 }}>
        <span className="icon">⚠</span>
        <div>
          <strong>Benchmark-only.</strong> Results do not affect firewall decisions.
          Only <span className="mono">full_canonical__lgbm</span> is executable as the firewall prototype.
        </div>
      </div>

      {/* comparison table */}
      <div className="table-wrap">
        <table className="dash" style={{ fontSize: 12 }}>
          <thead>
            <tr>
              <th>Model</th>
              <th>Role</th>
              <th>Executable</th>
              <th>Compatible</th>
              <th>AUC</th>
              <th>TP</th>
              <th>FP</th>
              <th>TN</th>
              <th>FN</th>
              <th>Rows</th>
              <th>Captures</th>
              <th>Missing features</th>
              <th>Actions (P/R/B)</th>
              <th>Warning</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.model_id}
                style={{
                  opacity: r.skipped ? 0.5 : 1,
                  background: r.model_id === 'full_canonical__lgbm'
                    ? 'rgba(79,157,255,0.05)'
                    : 'transparent',
                }}
              >
                <td className="mono" style={{ fontWeight: r.model_id === 'full_canonical__lgbm' ? 700 : 400 }}>
                  {r.model_id}
                  {r.skipped && (
                    <span className="badge warn small-badge" style={{ marginLeft: 4 }}>skipped</span>
                  )}
                </td>
                <td><span className="mono" style={{ fontSize: 11 }}>{r.role ?? '—'}</span></td>
                <td><Bool value={r.executable} /></td>
                <td><Bool value={r.benchmark_compatible} /></td>
                <td className="num">
                  {r.AUC !== undefined ? (
                    <strong>{fmt(r.AUC, 4)}</strong>
                  ) : '—'}
                </td>
                <td className="num">{r.TP !== undefined ? r.TP : '—'}</td>
                <td className="num">{r.FP !== undefined ? r.FP : '—'}</td>
                <td className="num">{r.TN !== undefined ? r.TN : '—'}</td>
                <td className="num">{r.FN !== undefined ? r.FN : '—'}</td>
                <td className="num">{r.rows_used ?? '—'}</td>
                <td className="num">{r.captures_used ?? '—'}</td>
                <td style={{ fontSize: 11 }}>
                  {r.missing_features && r.missing_features.length > 0
                    ? <span className="mono">{r.missing_features.slice(0, 3).join(', ')}{r.missing_features.length > 3 ? ` +${r.missing_features.length - 3}` : ''}</span>
                    : <span className="muted">none</span>}
                </td>
                <td style={{ fontSize: 11 }}>
                  {r.action_counts
                    ? `${r.action_counts.PASS ?? 0} / ${r.action_counts.FLAG_REVIEW ?? 0} / ${r.action_counts.BLOCK ?? 0}`
                    : '—'}
                </td>
                <td style={{ fontSize: 10, color: 'var(--text-dim)' }}>
                  {r.warning ? r.warning : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* skipped reasons */}
      {rows.filter(r => r.skipped && r.skipped_reason).length > 0 && (
        <div style={{ marginTop: 12 }}>
          {rows.filter(r => r.skipped && r.skipped_reason).map(r => (
            <div key={r.model_id} className="warning-box warn" style={{ marginBottom: 6 }}>
              <span className="icon">⚠</span>
              <div>
                <span className="mono">{r.model_id}</span> skipped — {r.skipped_reason}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── existing session table ───────────────────────────────────────────────────

/** Per-session table for a single model result */
function SessionTable({ sessions }) {
  if (!sessions || sessions.length === 0) {
    return <div className="muted" style={{ fontSize: 12 }}>No sessions.</div>;
  }
  return (
    <div className="table-wrap">
      <table className="dash" style={{ fontSize: 12 }}>
        <thead>
          <tr>
            <th>Session ID</th>
            <th>Flows</th>
            <th>Score</th>
            <th>Strict</th>
            <th>Balanced</th>
            <th>Action</th>
            <th>Simulated</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr key={s.session_id}>
              <td className="mono">{s.session_id}</td>
              <td className="num">{s.n_flows}</td>
              <td className="num"><strong>{fmt(s.session_score)}</strong></td>
              <td><Bool value={s.strict_trigger} /></td>
              <td><Bool value={s.balanced_trigger} /></td>
              <td><ActionPill action={s.action} /></td>
              <td><Bool value={s.simulated} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** One result card for a single model */
function ModelResultCard({ result }) {
  const [expanded, setExpanded] = useState(true);
  const isSkipped  = result.skipped;
  const isDefault  = result.default_firewall;
  const isCmpOnly  = result.comparison_only;

  const cardBorder = isSkipped
    ? 'var(--border)'
    : isDefault
      ? 'rgba(79,157,255,0.35)'
      : 'var(--border)';

  return (
    <div
      className="card mm-result-card"
      style={{ borderColor: cardBorder }}
    >
      {/* ── header ── */}
      <div className="mm-result-header">
        <div className="mm-result-title-row">
          <span className="mono" style={{ fontWeight: 700, fontSize: 14 }}>
            {result.model_id}
          </span>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
            {isDefault && (
              <span className="badge ok small-badge">
                <span className="dot" />Default firewall
              </span>
            )}
            {isCmpOnly && (
              <span className="badge info small-badge">
                <span className="dot" />Comparison-only
              </span>
            )}
            {isSkipped && (
              <span className="badge warn small-badge">
                <span className="dot" />Skipped
              </span>
            )}
            {result.status && <StatusBadge status={result.status} />}
            <span className="badge neutral small-badge">
              <span className="dot" />simulation
            </span>
          </div>
        </div>
        <button
          type="button"
          className="secondary"
          style={{ padding: '4px 10px', fontSize: 12 }}
          onClick={() => setExpanded((v) => !v)}
        >
          {expanded ? '– Collapse' : '+ Expand'}
        </button>
      </div>

      {/* ── skipped state ── */}
      {isSkipped && (
        <div className="warning-box warn" style={{ margin: '10px 0 0' }}>
          <span className="icon">⚠</span>
          <div>
            <strong>Skipped</strong> — CSV is missing required features for this model.
            {result.missing_features && result.missing_features.length > 0 && (
              <ul className="clean" style={{ marginTop: 4 }}>
                {result.missing_features.map((f) => (
                  <li key={f} className="mono" style={{ fontSize: 12 }}>{f}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {/* ── expanded body ── */}
      {expanded && !isSkipped && (
        <div className="mm-result-body">
          {/* metrics row */}
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
              <div className="mm-meta-label">Strict thr</div>
              <div className="mm-meta-val">{fmt(result.thresholds?.strict)}</div>
            </div>
            <div className="mm-meta-item">
              <div className="mm-meta-label">Balanced thr</div>
              <div className="mm-meta-val">{fmt(result.thresholds?.balanced)}</div>
            </div>
            <div className="mm-meta-item">
              <div className="mm-meta-label">Flows</div>
              <div className="mm-meta-val">{result.total_flows}</div>
            </div>
            <div className="mm-meta-item">
              <div className="mm-meta-label">Sessions</div>
              <div className="mm-meta-val">{result.total_sessions}</div>
            </div>
            <div className="mm-meta-item">
              <div className="mm-meta-label">Action mode</div>
              <div className="mm-meta-val mono">{result.action_mode}</div>
            </div>
            <div className="mm-meta-item">
              <div className="mm-meta-label">Prod-ready</div>
              <div className="mm-meta-val">
                <span className="badge bad small-badge">false</span>
              </div>
            </div>
          </div>

          {/* count tiles */}
          <CountTiles counts={result.counts} />

          {/* comparison-only disclaimer */}
          {isCmpOnly && (
            <div className="warning-box info" style={{ margin: '10px 0' }}>
              <span className="icon">ℹ</span>
              Benchmark result only — not deployment-approved.
            </div>
          )}

          {/* warnings from backend */}
          {result.warnings && result.warnings.length > 0 && (
            <div className="mm-warnings">
              {result.warnings.map((w, i) => (
                <div key={i} className="mm-warning-line">⚠ {w}</div>
              ))}
            </div>
          )}

          {/* session table */}
          <div style={{ marginTop: 12 }}>
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--text-dim)',
                marginBottom: 6,
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
              }}
            >
              Per-session decisions (simulated)
            </div>
            <SessionTable sessions={result.sessions} />
          </div>
        </div>
      )}
    </div>
  );
}

// ─── model roster (read-only) ─────────────────────────────────────────────────

const COMPARISON_LABELS = {
  robust9_firewall:          'legacy baseline',
  timing_shape__lgbm:        'benchmark comparison',
  full_canonical__lgbm:      'executable / final model',
  balanced__lgbm:            'benchmark comparison',
  balanced__rf:              'benchmark comparison',
};

function getComparisonLabel(modelId, isDefault) {
  if (isDefault) return 'executable / final model';
  return COMPARISON_LABELS[modelId] || 'comparison-only';
}

function ModelRoster({ runtimeModels }) {
  if (!runtimeModels || runtimeModels.length === 0) return null;
  return (
    <div className="mm-model-selector">
      {runtimeModels.map((m) => {
        const isDefault = m.default_firewall;
        const compLabel = getComparisonLabel(m.model_id, isDefault);
        return (
          <div
            key={m.model_id}
            className={`mm-model-checkbox-card ${isDefault ? 'checked default-fw' : ''}`}
            style={{ cursor: 'default', opacity: isDefault ? 1 : 0.72 }}
          >
            <div className="mm-checkbox-row">
              <span className="mono" style={{ fontWeight: 600, fontSize: 13 }}>
                {m.model_id}
              </span>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {isDefault ? (
                  <span className="badge ok small-badge">
                    <span className="dot" />executable · final model
                  </span>
                ) : (
                  <span className="badge neutral small-badge">
                    <span className="dot" />{compLabel}
                  </span>
                )}
              </div>
            </div>
            <div className="mm-model-meta">
              <span>{m.feature_count} features</span>
              <span className="mono">{m.selected_probability_column}</span>
              <span className="mono">{m.selected_aggregation}</span>
            </div>
            {m.ui_warning && (
              <div className="mm-model-warning">{m.ui_warning}</div>
            )}
            {!isDefault && (
              <div className="mm-model-warning" style={{ color: 'var(--text-dim)', fontStyle: 'italic' }}>
                Read-only — {compLabel}. Not executable in this UI.
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── required features section ────────────────────────────────────────────────

function RequiredFeaturesSection({ featureInfo, runtimeModels }) {
  const [show, setShow] = useState(false);
  if (!featureInfo) return null;
  return (
    <div className="card" style={{ padding: 0 }}>
      <button
        type="button"
        onClick={() => setShow((v) => !v)}
        style={{
          width: '100%',
          textAlign: 'left',
          padding: '12px 16px',
          background: 'transparent',
          color: 'var(--text)',
          border: 'none',
          cursor: 'pointer',
          fontWeight: 600,
          fontSize: 13,
          display: 'flex',
          justifyContent: 'space-between',
        }}
      >
        <span>{show ? '–' : '+'} Required features ({featureInfo.union_feature_count} in union)</span>
        <span className="badge neutral small-badge">
          {(featureInfo.optional_columns || []).join('  ')} optional
        </span>
      </button>
      {show && (
        <div style={{ padding: '0 16px 16px' }}>
          <div className="warning-box info" style={{ marginBottom: 12 }}>
            <span className="icon">ℹ</span>
            <div>
              A model is <strong>skipped</strong> if the uploaded CSV lacks its required columns —
              other models in the same request still run.{' '}
              Labels (<span className="mono">label</span>) are optional for prediction and
              required only for evaluation metrics.
            </div>
          </div>

          <div style={{ marginBottom: 10 }}>
            <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-dim)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Union of all required features ({featureInfo.union_feature_count})
            </div>
            <div className="mm-feature-chips">
              {(featureInfo.union_required_features || []).map((f) => (
                <span key={f} className="mm-feature-chip">{f}</span>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: 10 }}>
            <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-dim)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Optional pass-through columns
            </div>
            <div className="mm-feature-chips">
              {(featureInfo.optional_columns || []).map((f) => (
                <span key={f} className="mm-feature-chip optional">{f}</span>
              ))}
            </div>
          </div>

          {runtimeModels && runtimeModels.map((m) => {
            const perModel = featureInfo.per_model_required_features?.[m.model_id] || [];
            return (
              <details key={m.model_id} className="mm-per-model-features">
                <summary>
                  <span className="mono">{m.model_id}</span>
                  <span className="dim"> — {perModel.length} features</span>
                </summary>
                <div className="mm-feature-chips" style={{ marginTop: 6 }}>
                  {perModel.map((f) => (
                    <span key={f} className="mm-feature-chip">{f}</span>
                  ))}
                </div>
              </details>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── main page ────────────────────────────────────────────────────────────────

const FINAL_MODEL_ID = 'full_canonical__lgbm';

export default function MultiModelCsvEvaluation() {
  const [runtimeModels,  setRuntimeModels]  = useState(null);
  const [featureInfo,    setFeatureInfo]     = useState(null);
  const [loadError,      setLoadError]       = useState(null);
  const [loading,        setLoading]         = useState(true);

  // Final-model results state.
  const [results,   setResults]   = useState(null);
  const [running,   setRunning]   = useState(false);
  const [runError,  setRunError]  = useState(null);

  // Benchmark results state.
  const [benchResults,  setBenchResults]  = useState(null);
  const [benchRunning,  setBenchRunning]  = useState(false);
  const [benchError,    setBenchError]    = useState(null);

  // File inputs.
  const fileRef      = useRef(null);
  const benchFileRef = useRef(null);
  const [fileName,      setFileName]      = useState('');
  const [benchFileName, setBenchFileName] = useState('');

  // Validation errors.
  const [validationError,      setValidationError]      = useState('');
  const [benchValidationError, setBenchValidationError] = useState('');

  // ── load runtime models on mount ──
  useEffect(() => {
    (async () => {
      try {
        const [models, feats] = await Promise.all([
          api.runtimeModels(),
          api.runtimeRequiredFeatures(),
        ]);
        setRuntimeModels(models);
        setFeatureInfo(feats);
      } catch (e) {
        setLoadError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // ── run bundled legacy demo (final model only) ──
  async function runDemo() {
    setRunError(null);
    setResults(null);
    setRunning(true);
    try {
      const data = await api.multimodelDemo();
      setResults(data);
    } catch (e) {
      setRunError(e.message);
    } finally {
      setRunning(false);
    }
  }

  // ── upload & analyze with final model only ──
  async function analyzeFile() {
    setValidationError('');
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setValidationError('Please select a CSV file before clicking Analyze.');
      return;
    }
    setRunError(null);
    setResults(null);
    setRunning(true);
    try {
      const data = await api.analyzeMultimodelCsv(file, FINAL_MODEL_ID);
      setResults(data);
    } catch (e) {
      setRunError(e.message);
    } finally {
      setRunning(false);
    }
  }

  // ── run bundled compatible benchmark ──
  async function runBundledBenchmark() {
    setBenchError(null);
    setBenchResults(null);
    setBenchRunning(true);
    try {
      const data = await api.benchmarkBundled();
      setBenchResults(data);
    } catch (e) {
      setBenchError(e.message);
    } finally {
      setBenchRunning(false);
    }
  }

  // ── upload & run compatible benchmark ──
  async function runBenchmarkUpload() {
    setBenchValidationError('');
    const file = benchFileRef.current?.files?.[0];
    if (!file) {
      setBenchValidationError('Please select a CSV file before clicking Analyze.');
      return;
    }
    setBenchError(null);
    setBenchResults(null);
    setBenchRunning(true);
    try {
      const data = await api.benchmarkUploadCsv(file);
      setBenchResults(data);
    } catch (e) {
      setBenchError(e.message);
    } finally {
      setBenchRunning(false);
    }
  }

  // ── derived ──
  const totalRun     = results?.model_results?.filter((r) => !r.skipped).length ?? 0;
  const totalSkipped = results?.model_results?.filter((r) =>  r.skipped).length ?? 0;

  // ── render ──
  return (
    <div>
      {/* ── page header ── */}
      <div className="page-header">
        <div>
          <h1>Model comparison</h1>
          <div className="subtitle">
            Read-only comparison of registered models.{' '}
            Only <span className="mono">full_canonical__lgbm</span> is executable as the firewall prototype.
            Benchmarking only — firewall decisions remain <strong>simulated</strong>.
          </div>
        </div>
      </div>

      <WarningBox tone="warn">
        <strong>Simulation only.</strong> Only{' '}
        <span className="mono">full_canonical__lgbm</span> is the executable model.
        All other models are shown as{' '}
        <em>legacy baseline</em>, <em>benchmark comparison</em>, <em>negative control</em>,{' '}
        <em>research-only</em>, or <em>unsupported</em>.
        BLOCK decisions are simulated and have no effect on any network.
      </WarningBox>

      {/* ── loading / error ── */}
      {loading && (
        <div className="loading-line">
          <span className="spinner" />Loading model list…
        </div>
      )}
      {loadError && (
        <div className="error-box">
          Failed to load runtime models: {loadError}
        </div>
      )}

      {!loading && !loadError && (
        <>
          {/* ── model roster (read-only) ── */}
          <div className="section">
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--text-dim)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                marginBottom: 8,
              }}
            >
              Registered models — {runtimeModels?.length ?? 0} total
              <span className="badge ok small-badge" style={{ marginLeft: 10 }}>
                <span className="dot" />1 executable
              </span>
            </div>
            <ModelRoster runtimeModels={runtimeModels} />
          </div>

          {/* ── required features (collapsible) ── */}
          <div className="section">
            <RequiredFeaturesSection
              featureInfo={featureInfo}
              runtimeModels={runtimeModels}
            />
          </div>

          {/* ════════════════════════════════════════════════════════════════
              COMPATIBLE BENCHMARK COMPARISON — NEW SECTION
          ════════════════════════════════════════════════════════════════ */}
          <div className="section card" style={{ borderColor: 'rgba(79,157,255,0.3)' }}>
            <h2 style={{ marginTop: 0 }}>Compatible benchmark comparison</h2>
            <p className="dim" style={{ marginTop: 0, marginBottom: 12 }}>
              Upload the audit-generated benchmark CSV or run the bundled compatible benchmark.
              This runs only the 4 models proven compatible with the same raw-feature CSV.
              Results are <strong>benchmark-only</strong> and do not change firewall decisions.
            </p>

            <div className="warning-box info" style={{ marginBottom: 14 }}>
              <span className="icon">ℹ</span>
              <div>
                <strong>Bundled benchmark:</strong>{' '}
                <span className="mono">demo_flows_full_canonical(2).csv</span>{' '}
                — compatible raw-feature benchmark.{' '}
                <span className="badge bad small-badge" style={{ marginLeft: 4 }}>benchmark-only</span>
              </div>
            </div>

            {/* compatible model roster */}
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
                Models in benchmark — 4 compatible · 2 excluded
              </div>
              <BenchmarkModelRoster />
            </div>

            {/* buttons */}
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 14 }}>
              <button type="button" onClick={runBundledBenchmark} disabled={benchRunning}>
                {benchRunning
                  ? <><span className="spinner" /> Running…</>
                  : '▶ Run bundled compatible benchmark'}
              </button>
            </div>

            {/* upload compatible benchmark CSV */}
            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 14 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>
                Upload compatible benchmark CSV
              </div>
              <p className="dim" style={{ marginTop: 0, marginBottom: 10, fontSize: 12 }}>
                Upload <span className="mono">demo_flows_full_canonical(2).csv</span> or a compatible CSV
                with the same raw features. The 4 compatible models will each select their own feature subset.
                Extra columns are ignored. Missing required features skip only that model.
              </p>
              <div className="mm-file-row">
                <label className="mm-file-label">
                  <input
                    ref={benchFileRef}
                    type="file"
                    accept=".csv"
                    onChange={(e) => setBenchFileName(e.target.files?.[0]?.name || '')}
                    style={{ display: 'none' }}
                  />
                  <span className="button secondary"> Choose benchmark CSV</span>
                  {benchFileName
                    ? <span className="mono" style={{ fontSize: 12 }}>{benchFileName}</span>
                    : <span className="muted" style={{ fontSize: 12 }}>No file selected</span>
                  }
                </label>
                <button
                  type="button"
                  onClick={runBenchmarkUpload}
                  disabled={benchRunning}
                >
                  {benchRunning
                    ? <><span className="spinner" /> Analyzing…</>
                    : 'Analyze CSV with compatible benchmark models'}
                </button>
              </div>
              {benchValidationError && (
                <div className="error-box" style={{ marginTop: 10 }}>{benchValidationError}</div>
              )}
            </div>

            {/* benchmark error */}
            {benchError && (
              <div className="error-box" style={{ marginTop: 12 }}>
                <strong>Benchmark error:</strong> {benchError}
              </div>
            )}

            {/* benchmark running indicator */}
            {benchRunning && !benchResults && (
              <div className="loading-line" style={{ marginTop: 12 }}>
                <span className="spinner" />Running benchmark…
              </div>
            )}

            {/* benchmark results table */}
            {benchResults && (
              <BenchmarkResultsTable benchmarkResult={benchResults} />
            )}
          </div>
          {/* ── end compatible benchmark comparison ── */}

          {/* ── bundled legacy demo (final model only) ── */}
          <div className="section card">
            <h2 style={{ marginTop: 0 }}>Bundled demo — small legacy demo only</h2>
            <p className="dim" style={{ marginTop: 0, marginBottom: 8 }}>
              Uses <span className="mono">demo_multimodel_flows.csv</span> (50 flows, 4 sessions).{' '}
              <span className="badge warn small-badge">Small legacy demo only — not the audit benchmark.</span>
              {' '}Runs <span className="mono">full_canonical__lgbm</span> only.
            </p>
            <div className="warning-box info" style={{ marginBottom: 12 }}>
              <span className="icon">ℹ</span>
              <strong>Note:</strong>{' '}
              This is the small 50-flow legacy demo, not the main audit benchmark.
              For the real simultaneous benchmark (7,952 flows, 104 captures), use the{' '}
              <strong>Compatible benchmark comparison</strong> section above.
            </div>
            <button type="button" onClick={runDemo} disabled={running}>
              {running ? <><span className="spinner" /> Running…</> : '▶ Run small legacy demo'}
            </button>
          </div>

          {/* ── CSV upload — final model only ── */}
          <div className="section card">
            <h2 style={{ marginTop: 0 }}>Analyze CSV with final model</h2>
            <p className="dim" style={{ marginTop: 0, marginBottom: 12 }}>
              Runs <span className="mono">full_canonical__lgbm</span> only (34 full-canonical features required).
              Upload a CSV with the full-canonical feature set.
              <br />
              <strong>Note:</strong> This runs only the final firewall model, not all 4 benchmark models.
              For full benchmark comparison, use the <strong>Compatible benchmark comparison</strong> section above.
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
                <span className="button secondary"> Choose CSV file</span>
                {fileName
                  ? <span className="mono" style={{ fontSize: 12 }}>{fileName}</span>
                  : <span className="muted" style={{ fontSize: 12 }}>No file selected</span>
                }
              </label>
              <button
                type="button"
                onClick={analyzeFile}
                disabled={running}
              >
                {running
                  ? <><span className="spinner" /> Analyzing…</>
                  : 'Analyze CSV with final model'
                }
              </button>
            </div>

            {validationError && (
              <div className="error-box" style={{ marginTop: 10 }}>
                {validationError}
              </div>
            )}
          </div>
        </>
      )}

      {/* ── run error (for final model section) ── */}
      {runError && (
        <div className="error-box" style={{ marginBottom: 16 }}>
          <strong>Error:</strong> {runError}
        </div>
      )}

      {/* ── results (final model section) ── */}
      {running && !results && (
        <div className="loading-line">
          <span className="spinner" />Running inference…
        </div>
      )}

      {results && (
        <div className="section">
          {/* input summary banner */}
          <div className="mm-input-summary">
            <span>
              <strong>{results.input_summary?.total_flows ?? '?'}</strong> flows
            </span>
            <span className="dim">·</span>
            <span>
              <strong>{results.input_summary?.total_sessions ?? '?'}</strong> sessions
            </span>
            <span className="dim">·</span>
            <span>
              <strong>{totalRun}</strong> model{totalRun !== 1 ? 's' : ''} scored
            </span>
            {totalSkipped > 0 && (
              <>
                <span className="dim">·</span>
                <span className="badge warn small-badge">
                  <span className="dot" />{totalSkipped} skipped / comparison-only
                </span>
              </>
            )}
            <span className="badge neutral small-badge">
              <span className="dot" />simulation
            </span>
          </div>

          {/* global warnings */}
          {results.warnings && results.warnings.length > 0 && (
            <WarningBox tone="info">
              {results.warnings.map((w, i) => (
                <div key={i}>{w}</div>
              ))}
            </WarningBox>
          )}

          {/* per-model result cards */}
          <div className="mm-results-grid">
            {(results.model_results || []).map((r) => (
              <ModelResultCard key={r.model_id} result={r} />
            ))}
          </div>
        </div>
      )}

      {/* ── footer ── */}
      <div className="mm-page-footer">
        Model comparison page — benchmarking and audit only.{' '}
        Only <code className="mono">full_canonical__lgbm</code> is executable as the firewall prototype.
        Firewall decisions remain simulation-only. No real packets are examined or blocked.
      </div>
    </div>
  );
}
