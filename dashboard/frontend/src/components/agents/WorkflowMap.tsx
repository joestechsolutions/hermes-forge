import { useState } from 'react';
import { clock, relative, WorkflowData, WorkflowTask } from './agentTypes';

function taskStatus(task: WorkflowTask): string {
  if (task.active_now) return 'Working now';
  if (task.status === 'completed') return 'Completed';
  if (task.status === 'running') return 'Running state not confirmed';
  return task.status.charAt(0).toUpperCase() + task.status.slice(1);
}

function TaskList({ tasks, empty }: { tasks: WorkflowTask[]; empty: string }) {
  if (!tasks.length) return <p className="text-[#8fa8a5] text-xs mt-3 leading-relaxed">{empty}</p>;
  return <div className="space-y-2 mt-3">{tasks.slice(0, 4).map(task => (
    <div key={`${task.label}-${task.index}`} className="flex items-start justify-between gap-2 text-xs">
      <div className="min-w-0"><p className="text-[#d9ece9] truncate">{task.label}</p><p className="text-[#8fa8a5] text-[10px] mt-0.5 truncate">{task.model || 'Delegated agent'}</p></div>
      <span className={`whitespace-nowrap text-[10px] ${task.active_now ? 'text-[#4ecdc4]' : 'text-[#8fa8a5]'}`}>{taskStatus(task)}</span>
    </div>
  ))}</div>;
}

function StepTitle({ number, title, subtitle }: { number: string; title: string; subtitle: string }) {
  return <div className="flex items-center gap-2"><span className="w-6 h-6 rounded-full bg-[#10262b] border border-[#02a0a0]/40 text-[#4ecdc4] text-[11px] font-bold flex items-center justify-center">{number}</span><div><h3 className="font-semibold text-sm">{title}</h3><p className="text-[#8fa8a5] text-[10px]">{subtitle}</p></div></div>;
}

export default function WorkflowMap({ data, error }: { data: WorkflowData | null; error: boolean }) {
  const [showAll, setShowAll] = useState(false);

  const events = data?.events || [];
  const visibleEvents = showAll ? events : events.slice(0, 3);
  return <section aria-label="Live agent workflow" className="bg-[#0c1e22] border border-[#1e383b] rounded-2xl p-4 sm:p-5 mb-5">
    <div className="flex flex-wrap justify-between items-start gap-3 mb-4">
      <div><p className="text-[#4ecdc4] text-[10px] uppercase tracking-[0.2em]">Lead → workers → advisor → verify</p><h2 className="font-bold text-lg mt-1">How work is moving</h2><p className="text-[#8fa8a5] text-xs mt-1">Actual roles and events, not a progress bar.</p></div>
      <p className="text-[#8fa8a5] text-[11px]">{data ? `Updated ${clock(data.generated_at)}` : 'Loading workflow…'}</p>
    </div>
    {error && <div role="status" className="text-[#ffbd65] text-xs bg-[#10262b] border border-[#ffbd65]/40 rounded-xl p-3 mb-4">Could not refresh the workflow. Existing values may be stale.</div>}
    {data && !data.available && <div role="status" className="text-[#ffbd65] text-xs bg-[#10262b] border border-[#ffbd65]/40 rounded-xl p-3 mb-4">The delegation ledger is temporarily unavailable. No activity is being assumed.</div>}
    {data?.run && <p className={`text-xs mb-4 ${data.run.active_now ? 'text-[#4ecdc4]' : data.run.state === 'stale' ? 'text-[#ffbd65]' : 'text-[#8fa8a5]'}`}>{data.run.active_now ? 'Delegated batch is working now.' : data.run.state === 'stale' ? 'Latest batch is stale — no active owner process is confirmed.' : `Latest delegated batch: ${data.run.state}.`}</p>}

    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
      <article className="bg-[#071317] border border-[#1e383b] rounded-xl p-4 min-w-0">
        <StepTitle number="1" title="Lurkr · Lead" subtitle="Delegates and coordinates" />
        {data ? <><p className={`text-xs font-semibold mt-3 ${data.lead.active_now ? 'text-[#4ecdc4]' : 'text-[#d9ece9]'}`}>{data.lead.active_now ? 'Working now' : 'Idle'}</p><p className="text-[#b7d2cd] text-xs mt-1 truncate">Latest tool: {data.lead.current_action}</p><p className="text-[#8fa8a5] text-[10px] mt-1 truncate">{data.lead.model || 'Main Hermes session'}</p></> : <p className="text-[#8fa8a5] text-xs mt-3">Loading lead…</p>}
      </article>
      <article className="bg-[#071317] border border-[#1e383b] rounded-xl p-4 min-w-0">
        <StepTitle number="2" title="Workers" subtitle="Parallel delegated tasks" />
        {data ? <TaskList tasks={data.workers} empty={data.run ? 'No worker tasks in the latest batch.' : 'No delegation recorded yet.'} /> : <p className="text-[#8fa8a5] text-xs mt-3">Loading workers…</p>}
      </article>
      <article className="bg-[#071317] border border-[#1e383b] rounded-xl p-4 min-w-0">
        <StepTitle number="3" title="Advisor" subtitle="Explicit independent checkpoints" />
        {data ? <TaskList tasks={data.advisors} empty="No explicitly tagged advisor in the latest batch." /> : <p className="text-[#8fa8a5] text-xs mt-3">Loading advisor…</p>}
      </article>
      <article className="bg-[#071317] border border-[#1e383b] rounded-xl p-4 min-w-0">
        <StepTitle number="4" title="Verification" subtitle="A result, not a vibe" />
        {data ? <><p className={`text-xs font-semibold mt-3 leading-relaxed ${data.verification.state === 'passed' ? 'text-[#4ecdc4]' : 'text-[#8fa8a5]'}`}>{data.verification.label}</p>{data.verification.at && <p className="text-[#8fa8a5] text-[10px] mt-1">{relative(data.verification.at)}</p>}</> : <p className="text-[#8fa8a5] text-xs mt-3">Loading verification…</p>}
      </article>
    </div>

    {data && <div className="mt-4 pt-4 border-t border-[#1e383b]">
      <div className="flex justify-between items-center gap-3"><h3 className="text-xs font-semibold text-[#d9ece9]">Recent workflow events</h3>{events.length > 3 && <button onClick={() => setShowAll(value => !value)} className="min-h-11 text-[#4ecdc4] text-xs px-2">{showAll ? 'Show fewer' : `Show all ${events.length}`}</button>}</div>
      {visibleEvents.length ? <ol className="space-y-2 mt-2">{visibleEvents.map((event, index) => <li key={`${event.at}-${event.actor}-${index}`} className="grid grid-cols-[76px_minmax(0,1fr)] sm:grid-cols-[110px_130px_minmax(0,1fr)] gap-2 text-[11px]"><span className="text-[#8fa8a5]">{relative(event.at)}</span><span className="text-[#4ecdc4] truncate hidden sm:block">{event.actor}</span><span className="text-[#b7d2cd] break-words">{event.action}</span></li>)}</ol> : <p className="text-[#8fa8a5] text-xs mt-2">No workflow events recorded.</p>}
    </div>}
  </section>;
}
