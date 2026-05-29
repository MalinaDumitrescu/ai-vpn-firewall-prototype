import React from 'react';
import LiveVMReplay from './LiveVMReplay.jsx';
import LiveVMMonitor from './LiveVMMonitor.jsx';
import TabSwitcher from '../components/TabSwitcher.jsx';

/**
 * Live VM — unified page hosting two sub-views:
 *   - CSV Replay   (step-by-step replay + bundled full-canonical demo)
 *   - PCAP Monitor (live ingest + local demo scripts)
 *
 * `tab` and `onTabChange` are controlled from App.jsx so legacy routes
 * (demorunner → monitor, firewall → replay) land on the right tab.
 */
export default function LiveVM({ tab = 'replay', onTabChange }) {
  const tabs = [
    { id: 'replay',  label: 'CSV Replay'   },
    { id: 'monitor', label: 'PCAP Monitor' },
  ];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Live VM</h1>
          <div className="subtitle">
            Replay exported CSV flow features through{' '}
            <span className="mono">full_canonical__lgbm</span>{' '}
            (34-feature LightGBM), or monitor PCAP-derived batches from the
            local ingest script. Simulation only &mdash; no packets are blocked.
          </div>
        </div>
      </div>

      <TabSwitcher tabs={tabs} active={tab} onChange={onTabChange} />

      <div className="tab-panel">
        {tab === 'replay'  && <LiveVMReplay />}
        {tab === 'monitor' && <LiveVMMonitor />}
      </div>
    </div>
  );
}
