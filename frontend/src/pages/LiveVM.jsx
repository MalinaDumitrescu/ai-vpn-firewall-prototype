import React, { useState } from 'react';
import LiveVMReplay from './LiveVMReplay.jsx';
import LiveVMMonitor from './LiveVMMonitor.jsx';
import TabSwitcher from '../components/TabSwitcher.jsx';

/**
 * Live VM — unified page that hosts two complementary sub-views:
 *   - CSV Replay   (the previous Live VM Replay page)
 *   - PCAP Monitor (the previous Live VM Monitor page)
 *
 * The original pages are re-used as-is; only the parent navigation changes.
 */
export default function LiveVM() {
  const [tab, setTab] = useState('replay');

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
            Replay exported CSV flow features or monitor PCAP-derived batches
            from the local ingest script. Simulation only &mdash; no packets
            are blocked.
          </div>
        </div>
      </div>

      <TabSwitcher tabs={tabs} active={tab} onChange={setTab} />

      <div className="tab-panel">
        {tab === 'replay'  && <LiveVMReplay />}
        {tab === 'monitor' && <LiveVMMonitor />}
      </div>
    </div>
  );
}

