import React from 'react';
import DemoRunnerPanel from '../components/DemoRunnerPanel.jsx';
/**
 * Demo Runner (standalone page).
 *
 * Thin wrapper around <DemoRunnerPanel /> so the same UI is available both
 * as a dedicated page and as a card embedded on Live VM > PCAP Monitor.
 */
export default function DemoRunner({ onNavigate }) {
  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Demo runner</h1>
          <div className="subtitle">
            Start the local thesis demo scripts from the browser. Each button
            POSTs to a fixed backend allowlist &mdash; the browser never runs
            shell commands directly.
          </div>
        </div>
        <div className="button-row">
          {onNavigate && (
            <button className="secondary" onClick={() => onNavigate('livevm')}>
              Open Live VM &rarr;
            </button>
          )}
        </div>
      </div>
      <DemoRunnerPanel showJobs={true} />
    </div>
  );
}
