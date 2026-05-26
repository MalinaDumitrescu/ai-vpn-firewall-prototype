import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import WarningBox from '../components/WarningBox.jsx';
import ModelCard from '../components/ModelCard.jsx';

export default function Robustness() {
  const [controls, setControls] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const c = await api.robustnessControls();
        setControls(c);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const negatives = controls
    ? controls.map((entry) => [entry.model_id, entry])
    : [];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Robustness &amp; deployment posture</h1>
          <div className="subtitle">
            What this prototype is — and what it is not.
          </div>
        </div>
      </div>

      <WarningBox tone="bad">
        <strong>Unseen-domain robustness is not solved.</strong> The LODO
        (leave-one-dataset-out) negative controls collapse on their held-out
        datasets. Treat the default model as a <em>known-domain</em> prototype only.
      </WarningBox>

      <div className="section grid cols-2">
        <div className="card">
          <h2>Honest scope of this prototype</h2>
          <ul className="clean">
            <li>The default model works only as a <strong>known-domain</strong> prototype.</li>
            <li>LODO models are <strong>negative controls</strong>, not deployable.</li>
            <li><strong>Unseen-domain robustness is not solved.</strong></li>
            <li>
              Deployment in a new network requires <strong>local validation,
              recalibration, and drift monitoring</strong>.
            </li>
          </ul>
        </div>

        <div className="card">
          <h2>Recommended next steps before deployment</h2>
          <ul className="clean">
            <li>Collect labelled traffic from the target network.</li>
            <li>Re-run validation and recompute strict/balanced thresholds on local data.</li>
            <li>Refit isotonic calibration on local scores.</li>
            <li>Stand up drift monitoring on the 9 input features and on score distributions.</li>
            <li>Keep <span className="mono">action_mode = simulation</span> until reviewers approve live mode.</li>
          </ul>
        </div>
      </div>

      <div className="section">
        <div className="page-header" style={{ marginBottom: 10 }}>
          <h1 style={{ fontSize: 16 }}>Negative controls (LODO stress tests)</h1>
          <div className="subtitle">
            These are negative controls for unseen-domain robustness and are
            <strong> not deployable</strong>. Each is trained without one
            dataset and evaluated on it — they document the failure mode, they
            do not fix it.
          </div>
        </div>

        {loading && <div className="loading-line"><span className="spinner" />Loading negative controls…</div>}
        {error && <div className="error-box">{error}</div>}
        {!loading && !error && (
          negatives.length === 0 ? (
            <div className="muted">No negative controls in registry.</div>
          ) : (
            <div className="grid cols-2">
              {negatives.map(([id, entry]) => (
                <ModelCard key={id} modelId={id} entry={entry} />
              ))}
            </div>
          )
        )}
      </div>
    </div>
  );
}


