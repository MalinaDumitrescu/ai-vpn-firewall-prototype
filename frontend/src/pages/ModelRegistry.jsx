import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../api.js';
import ModelCard from '../components/ModelCard.jsx';
import WarningBox from '../components/WarningBox.jsx';

const GROUP_META = {
  main_demo_comparison: {
    title: 'Main demo comparison',
    subtitle:
      'The curated set used by the Model Comparison page. One default model plus five policy_computed baselines.',
    tone: 'info',
  },
  advanced_unsafe_benchmark: {
    title: 'Advanced unsafe benchmarks',
    subtitle:
      'Reference benchmarks with nonzero strict FPR. Visible to admins so reviewers can see what we rejected. Never used for firewall actions.',
    tone: 'warn',
  },
  robustness_negative_control: {
    title: 'Robustness negative controls (LODO)',
    subtitle:
      'Leave-one-dataset-out stress tests. They demonstrate the unseen-domain failure mode and are not deployable.',
    tone: 'bad',
  },
  hidden_alias_or_unsupported: {
    title: 'Hidden: aliases & unsupported',
    subtitle:
      'Aliases of other models and documentation-only stubs. Hidden from normal users; shown here only for registry auditing.',
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
            All packaged models from the runtime bundle, visually grouped by{' '}
            <span className="mono">ui_group</span>. Only the{' '}
            <strong>default_firewall</strong> model is approved for simulated
            firewall actions.
          </div>
        </div>
      </div>

      <WarningBox tone="info">
        <strong>One default model.</strong> Every other entry is comparison-only,
        a negative control, or unsupported — they are shown so reviewers can
        audit the registry, not so they can be deployed.
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
                <ModelCard key={modelId} modelId={modelId} entry={entry} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}