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

      <WarningBox tone="info">
        The executable prototype model is <span className="mono">full_canonical__lgbm</span>.
        Other models are shown only for comparison, negative-control, or research documentation.
        Unseen-domain robustness is not solved, and the prototype remains simulation-only.
      </WarningBox>

      <div className="section">
        <div className="card">
          <h2>Final research outcome</h2>
          <p style={{ lineHeight: 1.7, marginTop: 8, marginBottom: 0 }}>
            The final selected model is <span className="mono">full_canonical__lgbm</span>.
            It achieved the best deployment score among runtime-compatible and
            LODO-evaluated models. However, dataset-origin predictability remains
            perfect (<span className="mono">domain_auc = 1.0</span>), and DANN v2 did
            not meaningfully reduce embedding fingerprinting
            (<span className="mono">domain_reduction ≈ 0.0003</span>).
            Therefore, the prototype remains <strong>known-domain and simulation-only</strong>.
          </p>
        </div>
      </div>

      <div className="section grid cols-2">
        <div className="card">
          <h2>Honest scope of this prototype</h2>
          <ul className="clean">
            <li>
              <span className="mono">full_canonical__lgbm</span> is the final selected model —
              the <strong>best known-domain simulation prototype</strong>.
            </li>
            <li><span className="mono">robust9_firewall</span> is a <strong>legacy baseline</strong> kept for comparison only — not the recommended model.</li>
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
            <li>Stand up drift monitoring on the 34 input features and on score distributions.</li>
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


