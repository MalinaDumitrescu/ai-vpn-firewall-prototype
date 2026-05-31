import React, { useEffect, useState } from 'react';
import LiveVMReplay from './LiveVMReplay.jsx';
import LiveVMMonitor from './LiveVMMonitor.jsx';
import TabSwitcher from '../components/TabSwitcher.jsx';
import { api } from '../api.js';

/**
 * Live VM — unified page hosting two sub-views:
 *   - CSV Replay   (step-by-step replay + bundled full-canonical demo)
 *   - PCAP Monitor (live ingest + local demo scripts)
 *
 * `tab` and `onTabChange` are controlled from App.jsx so legacy routes
 * (demorunner → monitor, firewall → replay) land on the right tab.
 */
export default function LiveVM({ tab = 'replay', onTabChange }) {
  const [pageContent, setPageContent] = useState(null);

  useEffect(() => {
    api.modelDetailsFrontendContent().then(setPageContent).catch(() => null);
  }, []);

  const tabs = [
    { id: 'replay',  label: 'CSV Replay'   },
    { id: 'monitor', label: 'PCAP Monitor' },
  ];

  const liveVMPage = pageContent?.pages?.LiveVMPage;
  const schema     = liveVMPage?.expected_feature_schema;
  const pcapStatus = liveVMPage?.pcap_validation_status;
  const thresholds = liveVMPage?.thresholds;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Live VM</h1>
          <div className="subtitle">
            Live VM uses <span className="mono">unified_relative_shape_v2__lgbm</span> —
            the current unified feature contract v2 model (12 ratio/relative features, LightGBM).
            Replay CSVs compatible with the unified model, or monitor PCAP-derived batches using
            the unified feature contract v2 extractor. Simulation only &mdash; no packets are blocked.
          </div>
        </div>
      </div>

      {/* Extractor schema info panel */}
      {schema && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
            <h2 style={{ margin: 0, fontSize: 15 }}>Live extractor schema</h2>
            <span className="badge ok" style={{ fontSize: 11 }}>UNIFIED FEATURE CONTRACT V2</span>
            <span className="badge warn" style={{ fontSize: 11 }}>SIMULATION ONLY</span>
            {pcapStatus?.status && (
              <span className={`badge ${pcapStatus.status === 'PENDING' ? 'warn' : 'ok'}`} style={{ fontSize: 11 }}>
                PCAP {pcapStatus.status}
              </span>
            )}
          </div>
          <div className="kv" style={{ marginBottom: 10 }}>
            <div className="k">active_runtime_model</div>
            <div className="v mono">{liveVMPage?.active_runtime_model ?? 'unified_relative_shape_v2__lgbm'}</div>
            <div className="k">extractor_version</div>
            <div className="v mono">{schema.extractor_version}</div>
            <div className="k">feature_count</div>
            <div className="v mono">{schema.feature_count}</div>
            <div className="k">packet_size_convention</div>
            <div className="v mono">{schema.packet_size_convention}</div>
            <div className="k">iat_unit</div>
            <div className="v mono">{schema.iat_unit}</div>
            <div className="k">direction_convention</div>
            <div className="v mono">{schema.direction_convention}</div>
            <div className="k">min_packets</div>
            <div className="v mono">{schema.min_packets}</div>
            <div className="k">max_window_packets</div>
            <div className="v mono">{schema.max_window_packets}</div>
            {thresholds && <>
              <div className="k">threshold_review</div>
              <div className="v mono">{thresholds.review}</div>
              <div className="k">threshold_block</div>
              <div className="v mono">{thresholds.block}</div>
              <div className="k">policy</div>
              <div className="v mono">{thresholds.policy}</div>
            </>}
          </div>
          {schema.features && schema.features.length > 0 && (
            <details style={{ fontSize: 12 }}>
              <summary style={{ cursor: 'pointer', color: 'var(--text-dim)', marginBottom: 6 }}>
                ▸ Required feature columns ({schema.features.length})
              </summary>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
                {schema.features.map(f => (
                  <span key={f} className="mono" style={{
                    fontSize: 11, padding: '2px 7px', borderRadius: 4,
                    background: 'var(--bg-card)', border: '1px solid var(--border)',
                  }}>{f}</span>
                ))}
              </div>
            </details>
          )}
          {pcapStatus?.description && (
            <div className="warning-box warn" style={{ marginTop: 10, marginBottom: 0 }}>
              <span className="icon">⚠</span>
              <div style={{ fontSize: 12 }}><strong>PCAP validation status:</strong> {pcapStatus.description}</div>
            </div>
          )}
          {liveVMPage?.extractor_compatibility_notes && (
            <div className="dim" style={{ fontSize: 12, marginTop: 8 }}>
              {liveVMPage.extractor_compatibility_notes}
            </div>
          )}
          {liveVMPage?.simulation_only_warning && (
            <div className="warning-box bad" style={{ marginTop: 10, marginBottom: 0 }}>
              <span className="icon">⚠</span>
              <div style={{ fontSize: 12, fontWeight: 600 }}>{liveVMPage.simulation_only_warning}</div>
            </div>
          )}
        </div>
      )}

      <TabSwitcher tabs={tabs} active={tab} onChange={onTabChange} />

      <div className="tab-panel">
        {tab === 'replay'  && <LiveVMReplay />}
        {tab === 'monitor' && <LiveVMMonitor />}
      </div>
    </div>
  );
}
