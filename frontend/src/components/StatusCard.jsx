import React from 'react';
import SummaryCard from './SummaryCard.jsx';

/**
 * StatusCard — props-renamed wrapper around SummaryCard so pages can use
 * the requested API:
 *   <StatusCard label="API Status" value="Online"
 *               subtitle="AI VPN Firewall Prototype API" tone="success" />
 *
 * `tone` maps to the existing accent palette:
 *   success -> ok
 *   warn    -> warn
 *   danger  -> bad
 *   info    -> info
 */
export default function StatusCard({ label, value, subtitle, tone }) {
  const accent =
    tone === 'success' ? 'ok'   :
    tone === 'danger'  ? 'bad'  :
    tone === 'warn'    ? 'warn' :
    tone === 'info'    ? 'info' :
                         undefined;
  return <SummaryCard label={label} value={value} sub={subtitle} accent={accent} />;
}

