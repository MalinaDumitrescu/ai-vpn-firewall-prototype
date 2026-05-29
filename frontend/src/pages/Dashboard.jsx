import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import SummaryCard from '../components/SummaryCard.jsx';
import WarningBox from '../components/WarningBox.jsx';
import StatusBadge from '../components/StatusBadge.jsx';

function num(v, d = 4) {
  if (v === null || v === undefined) return '—';
  if (typeof v !== 'number') return String(v);
  if (Number.isInteger(v)) return v.toString();
  return v.toFixed(d);
}

export default function Dashboard() {
  const [health, setHealth] = useState(null);
  const [defaultModel, setDefaultModel] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [h, m] = await Promise.all([api.health(), api.defaultModel()]);
        if (cancelled) return;
        setHealth(h);
        setDefaultModel(m);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Operations dashboard</h1>
          <div className="subtitle">
            Live status of the prototype API and the default firewall model.
          </div>
        </div>
      </div>

      <WarningBox tone="warn">
        <strong>Simulation only — no packets are blocked.</strong>{' '}
        <span className="mono">full_canonical__lgbm</span> is the selected known-domain prototype.
        Dataset fingerprinting remains unresolved (<span className="mono">domain_auc = 1.0</span>).
      </WarningBox>

      {loading && <div className="loading-line"><span className="spinner" />Loading status…</div>}
      {error && <div className="error-box">Failed to reach API: {error}</div>}

      {!loading && !error && (
        <>
          <div className="section grid cols-5">
            <SummaryCard
              label="API status"
              value={health?.status === 'ok' ? 'Online' : 'Unknown'}
              sub={health?.service}
              accent={health?.status === 'ok' ? 'ok' : 'bad'}
            />
            <SummaryCard
              label="Default model"
              value={defaultModel?.model_id || 'full_canonical__lgbm'}
              sub={defaultModel?.model_id === 'full_canonical__lgbm' ? 'Final recommended prototype' : (defaultModel?.status || 'Final recommended prototype')}
              accent="info"
            />
            <SummaryCard
              label="Action mode"
              value={defaultModel?.recommended_action_mode || 'simulation'}
              sub="Simulation only"
              accent="warn"
            />
            <SummaryCard
              label="Runtime compatible"
              value={'true'}
              sub="34-feature LightGBM"
              accent="ok"
            />
            <SummaryCard
              label="Production ready"
              value={'false'}
              sub="Prototype — do not deploy"
              accent="bad"
            />
          </div>

          <div className="section grid cols-2">
            <div className="card">
              <h2>Default model policy</h2>
              <div className="kv">
                <div className="k">model_id</div>
                <div className="v mono">{defaultModel?.model_id}</div>

                <div className="k">status</div>
                <div className="v">
                  <StatusBadge status={defaultModel?.status} />
                </div>

                <div className="k">selected_probability_column</div>
                <div className="v mono">{defaultModel?.selected_probability_column}</div>

                <div className="k">selected_aggregation</div>
                <div className="v mono">{defaultModel?.selected_aggregation}</div>

                <div className="k">recommended_action_mode</div>
                <div className="v mono">{defaultModel?.recommended_action_mode}</div>

                <div className="k">production_readiness</div>
                <div className="v">
                  <StatusBadge tone="bad" label="false" />
                </div>
              </div>
            </div>

            <div className="card">
              <h2>Model performance metrics</h2>
              <div className="kv">
                <div className="k">policy</div>
                <div className="v mono">{defaultModel?.policy || '—'}</div>

                <div className="k">pooled_auc</div>
                <div className="v">{num(defaultModel?.pooled_auc)}</div>

                <div className="k">lodo_min_auc</div>
                <div className="v">{num(defaultModel?.lodo_min_auc)}</div>

                <div className="k">lodo_mean_auc</div>
                <div className="v">{num(defaultModel?.lodo_mean_auc)}</div>

                <div className="k">fpr_at_0.5</div>
                <div className="v">{num(defaultModel?.['fpr_at_0.5'])}</div>

                <div className="k">ece</div>
                <div className="v">{num(defaultModel?.ece)}</div>

                <div className="k">review_threshold</div>
                <div className="v">{num(defaultModel?.review_threshold, 6)}</div>

                <div className="k">block_threshold</div>
                <div className="v">{num(defaultModel?.block_threshold, 6)}</div>

                <div className="k">updated_utc</div>
                <div className="v mono" style={{ fontSize: 11 }}>
                  {defaultModel?.updated_utc || '—'}
                </div>
              </div>
            </div>
          </div>

          <WarningBox tone="info">
            Metrics shown are from a held-out test set during model packaging.
            Performance on a new network or under domain drift is not guaranteed —
            see the Robustness page. <strong>Dataset-origin predictability remains
            perfect (<span className="mono">domain_auc = 1.0</span>); this prototype is known-domain only.</strong>
          </WarningBox>
        </>
      )}
    </div>
  );
}
