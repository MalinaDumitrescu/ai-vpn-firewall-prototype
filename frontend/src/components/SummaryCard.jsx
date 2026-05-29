import React from 'react';

export default function SummaryCard({ label, value, sub, accent, compact }) {
  const cls = [
    'summary-tile',
    accent ? `accent-${accent}` : '',
    compact ? 'compact' : '',
  ].filter(Boolean).join(' ');
  return (
    <div className={cls}>
      <div className="label">{label}</div>
      <div className="value">{value ?? '—'}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}
