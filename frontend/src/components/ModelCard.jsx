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
  const isDefault    = status === 'default_firewall' || status === 'recommended_firewall' || status === 'deployment_eligible';
  const isLegacy     = status === 'legacy_baseline';
  const isNegative   = status === 'negative_control';
  const isUnsupp     = status === 'unsupported';
  const isAlias      = status === 'alias';
  const isPolicyOnly = status === 'policy_computed' || status === 'benchmark_comparison';
  const isResearch   = status === 'research_only';

  // Benchmark-compat fields (may come from enriched registry or permissions endpoint)
  const isBenchCompat = entry?.benchmark_compatible === true
    || ['robust9_firewall', 'balanced_bagging_3ds_reference', 'balanced_bagging_baseline', 'full_canonical__lgbm'].includes(modelId);
  const isExecutable  = entry?.executable === true || modelId === 'full_canonical__lgbm';

  const isMetadata = variant === 'metadata';

  const approvalLabel =
    isDefault     ? 'Approved (simulation only)' :
    isLegacy      ? 'Legacy baseline (simulation only) — not the recommended model' :
    isNegative    ? 'Negative control - not deployable' :
    isPolicyOnly  ? 'Benchmark / diagnostic only - not deployable' :
    isResearch    ? 'Research only — not selected for deployment' :
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
          {isExecutable && (
            <span className="badge ok small-badge" title="Executable firewall model">
              <span className="dot" />executable
            </span>
          )}
          {isBenchCompat && !isExecutable && (
            <span className="badge info small-badge" title="Benchmark-compatible">
              <span className="dot" />benchmark compat
            </span>
          )}
          {!isBenchCompat && (
            <span className="badge neutral small-badge" title="Not selectable in benchmark">
              <span className="dot" />not selectable
            </span>
          )}
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

            <div className="k">benchmark compat</div>
            <div className="v" style={{ color: isBenchCompat ? 'var(--ok)' : 'var(--text-dim)' }}>
              {isBenchCompat ? '✓ yes' : '✗ no'}
            </div>

            <div className="k">selectable</div>
            <div className="v" style={{ color: isBenchCompat ? 'var(--ok)' : 'var(--text-dim)' }}>
              {isBenchCompat ? '✓ in benchmark' : '✗ not selectable'}
            </div>

            {entry?.runtime_compatible !== undefined && (
              <>
                <div className="k">runtime compat.</div>
                <div className="v" style={{ color: entry.runtime_compatible ? 'var(--ok)' : 'var(--bad)' }}>
                  {entry.runtime_compatible ? '✓ yes' : '✗ no'}
                </div>
              </>
            )}
            {entry?.deployment_eligible !== undefined && (
              <>
                <div className="k">deploy eligible</div>
                <div className="v" style={{ color: entry.deployment_eligible ? 'var(--ok)' : 'var(--bad)' }}>
                  {entry.deployment_eligible ? '✓ yes' : '✗ no'}
                </div>
              </>
            )}
            {entry?.production_ready !== undefined && (
              <>
                <div className="k">production ready</div>
                <div className="v" style={{ color: 'var(--bad)' }}>
                  ✗ false
                </div>
              </>
            )}
          </>
        )}

        {!isMetadata && (
          <>
            {entry?.pooled_auc !== undefined && (
              <>
                <div className="k">pooled AUC</div>
                <div className="v">{fmt(entry.pooled_auc)}</div>
              </>
            )}
            {entry?.lodo_min_auc !== undefined && (
              <>
                <div className="k">LODO-min AUC</div>
                <div className="v">{fmt(entry.lodo_min_auc)}</div>
              </>
            )}
            {entry?.domain_auc !== undefined && (
              <>
                <div className="k">domain AUC</div>
                <div className="v" style={{ color: entry.domain_auc >= 0.999 ? 'var(--bad)' : 'inherit' }}>
                  {fmt(entry.domain_auc)}
                  {entry.domain_auc >= 0.999 && ' ⚠'}
                </div>
              </>
            )}

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

      {!isDefault && !isLegacy && !isResearch && (
        <div className="warning-box warn" style={{ marginBottom: 0 }}>
          <span className="icon">⚠</span>
          <div>Not deployment-approved.</div>
        </div>
      )}
      {isLegacy && (
        <div className="warning-box info" style={{ marginBottom: 0 }}>
          <span className="icon">ℹ</span>
          <div>Legacy baseline — kept for comparison. <strong>Not the recommended model.</strong></div>
        </div>
      )}
      {isResearch && (
        <div className="warning-box warn" style={{ marginBottom: 0 }}>
          <span className="icon">🔬</span>
          <div>Research only — not selected for firewall deployment. Did not reduce domain fingerprinting.</div>
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
