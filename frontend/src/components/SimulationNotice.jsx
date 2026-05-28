import React from 'react';
import WarningBox from './WarningBox.jsx';

/**
 * SimulationNotice — thin variant wrapper around WarningBox so pages can use
 * a consistent name. Variants map to existing WarningBox tones:
 *   warning -> warn   (large yellow banner; use on interactive pages)
 *   danger  -> bad    (red; for hard refusals)
 *   info    -> info   (compact blue note; for informational pages)
 *   ok      -> ok     (green; for healthy states)
 *
 * Set `compact` to render a smaller inline badge-style note (used on
 * informational pages: Model Registry, Model Comparison, Robustness).
 */
export default function SimulationNotice({
  variant = 'warning',
  compact = false,
  icon,
  children,
}) {
  const tone =
    variant === 'warning' ? 'warn' :
    variant === 'danger'  ? 'bad'  :
    variant === 'ok'      ? 'ok'   :
                            'info';

  if (compact) {
    return (
      <div className={`sim-notice-compact ${tone}`}>
        <span className="dot" />
        <span>{children}</span>
      </div>
    );
  }
  return (
    <WarningBox tone={tone} icon={icon}>
      {children}
    </WarningBox>
  );
}

