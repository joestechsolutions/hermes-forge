import { useEffect, useState } from 'react';
import { AgentDetailData, clock, relative, statusClass, statusLabel } from './agentTypes';

type Props = { agentId: string; onBack: () => void };
type Tab = 'activity' | 'jobs';

export default function AgentDetail({ agentId, onBack }: Props) {
  const [data, setData] = useState<AgentDetailData | null>(null);
  const [error, setError] = useState(false);
  const [tab, setTab] = useState<Tab>('activity');

  useEffect(() => {
    let mounted = true;
    setData(null);
    setTab('activity');
    const load = async () => {
      try {
        const response = await fetch(`/api/v1/agents/${encodeURIComponent(agentId)}`, { cache: 'no-store', credentials: 'same-origin' });
        if (!response.ok) throw new Error('unavailable');
        const next = await response.json() as AgentDetailData;
        if (next.agent?.id !== agentId || !Array.isArray(next.sessions) || !Array.isArray(next.jobs)) throw new Error('invalid');
        if (mounted) { setData(next); setError(false); }
      } catch { if (mounted) setError(true); }
    };
    load();
    const timer = setInterval(load, 10_000);
    return () => { mounted = false; clearInterval(timer); };
  }, [agentId]);

  if (!data) return (
    <div className="bg-[#0c1e22] border border-[#1e383b] rounded-2xl p-5" role="status">
      <button onClick={onBack} className="lg:hidden min-h-11 text-[#4ecdc4] text-sm mb-3">← All agents</button>
      <p className="text-[#8fa8a5] text-sm">{error ? 'Agent activity is unavailable. Retry shortly.' : 'Loading agent activity…'}</p>
    </div>
  );

  const { agent } = data;
  return (
    <div className="space-y-4">
      <button onClick={onBack} className="lg:hidden min-h-11 text-[#4ecdc4] text-sm">← All agents</button>
      {error && <div role="status" className="border border-[#ffbd65]/40 bg-[#10262b] rounded-xl p-3 text-sm text-[#ffbd65]">Could not refresh. Values below may be stale.</div>}
      <header className="bg-[#0c1e22] border border-[#1e383b] rounded-2xl p-5">
        <div className="flex items-start justify-between gap-3">
          <div><h2 className="text-2xl font-bold">{agent.name}</h2><p className="text-[#4ecdc4] text-sm mt-1">{agent.role}</p></div>
          <span className={`text-[10px] px-2.5 py-1 border rounded-full whitespace-nowrap ${statusClass(agent)}`}>{statusLabel(agent)}</span>
        </div>
        <div className="mt-5 bg-[#071317] border border-[#1e383b] rounded-xl p-4">
          <p className="text-[10px] uppercase tracking-[0.2em] text-[#8fa8a5]">{data.active_now ? 'Working now' : 'Latest observed work'}</p>
          <p className="text-[#d9ece9] font-semibold mt-2 leading-relaxed">{data.current_title || agent.current_work}</p>
          {!data.active_now && <p className="text-[#8fa8a5] text-xs mt-2">No active session detected right now.</p>}
        </div>
        <div className="grid grid-cols-2 gap-3 mt-4 text-xs">
          <div><p className="text-[#8fa8a5]">Last observed work</p><p className="mt-1">{relative(agent.last_work_at)}</p></div>
          <div><p className="text-[#8fa8a5]">Next scheduled run</p><p className="text-[#4ecdc4] mt-1">{relative(agent.next_run_at, 'Not scheduled')}</p></div>
        </div>
        <p className="text-[#8fa8a5] text-[10px] mt-4">Updated {clock(data.generated_at)} · refreshes every 10s</p>
      </header>

      <div className="flex gap-2 bg-[#0c1e22] border border-[#1e383b] rounded-xl p-1.5" role="tablist" aria-label="Agent detail">
        <button role="tab" aria-selected={tab === 'activity'} onClick={() => setTab('activity')} className={`flex-1 min-h-11 rounded-lg text-sm ${tab === 'activity' ? 'bg-[#10262b] text-[#4ecdc4]' : 'text-[#8fa8a5]'}`}>Activity <span className="text-xs">({data.sessions.length})</span></button>
        <button role="tab" aria-selected={tab === 'jobs'} onClick={() => setTab('jobs')} className={`flex-1 min-h-11 rounded-lg text-sm ${tab === 'jobs' ? 'bg-[#10262b] text-[#4ecdc4]' : 'text-[#8fa8a5]'}`}>Scheduled work <span className="text-xs">({data.jobs.length})</span></button>
      </div>

      {!data.activity_available && <div role="status" className="text-[#ffbd65] text-sm bg-[#10262b] border border-[#ffbd65]/40 rounded-xl p-3">Session history is temporarily unavailable. Scheduled work is still shown.</div>}
      {tab === 'activity' ? (
        <section aria-label="Recent agent sessions" className="space-y-3">
          {data.sessions.length === 0 && <p className="text-[#8fa8a5] text-sm bg-[#0c1e22] border border-[#1e383b] rounded-xl p-5">No interactive sessions recorded. Check Scheduled work for automated results.</p>}
          {data.sessions.map((session, index) => (
            <article key={`${session.last_activity_at}-${index}`} className="bg-[#0c1e22] border border-[#1e383b] rounded-xl p-4">
              <div className="flex justify-between items-start gap-3">
                <h3 className="font-semibold text-sm leading-relaxed">{session.title}</h3>
                <span className={`text-[10px] whitespace-nowrap ${session.active ? 'text-[#4ecdc4]' : 'text-[#8fa8a5]'}`}>{session.active ? 'Working now' : session.ended_at ? 'Completed' : 'Idle'}</span>
              </div>
              {session.activity && session.activity !== session.title && <p className="text-[#b7d2cd] text-xs mt-2">{session.activity}</p>}
              {session.result && <details open={session.active ? true : undefined} className="mt-3 border-t border-[#1e383b] pt-2"><summary className="cursor-pointer min-h-11 flex items-center text-[#4ecdc4] text-xs">Final session result</summary><pre className="whitespace-pre-wrap break-words text-[#b7d2cd] text-xs leading-relaxed bg-[#071317] rounded-lg p-3 max-h-96 overflow-auto">{session.result}</pre>{session.result_truncated && <p className="text-[#8fa8a5] text-[10px] mt-2">Result capped at 6,000 characters.</p>}</details>}
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-[#8fa8a5] text-[11px] mt-3">
                <span>{relative(session.last_activity_at)}</span><span>{session.tool_call_count} tool calls</span>{session.model && <span className="font-mono">{session.model}</span>}
              </div>
            </article>
          ))}
        </section>
      ) : (
        <section aria-label="Agent scheduled jobs" className="space-y-3">
          {data.jobs.length === 0 && <p className="text-[#8fa8a5] text-sm bg-[#0c1e22] border border-[#1e383b] rounded-xl p-5">No scheduled jobs are attributed to this agent.</p>}
          {data.jobs.map(job => {
            const failed = job.failure_streak > 0 || !['ok', 'success', null].includes(job.last_status);
            return <article key={job.id} className={`bg-[#0c1e22] border rounded-xl p-4 ${failed ? 'border-[#ff6666]/60' : 'border-[#1e383b]'}`}>
              <div className="flex justify-between items-start gap-3"><h3 className="font-semibold text-sm break-words">{job.name}</h3><span className={`text-[10px] whitespace-nowrap ${failed ? 'text-[#ff6666]' : job.enabled ? 'text-[#4ecdc4]' : 'text-[#8fa8a5]'}`}>{failed ? 'Needs attention' : job.enabled ? 'Scheduled' : 'Paused / completed'}</span></div>
              <div className="grid grid-cols-2 gap-3 mt-3 text-[11px]"><div><p className="text-[#8fa8a5]">Cadence</p><p className="mt-1">{job.cadence}</p></div><div><p className="text-[#8fa8a5]">Last result</p><p className="mt-1">{job.last_status || 'No run yet'} · {relative(job.last_run_at, 'never')}</p></div><div><p className="text-[#8fa8a5]">Next run</p><p className="mt-1">{relative(job.next_run_at, 'Not scheduled')}</p></div>{job.model && <div><p className="text-[#8fa8a5]">Model</p><p className="font-mono mt-1 break-words">{job.model}</p></div>}</div>
              {job.paused_reason && <p className="text-[#ffbd65] text-xs mt-3">{job.paused_reason}</p>}
              {job.latest_output ? <details className="mt-4 border-t border-[#1e383b] pt-2"><summary className="cursor-pointer min-h-11 flex items-center text-[#4ecdc4] text-xs">Latest output · {relative(job.latest_output.mtime)}</summary><pre className="whitespace-pre-wrap break-words text-[#b7d2cd] text-xs leading-relaxed bg-[#071317] rounded-lg p-3 max-h-96 overflow-auto">{job.latest_output.body}</pre></details> : <p className="text-[#8fa8a5] text-xs mt-3">No saved output for this job.</p>}
            </article>;
          })}
        </section>
      )}
    </div>
  );
}
