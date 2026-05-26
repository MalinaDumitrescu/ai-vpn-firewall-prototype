import React from 'react';

/**
 * Maps a registry status (or arbitrary keyword) to a visual badge.
 * Accepts a `status` prop or a free-form `label` + `tone`.
 */
const STATUS_MAP = {
  default_firewall: { tone: 'ok',      label: 'Default firewall' },
  policy_computed:  { tone: 'warn',    label: 'Comparison only' },
  negative_control: { tone: 'bad',     label: 'Negative control' },
  unsupported:      { tone: 'neutral', label: 'Unsupported' },
  alias:            { tone: 'info',    label: 'Alias' },
};

export default function StatusBadge({ status, label, tone, title }) {
  if (status && STATUS_MAP[status]) {
    const s = STATUS_MAP[status];
    return (
      <span className={`badge ${s.tone}`} title={title || status}>
        <span className="dot" />
        {s.label}
      </span>
    );
  }
  const t = tone || 'neutral';
  return (
    <span className={`badge ${t}`} title={title || label}>
      <span className="dot" />
      {label || status || 'unknown'}
    </span>
  );
}
