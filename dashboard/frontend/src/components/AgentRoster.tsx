import { useEffect, useState } from 'react';

type Agent = {
  id: string;
  name: string;
  role: string;
  description: string;
  status: 'ready' | 'active' | 'completed' | 'needs-attention';
  current_work: string;
  last_work_at: string | null;
  scheduled_jobs: number;
  active_jobs: number;
  failing_jobs: number;
  next_run_at: string | null;
};

type Roster = { agents: Agent[]; count: number; generated_at: string };

function relative(iso: string | null): string {
  if (!iso) return 'Not scheduled';
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return 'Not scheduled';
  const minutes = Math.round(Math.abs(then - Date.now()) / 60000);
  const suffix = then > Date.now() ? 'from now' : 'ago';
  if (minutes < 60) return `${minutes}m ${suffix}`;
  if (minutes < 1440) return `${Math.round(minutes / 60)}h ${suffix}`;
  return new Date(iso).toLocaleDateString();
}

const STATUS_LABEL: Record<Agent['status'], string> = {
  ready: 'No work yet',
  active: 'Working now',
  completed: 'Idle',
  'needs-attention': 'Needs attention',
};

export default function AgentRoster() {
  const [data, setData] = useState<Roster | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const response = await fetch('/api/v1/agents', { credentials: 'same-origin', cache: 'no-store' });
        if (!response.ok) throw new Error('unavailable');
        const next = await response.json();
        if (mounted) {
          setData(next);
          setError(false);
        }
      } catch {
        if (mounted) setError(true);
      }
    };
    load();
    const timer = setInterval(load, 30_000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <section aria-labelledby="agent-roster-title" className="mb-8">
      <div className="flex justify-between items-end gap-4 mb-3">
        <div>
          <h2 id="agent-roster-title" className="text-lg font-bold text-[#d9ece9] tracking-wider uppercase">Your agents</h2>
          <p className="text-[#8fa8a5] text-xs mt-1">Who owns what, and the latest observed status.</p>
        </div>
        <span className="text-[#5d7573] text-[10px] shrink-0">{data ? `${data.count} agents` : ''}</span>
      </div>
      {error && (
        <div role="status" className="border border-[#ffbd65]/40 bg-[#10262b] p-4 text-sm text-[#ffbd65] mb-4">
          Agent status could not refresh. Existing values may be stale; scheduled reports are below.
        </div>
      )}
      {!data && !error && <div role="status" className="text-[#8fa8a5] text-sm mb-4">Loading agents…</div>}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {data?.agents.map(agent => (
          <article key={agent.id} className={`bg-[#0c1e22] border rounded-2xl p-5 shadow-[0_14px_36px_rgba(0,0,0,0.18)] ${agent.failing_jobs > 0 ? 'border-[#ff6666]/60' : 'border-[#1e383b]'}`}>
            <div className="flex justify-between gap-2 items-start">
              <div className="min-w-0">
                <h3 className="font-bold text-[#d9ece9] text-base">{agent.name}</h3>
                <p className="text-[#4ecdc4] text-[11px] mt-0.5">{agent.role}</p>
              </div>
              <span className={`inline-flex items-center gap-1.5 text-[10px] px-2.5 py-1 border rounded-full whitespace-nowrap ${agent.status === 'needs-attention' ? 'text-[#ffbd65] border-[#ffbd65]/50 bg-[#ffbd65]/5' : 'text-[#4ecdc4] border-[#02a0a0]/40 bg-[#02a0a0]/5'}`}>
                <span aria-hidden="true" className={`w-1.5 h-1.5 rounded-full ${agent.status === 'needs-attention' ? 'bg-[#ffbd65]' : 'bg-[#4ecdc4]'}`} />
                {STATUS_LABEL[agent.status]}
              </span>
            </div>
            <p className="text-[#b7d2cd] text-xs mt-3 leading-relaxed line-clamp-3">{agent.description}</p>
            <p className="text-[#8fa8a5] text-xs mt-3 bg-[#10262b] rounded-xl px-3 py-2.5">{agent.current_work}</p>
            <dl className="grid grid-cols-2 gap-x-3 gap-y-2 mt-4 pt-3 border-t border-[#1e383b] text-[11px]">
              <div><dt className="text-[#8fa8a5]">Scheduled jobs</dt><dd className="text-[#d9ece9] mt-0.5">{agent.scheduled_jobs}</dd></div>
              <div><dt className="text-[#8fa8a5]">Last work</dt><dd className="text-[#d9ece9] mt-0.5">{relative(agent.last_work_at)}</dd></div>
              <div className="col-span-2"><dt className="text-[#8fa8a5]">Next scheduled run</dt><dd className="text-[#4ecdc4] mt-0.5">{relative(agent.next_run_at)}</dd></div>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}
