import React from 'react';

/**
 * TabSwitcher — small segmented-button row used to switch between sub-views
 * inside a single page (e.g. Live VM > CSV Replay / PCAP Monitor).
 *
 * Props:
 *   tabs:    [{ id, label, badge? }]
 *   active:  string  (the active tab id)
 *   onChange: (id) => void
 */
export default function TabSwitcher({ tabs, active, onChange }) {
  return (
    <div className="tab-switcher" role="tablist">
      {tabs.map((t) => {
        const isActive = t.id === active;
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            className={`tab-switcher-btn ${isActive ? 'active' : ''}`}
            onClick={() => onChange(t.id)}
          >
            {t.label}
            {t.badge !== undefined && t.badge !== null && (
              <span className="tab-switcher-badge">{t.badge}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

