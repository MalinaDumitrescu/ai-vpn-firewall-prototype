import React, { useEffect, useState } from 'react';
import Navbar from './components/Navbar.jsx';
import Dashboard from './pages/Dashboard.jsx';
import MultiModelCsvEvaluation from './pages/MultiModelCsvEvaluation.jsx';
import LiveVM from './pages/LiveVM.jsx';
import Models from './pages/Models.jsx';
import Robustness from './pages/Robustness.jsx';
import { api, API_BASE } from './api.js';

// Legacy page ids kept as aliases so old bookmarks / links do not break.
const LEGACY_ALIASES = {
  livereplay:  'livevm',
  livemonitor: 'livevm',
  registry:    'models',
  comparison:  'models',
  // demorunner / firewall handled inline in handleNavigate with tab selection
};

export default function App() {
  const [page, setPage]           = useState('dashboard');
  const [liveVmTab, setLiveVmTab] = useState('replay');
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

  function handleNavigate(pageId) {
    // Legacy routes: redirect to LiveVM with the appropriate tab.
    if (pageId === 'demorunner') {
      setPage('livevm');
      setLiveVmTab('monitor');
      return;
    }
    if (pageId === 'firewall') {
      setPage('livevm');
      setLiveVmTab('replay');
      return;
    }
    // When explicitly clicking Live VM from the navbar, go to default replay tab.
    if (pageId === 'livevm') {
      setLiveVmTab('replay');
    }
    setPage(LEGACY_ALIASES[pageId] || pageId);
  }

  const resolvedPage = LEGACY_ALIASES[page] || page;

  let body = null;
  switch (resolvedPage) {
    case 'multimodel':  body = <MultiModelCsvEvaluation />; break;
    case 'livevm':
      body = <LiveVM tab={liveVmTab} onTabChange={setLiveVmTab} />; break;
    case 'models':      body = <Models />; break;
    case 'robustness':  body = <Robustness />; break;
    case 'dashboard':
    default:            body = <Dashboard />; break;
  }

  return (
    <div className="app-shell">
      <Navbar current={resolvedPage} onNavigate={handleNavigate} apiStatus={apiStatus} />
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
