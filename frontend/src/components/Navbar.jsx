import React from 'react';

const LINKS = [
  { id: 'dashboard',   label: 'Dashboard' },
  { id: 'firewall',    label: 'Firewall Demo' },
  { id: 'multimodel',  label: 'Multi-model CSV' },
  { id: 'livereplay',  label: 'Live VM Replay' },
  { id: 'livemonitor', label: 'Live VM Monitor' },
  { id: 'registry',    label: 'Model Registry' },
  { id: 'comparison',  label: 'Model Comparison' },
  { id: 'robustness',  label: 'Robustness' },
];

export default function Navbar({ current, onNavigate, apiStatus }) {
  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <span className="logo-dot" />
        AI&nbsp;VPN&nbsp;Firewall
        <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>
          &nbsp;/ prototype
        </span>
      </div>
      <div className="navbar-links">
        {LINKS.map((link) => (
          <div
            key={link.id}
            className={`navbar-link ${current === link.id ? 'active' : ''}`}
            onClick={() => onNavigate(link.id)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === 'Enter') onNavigate(link.id); }}
          >
            {link.label}
          </div>
        ))}
      </div>
      <div className="navbar-meta">
        {apiStatus === 'ok'   && <span className="badge ok"><span className="dot" />API ONLINE</span>}
        {apiStatus === 'down' && <span className="badge bad"><span className="dot" />API OFFLINE</span>}
        {apiStatus === 'loading' && <span className="badge neutral"><span className="dot" />…</span>}
      </div>
    </nav>
  );
}




