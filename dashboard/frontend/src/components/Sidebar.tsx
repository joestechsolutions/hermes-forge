import { ReactNode } from 'react';
import RuntimeStatus from './RuntimeStatus';

export type NavItem =
  | 'agents'
  | 'dashboard'
  | 'services'
  | 'models'
  | 'logs'
  | 'security'
  | 'snapshots'
  | 'briefings';

interface Props {
  active: NavItem;
  onNavigate: (item: NavItem) => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

const navItems: { id: NavItem; label: string }[] = [
  { id: 'agents', label: 'Agents' },
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'briefings', label: 'Command Center' },
  { id: 'services', label: 'Services' },
  { id: 'models', label: 'Models' },
  { id: 'logs', label: 'Logs' },
  { id: 'security', label: 'Security' },
  { id: 'snapshots', label: 'Snapshots' },
];

function NavLink({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3 text-sm tracking-wider uppercase transition-colors ${
        active
          ? 'text-[#02a0a0] bg-[#10262b] border-l-2 border-[#02a0a0]'
          : 'text-[#8fa8a5] hover:text-[#d9ece9] hover:bg-[#10262b] border-l-2 border-transparent'
      }`}
    >
      {label}
    </button>
  );
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="px-4 pt-4 pb-1 text-[10px] tracking-[0.2em] uppercase text-[#5d7573]">
      {children}
    </div>
  );
}

export default function Sidebar({ active, onNavigate, mobileOpen, onCloseMobile }: Props) {
  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 md:hidden"
          onClick={onCloseMobile}
        />
      )}
      <aside
        className={`fixed left-0 top-0 w-[240px] h-full bg-[#071317] border-r border-[#1e383b] flex flex-col z-50 transition-transform duration-200 md:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand — JTS block wordmark (echoes logo: teal JTS + amber pixel) */}
        <div className="px-6 pt-6 pb-4 border-b border-[#1e383b] flex items-start justify-between">
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-[#02a0a0] text-2xl font-extrabold tracking-[0.08em] leading-none">JTS</span>
              <span className="w-2 h-2 bg-[#ffbd65] inline-block" aria-hidden="true" />
            </div>
            <div className="text-[#5d7573] text-[10px] tracking-[0.18em] mt-1.5 uppercase">Joe's Tech Solutions</div>
          </div>
          <button
            onClick={onCloseMobile}
            className="md:hidden text-[#8fa8a5] hover:text-white text-xl leading-none px-1"
            aria-label="Close menu"
          >
            ×
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-2">
          <SectionLabel>Navigation</SectionLabel>
          {navItems.map((item) => (
            <NavLink
              key={item.id}
              active={active === item.id}
              label={item.label}
              onClick={() => { onNavigate(item.id); onCloseMobile(); }}
            />
          ))}

        </nav>

        {/* Bottom status */}
        <div className="px-4 py-3 border-t border-[#1e383b]">
          <RuntimeStatus />
          <a href="/api/auth/logout" className="mt-3 min-h-11 flex items-center justify-center rounded-xl border border-[#1e383b] text-[#8fa8a5] text-xs hover:text-[#d9ece9] hover:border-[#02a0a0]/40">
            Sign out
          </a>
          <div className="text-[#5d7573] text-[10px]">v2.0.0</div>
        </div>
      </aside>
    </>
  );
}