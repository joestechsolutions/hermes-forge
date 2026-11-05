import { useEffect, useState } from 'react';
import AgentDetail from './AgentDetail';
import { clock, relative, Roster, statusClass, statusLabel } from './agentTypes';

export default function AgentsPage() {
  const [roster, setRoster] = useState<Roster | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showMobileDetail, setShowMobileDetail] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const response = await fetch('/api/v1/agents', { cache: 'no-store', credentials: 'same-origin' });
        if (!response.ok) throw new Error('unavailable');
        const next = await response.json() as Roster;
        if (!Array.isArray(next.agents)) throw new Error('invalid');
        if (mounted) {
          setRoster(next);
          setSelectedId(current => current && next.agents.some(agent => agent.id === current) ? current : next.agents[0]?.id || null);
          setError(false);
        }
      } catch { if (mounted) setError(true); }
    };
    load();
    const timer = setInterval(load, 15_000);
    return () => { mounted = false; clearInterval(timer); };
  }, []);

  const agents = roster?.agents || [];
  const working = agents.filter(agent => agent.active_now).length;
  const attention = agents.filter(agent => agent.failing_jobs > 0).length;
  const nextUp = agents.filter(agent => agent.next_run_at).sort((a, b) => new Date(a.next_run_at || '').getTime() - new Date(b.next_run_at || '').getTime())[0];

  return (
    <div className="max-w-[1600px] mx-auto">
      <header className="mb-5">
        <div className="flex flex-wrap justify-between items-end gap-3">
          <div><p className="text-[#4ecdc4] text-[10px] uppercase tracking-[0.25em]">Live work center</p><h1 className="text-3xl font-bold mt-2">Agents</h1><p className="text-[#8fa8a5] text-sm mt-2">Tap an agent to see what it is doing and what it finished.</p></div>
          <p className="text-[#8fa8a5] text-xs">{roster ? `${roster.count} agents · updated ${clock(roster.generated_at)}` : 'Loading live status…'}</p>
        </div>
      </header>
      {error && <div role="status" className="border border-[#ffbd65]/40 bg-[#10262b] rounded-xl p-3 text-sm text-[#ffbd65] mb-4">Could not refresh the roster. Existing values may be stale.</div>}

      <section aria-label="Fleet activity summary" className="grid grid-cols-3 gap-2 sm:gap-3 mb-5">
        <div className="bg-[#0c1e22] border border-[#1e383b] rounded-xl p-3 sm:p-4"><p className="text-[#8fa8a5] text-[10px] sm:text-xs uppercase tracking-wider">Working now</p><p className="text-[#4ecdc4] text-2xl font-bold mt-1">{working}</p></div>
        <div className="bg-[#0c1e22] border border-[#1e383b] rounded-xl p-3 sm:p-4"><p className="text-[#8fa8a5] text-[10px] sm:text-xs uppercase tracking-wider">Needs attention</p><p className={`text-2xl font-bold mt-1 ${attention ? 'text-[#ffbd65]' : 'text-[#d9ece9]'}`}>{attention}</p></div>
        <div className="bg-[#0c1e22] border border-[#1e383b] rounded-xl p-3 sm:p-4"><p className="text-[#8fa8a5] text-[10px] sm:text-xs uppercase tracking-wider">Next run</p><p className="text-sm font-semibold mt-1 truncate">{nextUp ? nextUp.name : 'None'}</p><p className="text-[#4ecdc4] text-[11px] mt-0.5">{nextUp ? relative(nextUp.next_run_at, 'Not scheduled') : 'Not scheduled'}</p></div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-[320px_minmax(0,1fr)] xl:grid-cols-[360px_minmax(0,1fr)] gap-4 items-start">
        <section aria-label="Installed agents" className={`${showMobileDetail ? 'hidden' : 'block'} lg:block space-y-3`}>
          {!roster && !error && <div className="bg-[#0c1e22] border border-[#1e383b] rounded-xl p-5 text-[#8fa8a5] text-sm" role="status">Loading agents…</div>}
          {roster && agents.length === 0 && <p className="text-[#8fa8a5] text-sm">No installed agents found.</p>}
          {agents.map(agent => (
            <button key={agent.id} aria-pressed={selectedId === agent.id} aria-label={`Open ${agent.name} activity`} onClick={() => { setSelectedId(agent.id); setShowMobileDetail(true); }} className={`w-full text-left bg-[#0c1e22] border rounded-2xl p-4 transition-colors ${selectedId === agent.id ? 'border-[#02a0a0]/70 bg-[#10262b]' : agent.failing_jobs > 0 ? 'border-[#ffbd65]/60 hover:border-[#ffbd65]' : 'border-[#1e383b] hover:border-[#02a0a0]/40'}`}>
              <div className="flex justify-between items-start gap-3">
                <div><h2 className="font-bold text-base">{agent.name}</h2><p className="text-[#4ecdc4] text-[11px] mt-0.5">{agent.role}</p></div>
                <span className={`text-[10px] px-2.5 py-1 border rounded-full whitespace-nowrap ${statusClass(agent)}`}>{statusLabel(agent)}</span>
              </div>
              <p className="text-[#b7d2cd] text-xs mt-3 line-clamp-2">{agent.current_work}</p>
              <div className="flex justify-between gap-3 text-[#8fa8a5] text-[11px] mt-3 pt-3 border-t border-[#1e383b]"><span>Last work {relative(agent.last_work_at)}</span><span>{agent.active_jobs} scheduled</span></div>
            </button>
          ))}
        </section>
        <section aria-label="Selected agent detail" className={`${showMobileDetail ? 'block' : 'hidden'} lg:block min-w-0`}>
          {selectedId ? <AgentDetail key={selectedId} agentId={selectedId} onBack={() => setShowMobileDetail(false)} /> : <div className="bg-[#0c1e22] border border-[#1e383b] rounded-2xl p-6 text-[#8fa8a5]">Select an agent.</div>}
        </section>
      </div>
    </div>
  );
}
