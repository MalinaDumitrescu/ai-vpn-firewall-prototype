import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import StatusBadge from '../components/StatusBadge.jsx';
import WarningBox from '../components/WarningBox.jsx';

const COLUMNS = [
  { key: 'model_id',              label: 'Model' },
  { key: 'ui_badge',              label: 'Role' },
  { key: 'status',                label: 'Status' },
  { key: 'session_auc_test',      label: 'Session AUC' },
  { key: 'strict_test_recall',    label: 'Strict recall' },
  { key: 'strict_test_fpr',       label: 'Strict FPR' },
  { key: 'balanced_test_recall',  label: 'Balanced recall' },
  { key: 'balanced_test_fpr',     label: 'Balanced FPR' },
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
                const isNum =
                  c.key.includes('recall') ||
                  c.key.includes('fpr') ||
                  c.key.includes('auc');
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
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const [m, a] = await Promise.all([
          api.mainComparison(),
          api.advancedBenchmarks(),
        ]);
        setMain(m);
        setAdvanced(a);
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
            Six curated demo models from{' '}
            <span className="mono">ui_model_groups.json → main_demo_comparison</span>.
            Aliases, unsupported stubs, and LODO negative controls are excluded
            from this view by design.
          </div>
        </div>
      </div>

      <WarningBox tone="info">
        Only <strong>robust9_firewall</strong> is deployment-approved (in
        simulation mode). The other five rows are <em>policy_computed</em>
        baselines and ablations shown for benchmarking — not for deployment.
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
    </div>
  );
}