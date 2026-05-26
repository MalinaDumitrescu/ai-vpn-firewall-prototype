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
        This prototype scores traffic and records suggested actions.
        It does not interact with the network data plane.
      </WarningBox>

      {loading && <div className="loading-line"><span className="spinner" />Loading status…</div>}
      {error && <div className="error-box">Failed to reach API: {error}</div>}

      {!loading && !error && (
        <>
          <div className="section grid cols-4">
            <SummaryCard
              label="API status"
              value={health?.status === 'ok' ? 'Online' : 'Unknown'}
              sub={health?.service}
              accent={health?.status === 'ok' ? 'ok' : 'bad'}
            />
            <SummaryCard
              label="Default model"
              value={defaultModel?.model_id || '—'}
              sub={defaultModel?.status}
              accent="info"
            />
            <SummaryCard
              label="Action mode"
              value={defaultModel?.recommended_action_mode || '—'}
              sub="Simulation only"
              accent="warn"
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
              <h2>Test-set policy metrics</h2>
              <div className="kv">
                <div className="k">strict_test_recall</div>
                <div className="v">{num(defaultModel?.strict_test_recall)}</div>

                <div className="k">strict_test_fpr</div>
                <div className="v">{num(defaultModel?.strict_test_fpr)}</div>

                <div className="k">balanced_test_recall</div>
                <div className="v">{num(defaultModel?.balanced_test_recall)}</div>

                <div className="k">balanced_test_fpr</div>
                <div className="v">{num(defaultModel?.balanced_test_fpr)}</div>

                <div className="k">session_auc_test</div>
                <div className="v">{num(defaultModel?.session_auc_test)}</div>

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
            see the Robustness page.
          </WarningBox>
        </>
      )}
    </div>
  );
}
