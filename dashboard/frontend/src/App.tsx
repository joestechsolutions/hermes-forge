import { useState } from 'react';
import Sidebar, { NavItem } from './components/Sidebar';
import DashboardPage from './pages/DashboardPage';
import ModelsPage from './pages/ModelsPage';
import LogsPage from './pages/LogsPage';
import SecurityPage from './pages/SecurityPage';
import SnapshotsPage from './pages/SnapshotsPage';
import CommandCenterPage from './pages/CommandCenterPage';
import ServicesPage from './pages/ServicesPage';

const TITLES: Record<NavItem, string> = {
  dashboard: 'Dashboard',
  briefings: 'Command Center',
  services: 'Services',
  models: 'Models',
  logs: 'Logs',
  security: 'Security',
  snapshots: 'Snapshots',
};

export default function App() {
  const [activeNav, setActiveNav] = useState<NavItem>('dashboard');
  const [mobileOpen, setMobileOpen] = useState(false);

  const renderPage = () => {
    switch (activeNav) {
      case 'dashboard':
        return <DashboardPage />;
      case 'briefings':
        return <CommandCenterPage />;
      case 'services':
        return <ServicesPage />;
      case 'models':
        return <ModelsPage />;
      case 'logs':
        return <LogsPage />;
      case 'security':
        return <SecurityPage />;
      case 'snapshots':
        return <SnapshotsPage />;
      default:
        return <DashboardPage />;
    }
  };

  return (
    <div className="min-h-screen bg-[#071317] text-[#d9ece9]">
      <Sidebar
        active={activeNav}
        onNavigate={setActiveNav}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
      />
      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 md:hidden flex items-center gap-3 bg-[#071317]/95 border-b border-[#1e383b] px-3 py-2.5">
        <button
          onClick={() => setMobileOpen(true)}
          className="text-[#02a0a0] border border-[#1e383b] min-w-11 min-h-11 px-2.5 py-1.5 text-lg leading-none rounded-xl"
          aria-label="Open menu"
        >
          ☰
        </button>
        <span className="flex items-center gap-1.5">
          <span className="text-[#02a0a0] text-lg font-extrabold tracking-[0.08em]">JTS</span>
          <span className="w-1.5 h-1.5 bg-[#ffbd65] inline-block" aria-hidden="true" />
        </span>
        <span className="text-[#5d7573] text-xs uppercase tracking-wider">{TITLES[activeNav]}</span>
      </header>
      <main className="md:ml-[240px] min-h-screen p-3 sm:p-4 md:p-6">
        {renderPage()}
      </main>
    </div>
  );
}