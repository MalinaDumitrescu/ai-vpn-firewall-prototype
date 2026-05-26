import React from 'react';

export default function WarningBox({ tone = 'warn', icon, children }) {
  const iconChar = icon || (
    tone === 'bad'  ? '⛔' :
    tone === 'info' ? 'ℹ' :
    tone === 'ok'   ? '✓' :
                      '⚠'
  );
  return (
    <div className={`warning-box ${tone}`}>
      <span className="icon">{iconChar}</span>
      <div>{children}</div>
    </div>
  );
}
