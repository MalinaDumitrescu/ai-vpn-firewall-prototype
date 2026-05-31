import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import WarningBox from '../components/WarningBox.jsx';
import ModelCard from '../components/ModelCard.jsx';

// Domain fingerprinting progression — matches frontend_page_content.json
const DOMAIN_FP_PROGRESSION = [
  { label: 'Legacy full_canonical__lgbm',        auc: 1.0,    cls: '' },
  { label: 'Phase 1 (all unified features)',      auc: 0.9903, cls: '' },
  { label: 'Best unified (relative_shape_v2) ★',  auc: 0.9591, cls: '--improved' },
  { label: 'Best low-FP (size_shape)',            auc: 0.9479, cls: '--best' },
];

const LODO_ROWS = [
  { dataset: 'LODO-ISCX',  auc: 0.6366, note: 'Hardest held-out set. Near-random on unseen ISCX.' },
  { dataset: 'LODO-VNAT',  auc: 0.9560, note: 'Good transfer from ISCX+USBVPN training.' },
  { dataset: 'LODO mean',  auc: 0.7963, note: 'Average across computable LODO splits.' },
  { dataset: 'LODO min',   auc: 0.6366, note: 'Worst-case held-out domain.' },
];

function DomainBar({ label, auc, cls }) {
  return (
    <div className="domain-bar-row">
      <div className="domain-bar-label">{label}</div>
      <div className="domain-bar-track">
        <div className={`domain-bar-fill${cls}`} style={{ width: `${Math.round(auc * 100)}%` }} />
      </div>
      <div className="domain-bar-value">{auc.toFixed(4)}</div>
    </div>
  );
}

export default function Robustness() {
  const [controls, setControls]       = useState(null);
  const [pageContent, setPageContent] = useState(null);
  const [error, setError]             = useState(null);
  const [loading, setLoading]         = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [c, pc] = await Promise.all([
          api.robustnessControls(),
          api.modelDetailsFrontendContent().catch(() => null),
        ]);
        setControls(c);
        setPageContent(pc);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const robPage    = pageContent?.pages?.RobustnessPage;
  const checklist  = robPage?.deployment_checklist   ?? [];
  const notSolved  = robPage?.what_is_not_solved     ?? [];
  const fpStory    = robPage?.domain_fingerprinting_story ?? [];
  const lodoInterp = robPage?.lodo_negative_control_interpretation;
  const liveCaveat = robPage?.live_validation_caveat;
  const outcome    = robPage?.final_research_outcome;
  const negatives  = controls ? controls.map((e) => [e.model_id, e]) : [];

  const DEFAULT_NOT_SOLVED = [
    'Domain fingerprinting: domain AUC = 0.9591 — still above 0.5 (random).',
    'LODO-ISCX = 0.637: cross-domain transfer to ISCX-style traffic is limited.',
    'ECE = 0.299: probability calibration is poor. Raw scores unreliable as probabilities.',
    'Live traffic validation: schema confirmed only. End-to-end live test pending.',
    'GroupDRO / DANN: alternative training strategies not fully explored.',
  ];

  const DEFAULT_CHECKLIST = [
    ['Unified feature contract defined', 'DONE'],
    ['Cross-dataset formula mismatches fixed', 'DONE'],
    ['30 models trained and evaluated', 'DONE'],
    ['LODO evaluation completed', 'DONE'],
    ['Domain fingerprinting measured', 'DONE'],
    ['Anti-fingerprint feature selection', 'DONE'],
    ['Runtime export candidate created', 'DONE'],
    ['Demo CSV created and validated', 'DONE'],
    ['Smoke test passed', 'DONE'],
    ['Live PCAP validation on VM', 'PENDING'],
    ['Production-ready threshold tuning', 'PENDING'],
    ['App runtime bundle replacement', 'PENDING — awaiting live validation'],
  ];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Robustness &amp; deployment posture</h1>
          <div className="subtitle">
            What this prototype is — and what it is not.
            Domain fingerprinting, LODO transfer, deployment checklist.
          </div>
        </div>
      </div>

      <WarningBox tone="bad">
        <strong>Unseen-domain robustness is not solved.</strong>{' '}
        LODO-ISCX AUC = 0.637 — the model collapses to near-random on completely unseen ISCX-style captures.
        Treat the prototype as a <em>known-domain simulation model only</em>.
      </WarningBox>

      <WarningBox tone="info">
        The active runtime model is <span className="mono">unified_relative_shape_v2__lgbm</span> — unified feature contract v2, simulation-only.{' '}
        <span className="mono">full_canonical__lgbm</span> is the
        <strong>legacy mixed-feature baseline (domain AUC = 1.0)</strong> — NOT the recommended model.
      </WarningBox>

      {/* Final research outcome */}
      <div className="section">
        <div className="card">
          <h2>Final research outcome</h2>
          <p style={{ lineHeight: 1.7, marginTop: 8, marginBottom: 8, fontWeight: 600 }}>
            {outcome?.headline ?? 'Unified feature contract reduced dataset fingerprinting but did not eliminate it.'}
          </p>
          <p style={{ lineHeight: 1.7, margin: 0, color: 'var(--text-dim)', fontSize: 13 }}>
            {outcome?.detail ??
              'After fixing cross-dataset formula mismatches and selecting ratio/relative features, domain AUC dropped from 1.0000 (legacy) to 0.9591 (unified_relative_shape_v2__lgbm). A meaningful improvement, but the classifier can still identify the source dataset above chance. The prototype remains simulation-only.'}
          </p>
        </div>
      </div>

      {/* Domain fingerprinting + LODO */}
      <div className="section grid cols-2">
        <div className="card">
          <h2>Domain fingerprinting — progression</h2>
          <p style={{ fontSize: 12, color: 'var(--text-dim)', margin: '6px 0 10px' }}>
            Domain AUC = ability of a classifier to identify the source dataset from features.
            1.0 = perfect fingerprinting (bad). 0.5 = random (ideal).
          </p>
          {DOMAIN_FP_PROGRESSION.map((r) => <DomainBar key={r.label} {...r} />)}
          <div className="dim" style={{ fontSize: 11, marginTop: 8 }}>
            bar: red = high FP · orange = improved · green = best available · ★ = selected model
          </div>
          {fpStory.length > 0 && (
            <ul className="clean" style={{ fontSize: 12, marginTop: 10, paddingLeft: 0 }}>
              {fpStory.map((s, i) => (
                <li key={i} style={{ padding: '2px 0', color: 'var(--text-dim)', display: 'flex', gap: 6 }}>
                  <span style={{ flexShrink: 0 }}>→</span>{s}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card">
          <h2>LODO transfer summary</h2>
          <p style={{ fontSize: 12, color: 'var(--text-dim)', margin: '6px 0 10px' }}>
            Leave-one-dataset-out AUC for <span className="mono">unified_relative_shape_v2__lgbm</span>.
            Below 0.7 = weak cross-domain transfer.
          </p>
          <table className="feature-table">
            <thead>
              <tr><th>Split</th><th>AUC</th><th>Notes</th></tr>
            </thead>
            <tbody>
              {LODO_ROWS.map((r) => (
                <tr key={r.dataset}>
                  <td className="mono" style={{ fontSize: 12 }}>{r.dataset}</td>
                  <td style={{ fontWeight: 700, color: r.auc < 0.7 ? 'var(--warn)' : 'var(--ok)' }}>
                    {r.auc.toFixed(4)}
                  </td>
                  <td style={{ fontSize: 12, color: 'var(--text-dim)' }}>{r.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {lodoInterp?.interpretation && (
            <p style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 10, lineHeight: 1.6 }}>
              {lodoInterp.interpretation}
            </p>
          )}
        </div>
      </div>

      {/* What is not solved + live PCAP */}
      <div className="section grid cols-2">
        <div className="card">
          <h2>What is not solved</h2>
          <ul className="clean" style={{ margin: 0, paddingLeft: 0 }}>
            {(notSolved.length > 0 ? notSolved : DEFAULT_NOT_SOLVED).map((item, i) => (
              <li key={i} style={{ padding: '5px 0', borderBottom: '1px solid var(--border)', fontSize: 13, display: 'flex', gap: 8 }}>
                <span style={{ color: 'var(--bad)', flexShrink: 0 }}>✗</span>
                <span style={{ color: 'var(--text-dim)' }}>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="card">
          <h2>Live PCAP validation status</h2>
          <div className="warning-box warn" style={{ marginBottom: 12 }}>
            <span className="icon">⚠</span>
            <div style={{ fontSize: 13 }}><strong>Schema confirmed — live end-to-end test pending.</strong></div>
          </div>
          <p style={{ fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.6, marginTop: 0 }}>
            {liveCaveat ?? 'Live PCAP validation is schema-confirmed only. The unified extractor has been verified to produce the correct 12 features from raw packet arrays. No end-to-end test with real live traffic has been run. Live validation required before any production deployment.'}
          </p>
          <div className="kv" style={{ marginTop: 12 }}>
            <div className="k">PCAP status</div>
            <div className="v"><span className="badge warn">PENDING</span></div>
            <div className="k">Schema</div>
            <div className="v"><span className="badge ok">CONFIRMED</span></div>
            <div className="k">action_mode</div>
            <div className="v mono">simulation</div>
            <div className="k">production_ready</div>
            <div className="v"><span className="badge bad">false</span></div>
          </div>
        </div>
      </div>

      {/* Deployment checklist */}
      <div className="section">
        <div className="card">
          <h2>Deployment checklist</h2>
          <ul className="deploy-checklist">
            {(checklist.length > 0
              ? checklist.map((item) => [item.item, item.status])
              : DEFAULT_CHECKLIST
            ).map(([item, status], i) => {
              const done = status === 'DONE';
              return (
                <li key={i}>
                  <span className={done ? 'check-done' : 'check-pending'}>{done ? '✓' : '○'}</span>
                  <span style={{ flex: 1 }}>{item}</span>
                  <span className={`badge ${done ? 'ok' : 'warn'}`} style={{ fontSize: 10 }}>{status}</span>
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      {/* LODO negative controls */}
      <div className="section">
        <div className="page-header" style={{ marginBottom: 10 }}>
          <h1 style={{ fontSize: 16 }}>Negative controls (LODO stress tests)</h1>
          <div className="subtitle">
            Trained without one dataset and evaluated on it — they document the failure mode, not fix it.
            <strong> Not deployable.</strong>
          </div>
        </div>

        {loading && <div className="loading-line"><span className="spinner" />Loading negative controls…</div>}
        {error && <div className="error-box">{error}</div>}
        {!loading && !error && (
          negatives.length === 0
            ? <div className="muted">No negative controls in registry.</div>
            : (
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
