import React from 'react';

function num(v, d = 4) {
  if (v === null || v === undefined) return '—';
  if (typeof v !== 'number') return String(v);
  if (Number.isInteger(v)) return v.toString();
  return v.toFixed(d);
}

function Bool({ value }) {
  if (value === true)  return <span className="badge ok"><span className="dot" />true</span>;
  if (value === false) return <span className="badge neutral"><span className="dot" />false</span>;
  return <span className="muted">—</span>;
}

export default function SessionTable({ sessions }) {
  if (!sessions || sessions.length === 0) {
    return <div className="muted">No sessions to display.</div>;
  }
  return (
    <div className="table-wrap">
      <table className="dash">
        <thead>
          <tr>
            <th>Session ID</th>
            <th>Flows</th>
            <th>Mean flow score</th>
            <th>Max flow score</th>
            <th>Session score</th>
            <th>Strict</th>
            <th>Balanced</th>
            <th>Action</th>
            <th>Simulated</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s) => (
            <tr key={s.session_id}>
              <td className="mono">{s.session_id}</td>
              <td className="num">{s.n_flows}</td>
              <td className="num">{num(s.flow_score_mean)}</td>
              <td className="num">{num(s.flow_score_max)}</td>
              <td className="num"><strong>{num(s.session_score)}</strong></td>
              <td><Bool value={s.strict_trigger} /></td>
              <td><Bool value={s.balanced_trigger} /></td>
              <td><span className={`action-pill ${s.action}`}>{s.action}</span></td>
              <td><Bool value={s.simulated} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
