import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../api.js';
import ModelCard from '../components/ModelCard.jsx';
import WarningBox from '../components/WarningBox.jsx';

const GROUP_META = {
  main_demo_comparison: {
    title: 'Main demo & comparison',
    subtitle:
      'unified_relative_shape_v2__lgbm — CURRENT MODEL · EXECUTABLE · UNIFIED FEATURE CONTRACT V2 / simulation-only / not production-ready. ' +
      'full_canonical__lgbm — LEGACY MIXED-FEATURE BASELINE / comparison-only. ' +
      'robust9_firewall — LEGACY ROBUST9 BASELINE / comparison-only. ' +
      'timing_shape__lgbm — DIAGNOSTIC / old experiment / comparison-only. ' +
      'balanced_bagging_* — BENCHMARK COMPARISON / comparison-only. ' +
      'robust13_comparison — COMPARISON ONLY / not benchmark-selectable (requires session-derived features).',
    tone: 'info',
  },
  research_only: {
    title: 'Research-only (DANN v2)',
    subtitle:
      'RESEARCH ONLY. Adversarial domain-adaptation research candidates. DANN v2 did not meaningfully reduce ' +
      'embedding-domain fingerprinting (domain_reduction ≈ 0.0003) and was not selected for deployment. ' +
      'Not runtime-compatible. Not benchmark-selectable.',
    tone: 'warn',
  },
  advanced_unsafe_benchmark: {
    title: 'Advanced unsafe benchmarks',
    subtitle:
      'COMPARISON ONLY. Reference benchmarks with nonzero strict FPR. Never used for firewall actions. ' +
      'Not benchmark-selectable.',
    tone: 'warn',
  },
  robustness_negative_control: {
    title: 'Robustness negative controls (LODO)',
    subtitle:
      'NEGATIVE CONTROL. Leave-one-dataset-out stress tests — they demonstrate the unseen-domain failure mode and ' +
      'are NOT deployable. Not benchmark-selectable. Report-only.',
    tone: 'bad',
  },
  hidden_alias_or_unsupported: {
    title: 'Hidden: aliases & unsupported',
    subtitle:
      'UNSUPPORTED / ALIAS / DOCUMENTATION-ONLY. Aliases of other models and documentation-only stubs. ' +
      'Not benchmark-selectable. Hidden from normal users — shown here only for registry auditing.',
    tone: 'neutral',
  },
  _ungrouped: {
    title: 'Ungrouped',
    subtitle: 'Registry entries that do not declare a ui_group.',
    tone: 'neutral',
  },
};

const GROUP_ORDER = [
  'main_demo_comparison',
  'research_only',
  'advanced_unsafe_benchmark',
  'robustness_negative_control',
  'hidden_alias_or_unsupported',
  '_ungrouped',
];

export default function ModelRegistry() {
  const [models, setModels] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const m = await api.models();
        setModels(m);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const grouped = useMemo(() => {
    if (!models) return {};
    const buckets = {};
    Object.entries(models).forEach(([id, entry]) => {
      const g = entry.ui_group || '_ungrouped';
      if (!buckets[g]) buckets[g] = [];
      buckets[g].push([id, entry]);
    });
    Object.values(buckets).forEach((arr) =>
      arr.sort(
        ([ida, a], [idb, b]) =>
          (a.ui_sort_order ?? 9999) - (b.ui_sort_order ?? 9999) ||
          ida.localeCompare(idb),
      ),
    );
    return buckets;
  }, [models]);

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Model registry (admin view)</h1>
          <div className="subtitle">
            Packaged model <strong>metadata</strong> from the runtime bundle:
            identity, artifact path, role, probability column, aggregation,
            deployment approval, and notes. For benchmark metrics
            (session AUC, strict/balanced recall &amp; FPR), see the{' '}
            <strong>Comparison</strong> tab.
          </div>
        </div>
      </div>

      <WarningBox tone="info">
        <strong>Permission summary:</strong>{' '}
        <span className="mono">unified_relative_shape_v2__lgbm</span> — <strong>CURRENT MODEL · EXECUTABLE · UNIFIED FEATURE CONTRACT V2</strong> / simulation-only / not production-ready.{' '}
        <span className="mono">full_canonical__lgbm</span> — <strong>LEGACY MIXED-FEATURE BASELINE</strong> / comparison-only — not the recommended model.{' '}
        <span className="mono">robust9_firewall</span>, <span className="mono">balanced_bagging_3ds_reference</span>,{' '}
        <span className="mono">balanced_bagging_baseline</span> — <strong>LEGACY / BENCHMARK COMPARISON ONLY</strong> / not executable.{' '}
        All other models — <strong>NOT SELECTABLE</strong> in benchmark / comparison-only / research-only / negative-control / unsupported.
        Only <span className="mono">unified_relative_shape_v2__lgbm</span> runs firewall inference.
      </WarningBox>

      {loading && <div className="loading-line"><span className="spinner" />Loading registry…</div>}
      {error && <div className="error-box">Failed to load registry: {error}</div>}

      {!loading && !error && GROUP_ORDER.map((g) => {
        const entries = grouped[g];
        if (!entries || entries.length === 0) return null;
        const meta = GROUP_META[g] || GROUP_META._ungrouped;
        return (
          <div key={g} className="section">
            <div className="page-header" style={{ marginBottom: 10 }}>
              <h1 style={{ fontSize: 16 }}>
                {meta.title}{' '}
                <span className="dim" style={{ fontWeight: 400, fontSize: 12 }}>
                  ({entries.length})
                </span>
              </h1>
              <div className="subtitle">{meta.subtitle}</div>
            </div>
            <div className="grid cols-2">
              {entries.map(([modelId, entry]) => (
                <ModelCard key={modelId} modelId={modelId} entry={entry} variant="metadata" />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}