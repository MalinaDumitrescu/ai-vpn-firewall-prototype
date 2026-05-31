import React, { useState } from 'react';

/**
 * FeatureFormulaTable — expandable table showing feature formulas for a model.
 *
 * Props:
 *   modelId     — e.g. "unified_relative_shape_v2__lgbm"
 *   featuresObj — object from model_feature_details.json → models[modelId].features
 *   selectedOnly — if true, show only features where in_selected_model === true
 */

function featureTypeBadge(f) {
  if (f.is_timing_ratio_feature) return { label: 'timing ratio', cls: 'info' };
  if (f.is_size_ratio_feature)   return { label: 'size ratio',   cls: 'ok'   };
  if (f.is_directional_feature)  return { label: 'directional',  cls: 'warn' };
  if (f.is_timing_feature)       return { label: 'timing',       cls: 'info' };
  if (f.is_size_feature)         return { label: 'size',         cls: 'neutral' };
  return { label: 'other', cls: 'neutral' };
}

export default function FeatureFormulaTable({ featuresObj = {}, selectedOnly = false }) {
  const [open, setOpen] = useState(false);

  const entries = Object.entries(featuresObj).filter(
    ([, f]) => !selectedOnly || f.in_selected_model,
  );

  if (entries.length === 0) return null;

  return (
    <div style={{ marginTop: 12 }}>
      <button
        className="secondary"
        style={{ fontSize: 12, padding: '5px 12px' }}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? '▲ Hide' : '▼ Show'} features &amp; formulas ({entries.length})
      </button>

      {open && (
        <div style={{ marginTop: 10, overflowX: 'auto' }}>
          <table className="feature-table">
            <thead>
              <tr>
                <th>Feature</th>
                <th>Formula</th>
                <th>Type</th>
                <th>Live ✓</th>
                <th>⚠ FP concern</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(([name, f]) => {
                const { label, cls } = featureTypeBadge(f);
                return (
                  <tr key={name}>
                    <td>
                      <span className="mono" style={{ fontSize: 12 }}>{name}</span>
                      {f.top_anti_fingerprint_feature && (
                        <span title="Top anti-fingerprint feature" style={{ marginLeft: 5, color: 'var(--ok)', fontSize: 10 }}>★</span>
                      )}
                    </td>
                    <td>
                      <span className="formula-code">{f.formula}</span>
                    </td>
                    <td>
                      <span className={`badge ${cls}`} style={{ fontSize: 10 }}>{label}</span>
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      {f.live_extractor_compatible
                        ? <span style={{ color: 'var(--ok)' }}>✓</span>
                        : <span style={{ color: 'var(--bad)' }}>✗</span>}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      {f.previous_fingerprinting_concern
                        ? <span className="fp-warning" title="Previously had cross-dataset formula mismatch — now unified">⚠ unified</span>
                        : <span style={{ color: 'var(--text-mute)', fontSize: 11 }}>—</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {selectedOnly && (
            <div className="dim" style={{ fontSize: 11, marginTop: 6 }}>
              ★ = top anti-fingerprint feature · ⚠ unified = previously had cross-dataset formula mismatch, now fixed
            </div>
          )}
        </div>
      )}
    </div>
  );
}

