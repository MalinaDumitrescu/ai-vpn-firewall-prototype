import React, { useState } from 'react';
import ModelRegistry from './ModelRegistry.jsx';
import ModelCards from './ModelCards.jsx';
import ModelComparison from './ModelComparison.jsx';
import TabSwitcher from '../components/TabSwitcher.jsx';

/**
 * Models — unified entry point for the model-related pages:
 *   - Model Cards  (rich cards from model_cards_frontend.json: why selected, metrics, caveats, formulas)
 *   - Registry     (raw packaged metadata: model id, role, artifact, probability column, etc.)
 *   - Comparison   (legacy benchmark comparison page)
 */
export default function Models() {
  const [tab, setTab] = useState('cards');

  const tabs = [
    { id: 'cards',      label: 'Model Cards'  },
    { id: 'registry',   label: 'Registry'     },
    { id: 'comparison', label: 'Comparison'   },
  ];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Models</h1>
          <div className="subtitle">
            <span className="mono">unified_relative_shape_v2__lgbm</span> is the current recommended model
            (unified feature contract v2, executable, simulation-only).
            Model Cards shows rich descriptions with metrics, formulas, and caveats.
            Comparison shows legacy benchmark models for audit — active runtime inference is handled by <strong>Live VM</strong>.
          </div>
        </div>
      </div>

      <TabSwitcher tabs={tabs} active={tab} onChange={setTab} />

      <div className="tab-panel">
        {tab === 'cards'      && <ModelCards />}
        {tab === 'registry'   && <ModelRegistry />}
        {tab === 'comparison' && <ModelComparison />}
      </div>
    </div>
  );
}


