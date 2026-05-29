import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import StatusBadge from '../components/StatusBadge.jsx';
import WarningBox from '../components/WarningBox.jsx';

const COLUMNS = [
  { key: 'model_id',              label: 'Model' },
  { key: 'ui_badge',              label: 'Role' },
  { key: 'status',                label: 'Status' },
  { key: 'pooled_auc',            label: 'Pooled AUC' },
  { key: 'lodo_min_auc',          label: 'LODO-min AUC' },
  { key: 'domain_auc',            label: 'Domain AUC' },
  { key: 'fpr_at_0.5',            label: 'FPR' },
  { key: 'ece',                   label: 'ECE' },
  { key: 'session_auc_test',      label: 'Session AUC' },
  { key: 'strict_test_fpr',       label: 'Strict FPR' },
  { key: 'runtime_compatible',    label: 'Runtime compat.' },
  { key: 'deployment_eligible',   label: 'Deploy eligible' },
  { key: 'recommendation',        label: 'Recommendation' },
];

function fmt(v) {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return v.toString();
    return v.toFixed(4);
  }
  return String(v);
}

function ComparisonTable({ rows }) {
  return (
    <div className="table-wrap">
      <table className="dash">
        <thead>
          <tr>
            {COLUMNS.map((c) => <th key={c.key}>{c.label}</th>)}
            <th>Warning</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.model_id}>
              {COLUMNS.map((c) => {
                if (c.key === 'model_id') {
                  return <td key={c.key} className="mono">{r.model_id}</td>;
                }
                if (c.key === 'status') {
                  return (
                    <td key={c.key}>
                      {r.status ? <StatusBadge status={r.status} /> : '—'}
                    </td>
                  );
                }
                if (c.key === 'ui_badge') {
                  return (
                    <td key={c.key} style={{ fontSize: 12 }}>
                      {r.ui_badge || '—'}
                    </td>
                  );
                }
                const isBool =
                  c.key === 'runtime_compatible' ||
                  c.key === 'deployment_eligible';
                if (isBool) {
                  const val = r[c.key];
                  const label = val === true ? '✓ yes' : val === false ? '✗ no' : '—';
                  const color = val === true ? 'var(--ok)' : val === false ? 'var(--bad)' : 'var(--text-dim)';
                  return (
                    <td key={c.key} style={{ fontSize: 12, color }}>
                      {label}
                    </td>
                  );
                }
                if (c.key === 'recommendation') {
                  return (
                    <td key={c.key} style={{ fontSize: 12, color: 'var(--text-dim)', maxWidth: 220 }}>
                      {r.recommendation || '—'}
                    </td>
                  );
                }
                const isNum =
                  c.key.includes('recall') ||
                  c.key.includes('fpr') ||
                  c.key.includes('auc') ||
                  c.key === 'ece';
                return (
                  <td key={c.key} className={isNum ? 'num' : 'mono'}>
                    {fmt(r[c.key])}
                  </td>
                );
              })}
              <td style={{ fontSize: 12, color: 'var(--text-dim)', maxWidth: 320 }}>
                {r.ui_warning || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ModelComparison() {
  const [main, setMain] = useState(null);
  const [advanced, setAdvanced] = useState(null);
  const [research, setResearch] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showResearch, setShowResearch] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [m, a, uiGroups] = await Promise.all([
          api.mainComparison(),
          api.advancedBenchmarks(),
          api.uiGroups(),
        ]);
        setMain(m);
        setAdvanced(a);
        // Extract research_only models from ui groups if available
        const researchIds = uiGroups?.groups?.research_only || [];
        const allModels = await api.models();
        if (researchIds.length > 0 && allModels) {
          const researchRows = researchIds
            .map((id) => ({ model_id: id, ...allModels[id] }))
            .filter((r) => r.model_id);
          setResearch(researchRows);
        }
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Model comparison</h1>
          <div className="subtitle">
            Curated models from the registry. Columns show final research metrics
            where available: <span className="mono">pooled_auc</span>,{' '}
            <span className="mono">lodo_min_auc</span>,{' '}
            <span className="mono">domain_auc</span>,{' '}
            <span className="mono">fpr</span>, <span className="mono">ece</span>,
            runtime compatibility, and deployment eligibility.
          </div>
        </div>
      </div>

      <WarningBox tone="info">
        <strong>full_canonical__lgbm</strong> is the final recommended firewall model —
        executable / deployment-eligible / simulation-only / best known-domain prototype.{' '}
        <strong>robust9_firewall</strong> is retained as a legacy baseline / comparison-only — not the recommended model.{' '}
        <strong>timing_shape__lgbm</strong> is a benchmark comparison / diagnostic only.
        DANN v2 is research-only and did not meaningfully reduce fingerprinting.
        All rows are simulation-only — no packets are blocked.
      </WarningBox>

      {loading && <div className="loading-line"><span className="spinner" />Loading comparison…</div>}
      {error && <div className="error-box">Failed to load comparison: {error}</div>}

      {!loading && !error && main && <ComparisonTable rows={main} />}

      {!loading && !error && advanced && advanced.length > 0 && (
        <div className="section">
          <div className="card" style={{ padding: 0 }}>
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              style={{
                width: '100%',
                textAlign: 'left',
                padding: '14px 18px',
                background: 'transparent',
                color: 'var(--text)',
                border: 'none',
                cursor: 'pointer',
                fontSize: 15,
                fontWeight: 600,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <span>
                <span style={{ marginRight: 8 }}>{showAdvanced ? '▾' : '▸'}</span>
                Advanced unsafe benchmarks
                <span className="dim" style={{ marginLeft: 10, fontWeight: 400, fontSize: 12 }}>
                  ({advanced.length} models, hidden by default)
                </span>
              </span>
              <StatusBadge tone="bad" label="Do not deploy" />
            </button>

            {showAdvanced && (
              <div style={{ padding: '0 18px 18px 18px' }}>
                <WarningBox tone="bad">
                  <strong>Blocking disabled — nonzero strict FPR.</strong>{' '}
                  These models are shown only to explain why we did not pick
                  them. They must never be used to drive firewall actions, even
                  in simulation.
                </WarningBox>
                <ComparisonTable rows={advanced} />
              </div>
            )}
          </div>
        </div>
      )}

      {!loading && !error && research && research.length > 0 && (
        <div className="section">
          <div className="card" style={{ padding: 0 }}>
            <button
              type="button"
              onClick={() => setShowResearch((v) => !v)}
              style={{
                width: '100%',
                textAlign: 'left',
                padding: '14px 18px',
                background: 'transparent',
                color: 'var(--text)',
                border: 'none',
                cursor: 'pointer',
                fontSize: 15,
                fontWeight: 600,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <span>
                <span style={{ marginRight: 8 }}>{showResearch ? '▾' : '▸'}</span>
                DANN v2 &amp; research-only candidates
                <span className="dim" style={{ marginLeft: 10, fontWeight: 400, fontSize: 12 }}>
                  ({research.length} model{research.length !== 1 ? 's' : ''}, not selected)
                </span>
              </span>
              <StatusBadge tone="warn" label="Research only" />
            </button>

            {showResearch && (
              <div style={{ padding: '0 18px 18px 18px' }}>
                <WarningBox tone="warn">
                  <strong>Research only — not selected for deployment.</strong>{' '}
                  DANN v2 adversarial training did not meaningfully reduce
                  embedding-domain fingerprinting (<span className="mono">domain_reduction ≈ 0.0003</span>).
                  These models are not runtime-compatible and must not be used for firewall actions.
                </WarningBox>
                <ComparisonTable rows={research} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}