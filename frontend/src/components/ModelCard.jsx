import React from 'react';
import StatusBadge from './StatusBadge.jsx';

function fmt(v, digits = 4) {
  if (v === null || v === undefined || v === '') return '—';
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return v.toString();
    return v.toFixed(digits);
  }
  return String(v);
}

export default function ModelCard({ modelId, entry, variant = 'full' }) {
  const status = entry?.status || 'unknown';
  const isDefault    = status === 'default_firewall' || status === 'recommended_firewall';
  const isLegacy     = status === 'legacy_baseline';
  const isNegative   = status === 'negative_control';
  const isUnsupp     = status === 'unsupported';
  const isAlias      = status === 'alias';
  const isPolicyOnly = status === 'policy_computed';

  // metadata variant: Registry view focuses on identity / artifact / policy /
  // approval / notes and hides the benchmark metrics that already appear on
  // the Model Comparison page.
  const isMetadata = variant === 'metadata';

  const approvalLabel =
    isDefault     ? 'Approved (simulation only)' :
    isLegacy      ? 'Legacy baseline (simulation only)' :
    isNegative    ? 'Negative control - not deployable' :
    isPolicyOnly  ? 'Benchmark only - not deployable' :
    isUnsupp      ? 'Unsupported - not deployable' :
    isAlias       ? 'Alias - not deployable' :
                    'Not deployment-approved';

  return (
    <div className="card model-card">
      <div className="header">
        <div>
          <div className="title">{modelId}</div>
          <div className="dim" style={{ fontSize: 12, marginTop: 2 }}>
            {entry?.source_artifact || '\u2014'}
          </div>
        </div>
        <div className="badges">
          <StatusBadge status={status} />
          {entry?.recommended_action_mode && (
            <StatusBadge
              tone={entry.recommended_action_mode === 'simulation' ? 'info' : 'neutral'}
              label={entry.recommended_action_mode}
              title="recommended_action_mode"
            />
          )}
        </div>
      </div>

      <div className="metrics">
        <div className="k">prob col</div>
        <div className="v mono">{entry?.selected_probability_column ?? '\u2014'}</div>

        <div className="k">aggregation</div>
        <div className="v mono">{entry?.selected_aggregation ?? '\u2014'}</div>

        {isMetadata && (
          <>
            <div className="k">approval</div>
            <div className="v">{approvalLabel}</div>
          </>
        )}

        {!isMetadata && (
          <>
            <div className="k">strict recall</div>
            <div className="v">{fmt(entry?.strict_test_recall)}</div>

            <div className="k">strict FPR</div>
            <div className="v">{fmt(entry?.strict_test_fpr)}</div>

            <div className="k">balanced recall</div>
            <div className="v">{fmt(entry?.balanced_test_recall)}</div>

            <div className="k">balanced FPR</div>
            <div className="v">{fmt(entry?.balanced_test_fpr)}</div>

            <div className="k">session AUC</div>
            <div className="v">{fmt(entry?.session_auc_test)}</div>
          </>
        )}

        {entry?.held_out_dataset && (
          <>
            <div className="k">held-out</div>
            <div className="v mono">{entry.held_out_dataset}</div>
          </>
        )}
        {isAlias && entry?.alias_of && (
          <>
            <div className="k">alias of</div>
            <div className="v mono">{entry.alias_of}</div>
          </>
        )}
      </div>

      {!isDefault && !isLegacy && (
        <div className="warning-box warn" style={{ marginBottom: 0 }}>
          <span className="icon">⚠</span>
          <div>Not deployment-approved.</div>
        </div>
      )}
      {isLegacy && (
        <div className="warning-box info" style={{ marginBottom: 0 }}>
          <span className="icon">ℹ</span>
          <div>Legacy baseline — not the recommended model.</div>
        </div>
      )}
      {isNegative && (
        <div className="warning-box bad" style={{ marginBottom: 0 }}>
          <span className="icon">⛔</span>
          <div>LODO stress-test only.</div>
        </div>
      )}
      {isUnsupp && (
        <div className="warning-box info" style={{ marginBottom: 0 }}>
          <span className="icon">ℹ</span>
          <div>Unsupported / documentation-only.</div>
        </div>
      )}
      {isPolicyOnly && (
        <div className="warning-box info" style={{ marginBottom: 0 }}>
          <span className="icon">ℹ</span>
          <div>Comparison / benchmark only.</div>
        </div>
      )}

      {Array.isArray(entry?.warnings) && entry.warnings.length > 0 && (
        <div className="dim" style={{ fontSize: 12 }}>
          <strong style={{ color: 'var(--text-dim)' }}>Notes:</strong>
          <ul className="clean">
            {entry.warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
