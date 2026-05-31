import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import SummaryCard from '../components/SummaryCard.jsx';
import WarningBox from '../components/WarningBox.jsx';
import StatusBadge from '../components/StatusBadge.jsx';
import GooseMascot from '../components/GooseMascot.jsx';

function num(v, d = 4) {
  if (v === null || v === undefined) return '—';
  if (typeof v !== 'number') return String(v);
  if (Number.isInteger(v)) return v.toString();
  return v.toFixed(d);
}

const BADGE_ACCENT = { good: 'ok', moderate: 'warn', improved: 'info', warn: 'bad', best: 'ok' };

/** Small inline metric chip. */
function MetricChip({ label, value, badge }) {
  const accent = BADGE_ACCENT[badge] || 'neutral';
  return (
    <div className={`metric-chip metric-chip--${accent}`}>
      <span className="metric-chip__label">{label}</span>
      <span className="metric-chip__value">{value}</span>
    </div>
  );
}

export default function Dashboard() {
  const [health, setHealth]             = useState(null);
  const [defaultModel, setDefaultModel] = useState(null);
  const [pageContent, setPageContent]   = useState(null);
  const [cards, setCards]               = useState(null);
  const [error, setError]               = useState(null);
  const [loading, setLoading]           = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [h, m, pc, c] = await Promise.all([
          api.health(),
          api.defaultModel(),
          api.modelDetailsFrontendContent().catch(() => null),
          api.modelDetailsCards().catch(() => null),
        ]);
        if (cancelled) return;
        setHealth(h);
        setDefaultModel(m);
        setPageContent(pc);
        setCards(c);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const dash = pageContent?.pages?.Dashboard;
  const compactMetrics = dash?.compact_metrics ?? [];
  const limitationNotes = dash?.limitation_notes ?? [];
  const activeSummary = dash?.active_model_summary;

  // LODO and domain fingerprinting from model cards
  const activeCard = cards?.cards?.['unified_relative_shape_v2__lgbm'];
  const lodoCols = [
    { key: 'lodo_iscx_auc', label: 'LODO ISCX' },
    { key: 'lodo_vnat_auc', label: 'LODO VNAT' },
    { key: 'lodo_mean_auc', label: 'LODO mean' },
    { key: 'lodo_min_auc',  label: 'LODO min'  },
  ];
  const lodoRows = activeCard
    ? lodoCols.filter(({ key }) => activeCard.metrics?.[key] != null)
    : [];

  return (
    <div>

      {/* ── Page header row with guardian goose ──────────────────────── */}
      <div className="dash-goose-row">
        <div>
          <h1>System Overview</h1>
          <div className="subtitle">Live model status · Simulation only · Not for production</div>
        </div>
        <GooseMascot
          size="small"
          variant={loading ? 'watching' : error ? 'alert' : 'idle'}
          style={{ opacity: 0.78, marginTop: 4 }}
        />
      </div>

      <WarningBox tone="warn">
        <strong>Simulation only — no packets are blocked.</strong>{' '}
        <span className="mono">unified_relative_shape_v2__lgbm</span> is the selected unified-feature prototype.
        It is methodologically cleaner than the legacy mixed-feature model, but it is still not production-ready.
      </WarningBox>

      {loading && (
        <div className="goose-empty-state">
          <GooseMascot size="medium" variant="watching" style={{ opacity: 0.7 }} />
          <div className="loading-line" style={{ justifyContent: 'center' }}>
            <span className="spinner" />Loading system status…
          </div>
        </div>
      )}
      {error && (
        <div className="goose-empty-state">
          <GooseMascot size="medium" variant="alert" />
          <div className="error-box">Failed to reach API: {error}</div>
        </div>
      )}

      {!loading && !error && (
        <>
          {/* ── Active model identity chips from metadata package ─── */}
          {activeSummary && (
            <div className="card" style={{ marginBottom: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
                <div>
                  <h2 style={{ margin: 0 }}>{activeSummary.display_name}</h2>
                  <div className="dim" style={{ fontSize: 12, marginTop: 2 }}>
                    {activeSummary.role} · <span className="mono">{activeSummary.feature_family}</span> · {activeSummary.n_features} features · extractor {activeSummary.extractor_version}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <span className="badge ok">CURRENT MODEL</span>
                  <span className="badge info">EXECUTABLE</span>
                  <span className="badge warn">SIMULATION ONLY</span>
                </div>
              </div>
              {compactMetrics.length > 0 && (
                <div className="metric-chips-row">
                  {compactMetrics.map((m) => (
                    <MetricChip key={m.label} label={m.label} value={m.value} badge={m.badge} />
                  ))}
                </div>
              )}
              {limitationNotes.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <div className="dim" style={{ fontSize: 11, fontWeight: 600, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Known limitations</div>
                  <ul className="clean" style={{ fontSize: 12, margin: 0, paddingLeft: 0 }}>
                    {limitationNotes.map((note, i) => (
                      <li key={i} style={{ padding: '3px 0', color: 'var(--text-dim)', display: 'flex', gap: 6 }}>
                        <span style={{ color: 'var(--warn)', flexShrink: 0 }}>⚠</span>
                        {note}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* ── LODO mini-table + domain fingerprinting trend ─────────── */}
          <div className="section grid cols-2" style={{ marginBottom: 18 }}>
            {/* LODO mini-table */}
            <div className="card">
              <h2 style={{ marginBottom: 8 }}>LODO transfer summary</h2>
              <p className="dim" style={{ fontSize: 12, marginTop: 0, marginBottom: 10 }}>
                Leave-one-dataset-out AUC for <span className="mono">unified_relative_shape_v2__lgbm</span>.
                Below 0.7 = weak cross-domain transfer.
              </p>
              {lodoRows.length > 0 ? (
                <table className="feature-table">
                  <thead><tr><th>Split</th><th>AUC</th></tr></thead>
                  <tbody>
                    {lodoRows.map(({ key, label }) => {
                      const v = activeCard.metrics[key];
                      const weak = v < 0.7;
                      return (
                        <tr key={key}>
                          <td className="mono" style={{ fontSize: 12 }}>{label}</td>
                          <td style={{ fontWeight: 700, color: weak ? 'var(--warn)' : 'var(--ok)' }}>{v?.toFixed(4)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              ) : (
                <div className="dim" style={{ fontSize: 12 }}>
                  LODO-ISCX: 0.6366 · LODO-VNAT: 0.9560 · Mean: 0.7963 · Min: 0.6366
                </div>
              )}
              <div className="dim" style={{ fontSize: 11, marginTop: 8 }}>
                ISCX is the hardest held-out domain — model trained without it scores near-randomly.
              </div>
            </div>

            {/* Domain fingerprinting trend */}
            <div className="card">
              <h2 style={{ marginBottom: 8 }}>Domain fingerprinting — trend vs legacy</h2>
              <p className="dim" style={{ fontSize: 12, marginTop: 0, marginBottom: 10 }}>
                Domain AUC = classifier ability to identify source dataset from features.
                1.0 = perfect fingerprinting. 0.5 = random (ideal).
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[
                  { label: 'Legacy full_canonical__lgbm',       auc: 1.0,    cls: 'var(--bad)' },
                  { label: 'unified_relative_shape_v2__lgbm ★', auc: 0.9591, cls: 'var(--warn)' },
                ].map(({ label, auc, cls }) => (
                  <div key={label}>
                    <div style={{ fontSize: 11, color: 'var(--text-dim)', marginBottom: 2 }}>{label}</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ flex: 1, height: 10, background: 'var(--border)', borderRadius: 5, overflow: 'hidden' }}>
                        <div style={{ width: `${Math.round(auc * 100)}%`, height: '100%', background: cls, borderRadius: 5 }} />
                      </div>
                      <span style={{ fontSize: 12, fontWeight: 700, color: cls, minWidth: 50, textAlign: 'right' }}>{auc.toFixed(4)}</span>
                    </div>
                  </div>
                ))}
              </div>
              <div className="dim" style={{ fontSize: 11, marginTop: 10 }}>
                ★ selected model · fingerprinting reduced but not eliminated
              </div>
              <div className="warning-box warn" style={{ marginTop: 12, marginBottom: 0 }}>
                <span className="icon">⚠</span>
                <span style={{ fontSize: 12 }}>ECE ≈ 0.30 — raw probability scores are not well-calibrated. Use thresholds, not raw scores.</span>
              </div>
            </div>
          </div>
          <div className="dashboard-status-grid">
            <SummaryCard
              compact
              label="API Status"
              value={health?.status === 'ok' ? 'Online' : 'Unknown'}
              sub={health?.service}
              accent={health?.status === 'ok' ? 'ok' : 'bad'}
            />
            <SummaryCard
              compact
              label="Default Model"
              value={defaultModel?.model_id || 'unified_relative_shape_v2__lgbm'}
              sub={defaultModel?.model_id === 'unified_relative_shape_v2__lgbm' ? 'Unified feature contract v2 prototype' : (defaultModel?.status || 'Unified feature contract v2 prototype')}
              accent="info"
            />
            <SummaryCard
              compact
              label="Feature Family"
              value="unified_relative_shape_v2"
              sub="12 ratio/relative features"
              accent="info"
            />
            <SummaryCard
              compact
              label="Action Mode"
              value={defaultModel?.recommended_action_mode || 'simulation'}
              sub="Simulation only"
              accent="warn"
            />
            <SummaryCard
              compact
              label="Runtime Compatible"
              value="true"
              sub="12-feature unified LightGBM"
              accent="ok"
            />
            <SummaryCard
              compact
              label="Production Ready"
              value="false"
              sub="Prototype — do not deploy"
              accent="bad"
            />
          </div>

          <div className="section grid cols-2">
            <div className="card">
              <h2>Default model policy</h2>
              <div className="kv">
                <div className="k">model_id</div>
                <div className="v mono">{defaultModel?.model_id || 'unified_relative_shape_v2__lgbm'}</div>

                <div className="k">status</div>
                <div className="v">
                  <StatusBadge status={defaultModel?.status} />
                </div>

                <div className="k">feature_family</div>
                <div className="v mono">unified_relative_shape_v2</div>

                <div className="k">selected_probability_column</div>
                <div className="v mono">{defaultModel?.selected_probability_column}</div>

                <div className="k">selected_aggregation</div>
                <div className="v mono">{defaultModel?.selected_aggregation}</div>

                <div className="k">recommended_action_mode</div>
                <div className="v mono">{defaultModel?.recommended_action_mode || 'simulation'}</div>

                <div className="k">production_readiness</div>
                <div className="v">
                  <StatusBadge tone="bad" label="false" />
                </div>
              </div>
              <div className="warning-box info" style={{ marginTop: 12, marginBottom: 0 }}>
                <span className="icon">ℹ</span>
                <div>
                  Selected as the best methodologically clean model under <span className="mono">unified_feature_contract_v2</span>.
                  It uses 12 ratio/relative features and improved LODO-min AUC compared with the legacy model.
                  <ul className="clean" style={{ marginTop: 6, fontSize: 12 }}>
                    <li>ECE is high — treat probabilities cautiously.</li>
                    <li>FPR is higher than the legacy model.</li>
                    <li>Live PCAP validation is required before production claims.</li>
                    <li>Prototype remains simulation-only.</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="card">
              <h2>Model performance metrics</h2>
              <div className="kv">
                <div className="k">model</div>
                <div className="v mono">unified_relative_shape_v2__lgbm</div>

                <div className="k">test_auc</div>
                <div className="v">{num(defaultModel?.pooled_auc) !== '—' ? num(defaultModel?.pooled_auc) : '0.9826'}</div>

                <div className="k">lodo_min_auc</div>
                <div className="v">{num(defaultModel?.lodo_min_auc) !== '—' ? num(defaultModel?.lodo_min_auc) : '0.6366'}</div>

                <div className="k">domain_auc</div>
                <div className="v">{num(defaultModel?.domain_auc) !== '—' ? num(defaultModel?.domain_auc) : '0.9591'}</div>

                <div className="k">deployment_score</div>
                <div className="v">{num(defaultModel?.deployment_score) !== '—' ? num(defaultModel?.deployment_score) : '0.4691'}</div>

                <div className="k">ece</div>
                <div className="v">{num(defaultModel?.ece) !== '—' ? num(defaultModel?.ece) : '0.2988'}</div>

                <div className="k">recall</div>
                <div className="v">{num(defaultModel?.recall) !== '—' ? num(defaultModel?.recall) : '0.8930'}</div>

                <div className="k">fpr</div>
                <div className="v">{num(defaultModel?.['fpr_at_0.5']) !== '—' ? num(defaultModel?.['fpr_at_0.5']) : '0.0759'}</div>

                <div className="k">updated_utc</div>
                <div className="v mono" style={{ fontSize: 11 }}>
                  {defaultModel?.updated_utc || '—'}
                </div>
              </div>
              <div className="dim" style={{ fontSize: 12, marginTop: 10 }}>
                Domain fingerprinting was reduced compared with the legacy model, but not eliminated.
              </div>
            </div>
          </div>

          <WarningBox tone="info">
            Metrics shown are from a held-out test set during model packaging.
            Performance on a new network or under domain drift is not guaranteed —
            see the Robustness page.{' '}
            <strong>Domain fingerprinting was reduced compared with the legacy model
            (<span className="mono">domain_auc = 0.9591</span> vs 1.0), but not eliminated.
            This prototype is still not production-ready.</strong>
          </WarningBox>
        </>
      )}
    </div>
  );
}
