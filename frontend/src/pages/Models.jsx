import React, { useState } from 'react';
import ModelRegistry from './ModelRegistry.jsx';
import ModelComparison from './ModelComparison.jsx';
import TabSwitcher from '../components/TabSwitcher.jsx';

/**
 * Models — unified entry point for the model-related pages:
 *   - Registry   (metadata: model id, role, artifact, probability column,
 *                 aggregation, deployment approval, notes)
 *   - Comparison (metrics: session AUC, strict/balanced recall+FPR, warnings)
 */
export default function Models() {
  const [tab, setTab] = useState('registry');

  const tabs = [
    { id: 'registry',   label: 'Registry'   },
    { id: 'comparison', label: 'Comparison' },
  ];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Models</h1>
          <div className="subtitle">
            Registry shows packaged model metadata and deployment approval.
            Comparison shows benchmarking metrics on the same evaluation
            CSV. Both views are read-only.
          </div>
        </div>
      </div>

      <TabSwitcher tabs={tabs} active={tab} onChange={setTab} />

      <div className="tab-panel">
        {tab === 'registry'   && <ModelRegistry />}
        {tab === 'comparison' && <ModelComparison />}
      </div>
    </div>
  );
}

