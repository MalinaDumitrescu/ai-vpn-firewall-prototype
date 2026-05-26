import React, { useEffect, useState } from 'react';
import Navbar from './components/Navbar.jsx';
import Dashboard from './pages/Dashboard.jsx';
import FirewallDemo from './pages/FirewallDemo.jsx';
import MultiModelCsvEvaluation from './pages/MultiModelCsvEvaluation.jsx';
import LiveVMReplay from './pages/LiveVMReplay.jsx';
import LiveVMMonitor from './pages/LiveVMMonitor.jsx';
import ModelRegistry from './pages/ModelRegistry.jsx';
import ModelComparison from './pages/ModelComparison.jsx';
import Robustness from './pages/Robustness.jsx';
import { api, API_BASE } from './api.js';

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

  let body = null;
  switch (page) {
    case 'firewall':    body = <FirewallDemo />; break;
    case 'multimodel':  body = <MultiModelCsvEvaluation />; break;
    case 'livereplay':  body = <LiveVMReplay />; break;
    case 'livemonitor': body = <LiveVMMonitor />; break;
    case 'registry':    body = <ModelRegistry />; break;
    case 'comparison':  body = <ModelComparison />; break;
    case 'robustness':  body = <Robustness />; break;
    case 'dashboard':
    default:            body = <Dashboard />; break;
  }

  return (
    <div className="app-shell">
      <Navbar current={page} onNavigate={setPage} apiStatus={apiStatus} />
      <main className="app-main">
        {body}
        <div className="footer-note">
          API: <span className="mono">{API_BASE}</span> · Simulation mode ·
          Prototype build — not for production deployment.
        </div>
      </main>
    </div>
  );
}







