import React from 'react';

export default function SummaryCard({ label, value, sub, accent }) {
  const cls = accent ? `summary-tile accent-${accent}` : 'summary-tile';
  return (
    <div className={cls}>
      <div className="label">{label}</div>
      <div className="value">{value ?? '—'}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}
