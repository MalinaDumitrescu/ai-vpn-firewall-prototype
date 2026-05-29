import React, { useRef, useState } from 'react';
import { api } from '../api.js';
import SummaryCard from '../components/SummaryCard.jsx';
import SessionTable from '../components/SessionTable.jsx';
import WarningBox from '../components/WarningBox.jsx';
import StatusBadge from '../components/StatusBadge.jsx';

function num(v, d = 4) {
  if (v === null || v === undefined) return '—';
  if (typeof v !== 'number') return String(v);
  if (Number.isInteger(v)) return v.toString();
  return v.toFixed(d);
}

export default function FirewallDemo() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const fileRef = useRef(null);

  async function runDemo() {
    setLoading(true);
    setError(null);
    try {
      const r = await api.firewallDemo();
      setResult(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function uploadCsv(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.analyzeCsv(file);
      setResult(r);
    } catch (e2) {
      setError(e2.message);
    } finally {
      setLoading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  const counts = result?.counts || { PASS: 0, FLAG_REVIEW: 0, BLOCK: 0 };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>Single-model demo</h1>
          <div className="subtitle">
            Run the default <span className="mono">full_canonical__lgbm</span>{' '}
            model on bundled flows or an uploaded CSV. All actions are{' '}
            <strong>simulated</strong>.
          </div>
        </div>
        <div className="button-row">
          <button onClick={runDemo} disabled={loading}>
            {loading ? <><span className="spinner" />&nbsp;Running…</> : 'Run bundled demo'}
          </button>
          <button
            className="secondary"
            onClick={() => fileRef.current?.click()}
            disabled={loading}
          >
            Upload CSV
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            style={{ display: 'none' }}
            onChange={uploadCsv}
          />
        </div>
      </div>

      <WarningBox tone="warn">
        <strong>Simulation only.</strong> BLOCK / FLAG_REVIEW outcomes are
        recommendations from the model — no real packets are dropped.
      </WarningBox>

      {error && <div className="error-box">Error: {error}</div>}

      {result && (
        <>
          <div className="section grid cols-4">
            <SummaryCard label="Total flows" value={result.total_flows} accent="info" />
            <SummaryCard label="Total sessions" value={result.total_sessions} accent="info" />
            <SummaryCard label="Action mode" value={result.action_mode} accent="warn" />
            <SummaryCard
              label="Production ready"
              value={result.production_readiness ? 'true' : 'false'}
              accent={result.production_readiness ? 'warn' : 'bad'}
            />
          </div>

          <div className="section grid cols-3">
            <SummaryCard label="PASS"        value={counts.PASS}        accent="ok"   sub="Below balanced threshold" />
            <SummaryCard label="FLAG_REVIEW" value={counts.FLAG_REVIEW} accent="warn" sub="Balanced trigger only" />
            <SummaryCard label="BLOCK"       value={counts.BLOCK}       accent="bad"  sub="Strict trigger (simulated)" />
          </div>

          <div className="section grid cols-2">
            <div className="card">
              <h2>Active policy</h2>
              <div className="kv">
                <div className="k">model_id</div>
                <div className="v mono">{result.model_id}</div>

                <div className="k">probability_column</div>
                <div className="v mono">{result.probability_column}</div>

                <div className="k">aggregation</div>
                <div className="v mono">{result.aggregation}</div>

                <div className="k">strict threshold</div>
                <div className="v">{num(result.thresholds?.strict, 6)}</div>

                <div className="k">balanced threshold</div>
                <div className="v">{num(result.thresholds?.balanced, 6)}</div>

                <div className="k">action_mode</div>
                <div className="v">
                  <StatusBadge tone="warn" label={result.action_mode} />
                </div>

                <div className="k">production_readiness</div>
                <div className="v">
                  <StatusBadge
                    tone={result.production_readiness ? 'warn' : 'bad'}
                    label={result.production_readiness ? 'true' : 'false'}
                  />
                </div>
              </div>
            </div>

            <div className="card">
              <h2>Backend warnings</h2>
              {Array.isArray(result.warnings) && result.warnings.length > 0 ? (
                <ul className="clean">
                  {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
                </ul>
              ) : (
                <div className="muted">No warnings reported.</div>
              )}
            </div>
          </div>

          <div className="section">
            <div className="page-header" style={{ marginBottom: 10 }}>
              <h1 style={{ fontSize: 16 }}>Per-session decisions</h1>
              <div className="subtitle">
                {result.total_sessions} session(s) scored.
              </div>
            </div>
            <SessionTable sessions={result.sessions || []} />
          </div>
        </>
      )}

      {!result && !error && !loading && (
        <div className="card">
          <h2>Get started</h2>
          <div className="dim">
            Click <strong>Run bundled demo</strong> to score the sample flows shipped
            with the runtime bundle using <span className="mono">full_canonical__lgbm</span>{' '}
            (34 features), or upload a CSV containing the full-canonical feature set
            (<span className="mono">sz_coef_variation, sz_all_mean, iat_all_mean, …</span> — 34 total).
            For the legacy 9-feature robust9 schema use the multi-model evaluation page.
          </div>
        </div>
      )}
    </div>
  );
}
