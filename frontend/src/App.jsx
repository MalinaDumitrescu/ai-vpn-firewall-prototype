import React, { useEffect, useState } from 'react';
import Navbar from './components/Navbar.jsx';
import Dashboard from './pages/Dashboard.jsx';
import FirewallDemo from './pages/FirewallDemo.jsx';
import MultiModelCsvEvaluation from './pages/MultiModelCsvEvaluation.jsx';
import LiveVM from './pages/LiveVM.jsx';
import Models from './pages/Models.jsx';
import Robustness from './pages/Robustness.jsx';
import DemoRunner from './pages/DemoRunner.jsx';
import { api, API_BASE } from './api.js';

// Legacy page ids are kept working as aliases so old bookmarks / links do not
// break after the navigation refactor.
const LEGACY_ALIASES = {
  livereplay:  'livevm',
  livemonitor: 'livevm',
  registry:    'models',
  comparison:  'models',
};

export default function App() {
  const [page, setPage] = useState('dashboard');
  const [apiStatus, setApiStatus] = useState('loading');

  useEffect(() => {
    let mounted = true;
    async function ping() {
      try {
        await api.health();
        if (mounted) setApiStatus('ok');
      } catch {
        if (mounted) setApiStatus('down');
      }
    }
    ping();
    const t = setInterval(ping, 15000);
    return () => { mounted = false; clearInterval(t); };
  }, []);

  const resolvedPage = LEGACY_ALIASES[page] || page;

  let body = null;
  switch (resolvedPage) {
    case 'firewall':    body = <FirewallDemo />; break;
    case 'multimodel':  body = <MultiModelCsvEvaluation />; break;
    case 'livevm':      body = <LiveVM />; break;
    case 'models':      body = <Models />; break;
    case 'robustness':  body = <Robustness />; break;
    case 'demorunner':  body = <DemoRunner onNavigate={setPage} />; break;
    case 'dashboard':
    default:            body = <Dashboard />; break;
  }

  return (
    <div className="app-shell">
      <Navbar current={resolvedPage} onNavigate={setPage} apiStatus={apiStatus} />
      <main className="app-main">
        {body}
        <div className="footer-note">
          API: <span className="mono">{API_BASE}</span> &middot; Simulation mode &middot;
          Prototype build &mdash; not for production deployment.
        </div>
      </main>
    </div>
  );
}







