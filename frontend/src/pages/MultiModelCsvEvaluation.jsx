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
          {expanded ? '▾ Collapse' : '▸ Expand'}
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

// ─── model selector ───────────────────────────────────────────────────────────

function ModelSelector({ runtimeModels, selected, onToggle }) {
  if (!runtimeModels || runtimeModels.length === 0) return null;
  return (
    <div className="mm-model-selector">
      {runtimeModels.map((m) => {
        const checked = selected.has(m.model_id);
        const isDefault = m.default_firewall;
        return (
          <label
            key={m.model_id}
            className={`mm-model-checkbox-card ${checked ? 'checked' : ''} ${isDefault ? 'default-fw' : ''}`}
          >
            <div className="mm-checkbox-row">
              <input
                type="checkbox"
                checked={checked}
                onChange={() => onToggle(m.model_id)}
              />
              <span className="mono" style={{ fontWeight: 600, fontSize: 13 }}>
                {m.model_id}
              </span>
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {isDefault && (
                  <span className="badge ok small-badge">
                    <span className="dot" />Default FW
                  </span>
                )}
                {!isDefault && (
                  <span className="badge info small-badge">
                    <span className="dot" />Comparison
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
          </label>
        );
      })}
    </div>
  );
}

// ─── required features section ───────────────────────────────────────────────

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
        <span>{show ? '▾' : '▸'} Required features ({featureInfo.union_feature_count} in union)</span>
        <span className="badge neutral small-badge">
          {(featureInfo.optional_columns || []).join(' · ')} optional
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

export default function MultiModelCsvEvaluation() {
  const [runtimeModels,  setRuntimeModels]  = useState(null);
  const [featureInfo,    setFeatureInfo]     = useState(null);
  const [loadError,      setLoadError]       = useState(null);
  const [loading,        setLoading]         = useState(true);

  // Selected model IDs (Set).
  const [selected, setSelected] = useState(new Set());

  // Results state.
  const [results,   setResults]   = useState(null);  // { input_summary, model_results, ... }
  const [running,   setRunning]   = useState(false);
  const [runError,  setRunError]  = useState(null);

  // File input.
  const fileRef = useRef(null);
  const [fileName, setFileName] = useState('');

  // Validation errors.
  const [validationError, setValidationError] = useState('');

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
        // Default: all models checked.
        setSelected(new Set(models.map((m) => m.model_id)));
      } catch (e) {
        setLoadError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  function toggleModel(id) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // ── run demo ──
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

  // ── upload & analyze ──
  async function analyzeFile() {
    setValidationError('');
    const file = fileRef.current?.files?.[0];
    if (!file) {
      setValidationError('Please select a CSV file before clicking Analyze.');
      return;
    }
    if (selected.size === 0) {
      setValidationError('Select at least one model before analyzing.');
      return;
    }
    setRunError(null);
    setResults(null);
    setRunning(true);
    try {
      const ids = [...selected].join(',');
      const data = await api.analyzeMultimodelCsv(file, ids);
      setResults(data);
    } catch (e) {
      setRunError(e.message);
    } finally {
      setRunning(false);
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
          <h1>Multi-model CSV evaluation</h1>
          <div className="subtitle">
            Run all selected runtime models on the same CSV and compare results
            side-by-side. <strong>Simulation only</strong> — no packets are blocked.
          </div>
        </div>
      </div>

      <WarningBox tone="warn">
        <strong>Simulation only.</strong> This compares selected runtime models on the same
        uploaded CSV. It does not deploy or block traffic. BLOCK decisions are simulated and
        have no effect on any network.
      </WarningBox>

      {/* ── loading / error ── */}
      {loading && (
        <div className="loading-line">
          <span className="spinner" />Loading runtime model list…
        </div>
      )}
      {loadError && (
        <div className="error-box">
          Failed to load runtime models: {loadError}
        </div>
      )}

      {!loading && !loadError && (
        <>
          {/* ── model selector ── */}
          <div className="section">
            <div
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: 'var(--text-dim)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                marginBottom: 10,
              }}
            >
              Select runtime models ({selected.size} / {runtimeModels?.length ?? 0} selected)
            </div>
            <ModelSelector
              runtimeModels={runtimeModels}
              selected={selected}
              onToggle={toggleModel}
            />
          </div>

          {/* ── required features (collapsible) ── */}
          <div className="section">
            <RequiredFeaturesSection
              featureInfo={featureInfo}
              runtimeModels={runtimeModels}
            />
          </div>

          {/* ── demo button ── */}
          <div className="section card">
            <h2 style={{ marginTop: 0 }}>Run bundled multi-model demo</h2>
            <p className="dim" style={{ marginTop: 0, marginBottom: 12 }}>
              Uses <span className="mono">demo_multimodel_flows.csv</span> (50 flows, 4 sessions)
              and runs <strong>all 5 runtime allowlist models</strong> regardless of
              checkbox selection above.
            </p>
            <button type="button" onClick={runDemo} disabled={running}>
              {running ? <><span className="spinner" /> Running…</> : '▶ Run multi-model demo'}
            </button>
          </div>

          {/* ── CSV upload ── */}
          <div className="section card">
            <h2 style={{ marginTop: 0 }}>Analyze uploaded CSV</h2>
            <p className="dim" style={{ marginTop: 0, marginBottom: 12 }}>
              Models whose required features are absent in your CSV will be gracefully
              skipped — other selected models still run.
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
                disabled={running || selected.size === 0}
              >
                {running
                  ? <><span className="spinner" /> Analyzing…</>
                  : `Analyze CSV (${selected.size} model${selected.size !== 1 ? 's' : ''})`
                }
              </button>
            </div>

            {validationError && (
              <div className="error-box" style={{ marginTop: 10 }}>
                {validationError}
              </div>
            )}
            {selected.size === 0 && (
              <div className="warning-box warn" style={{ marginTop: 10 }}>
                <span className="icon">⚠</span>
                Select at least one model to analyze.
              </div>
            )}
          </div>
        </>
      )}

      {/* ── run error ── */}
      {runError && (
        <div className="error-box" style={{ marginBottom: 16 }}>
          <strong>Error:</strong> {runError}
        </div>
      )}

      {/* ── results ── */}
      {running && !results && (
        <div className="loading-line">
          <span className="spinner" />Running inference across selected models…
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
                  <span className="dot" />{totalSkipped} skipped
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
        Multi-model CSV evaluation is for benchmarking only. Firewall decisions
        remain simulation-only. No real packets are examined or blocked.
      </div>
    </div>
  );
}
