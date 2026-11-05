import { useEffect, useState } from 'react';
import AgentRoster from '../components/AgentRoster';

const API_BASE = '/api/v1';

async function fetchJson(path: string) {
  const response = await fetch(path, { cache: 'no-store' });
  if (!response.ok) throw new Error(`Update failed (${response.status})`);
  return response.json();
}

interface JobSummary {
  total_jobs: number;
  live: number;
  failing: number;
  failing_names: string[];
  next_up: { name: string; next_run_at: string }[];
  generated_at: string;
}

interface Category {
  category: string;
  total: number;
  live: number;
  failing: number;
}

interface Job {
  id: string;
  name: string;
  enabled: boolean;
  category: string;
  cadence: string;
  cron_expr: string | null;
  last_status: string | null;
  last_run_at: string | null;
  next_run_at: string | null;
  failure_streak: number;
  paused_reason: string | null;
  latest?: { file: string; mtime: string; size: number; body: string } | null;
}

interface Report {
  job: string;
  job_id: string;
  file: string;
  mtime: string;
  age_min: number;
  body: string;
}

function fmtWhen(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  const now = new Date();
  const diffMin = (now.getTime() - d.getTime()) / 60000;
  const local = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  if (diffMin < 0) {
    const inMin = -diffMin;
    if (inMin < 90) return `in ${Math.round(inMin)}m`;
    if (inMin < 24 * 60) return `today ${local}`;
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + local;
  }
  if (diffMin < 90) return `${Math.round(diffMin)}m ago`;
  if (diffMin < 24 * 60) return `${Math.round(diffMin / 60)}h ago`;
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function CadenceChip({ text }: { text: string }) {
  const color =
    /monthly/.test(text) ? 'text-[#ffbd65] border-[#ffbd65]'
    : /weekly|weekdays/.test(text) ? 'text-[#4ecdc4] border-[#4ecdc4]'
    : /daily|interval|minute/.test(text) ? 'text-[#02a0a0] border-[#02a0a0]'
    : 'text-[#8fa8a5] border-[#5d7573]';
  return <span className={`px-1 sm:px-1.5 py-0.5 border text-[9px] sm:text-[10px] uppercase tracking-wider ${color}`}>{text}</span>;
}

export default function CommandCenterPage() {
  const [summary, setSummary] = useState<JobSummary | null>(null);
  const [cats, setCats] = useState<Category[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [activeCat, setActiveCat] = useState<string | null>(null);
  const [openReport, setOpenReport] = useState<Report | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = async (cat: string | null) => {
    try {
      const [s, c, j, r] = await Promise.all([
        fetchJson(`${API_BASE}/command-center/summary`),
        fetchJson(`${API_BASE}/command-center/categories`),
        fetchJson(`${API_BASE}/command-center/jobs${cat ? `?category=${encodeURIComponent(cat)}` : ''}${cat ? '&' : '?'}outputs=true`),
        fetchJson(`${API_BASE}/command-center/reports?limit=12`),
      ]);
      setSummary(s); setCats(c); setJobs(j.jobs ?? []); setReports(r ?? []); setErr(null);
    } catch (e) {
      setErr('Could not refresh the Command Center. Existing values may be stale.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(activeCat); }, [activeCat]);

  const autoRef = () => { const t = setInterval(() => load(activeCat), 60_000); return () => clearInterval(t); };
  useEffect(autoRef, [activeCat]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="max-w-5xl overflow-x-hidden">
      <div className="flex items-baseline justify-between mb-1 gap-2">
        <h1 className="text-xl sm:text-2xl font-bold text-[#02a0a0] tracking-wider">COMMAND CENTER</h1>
        <span className="text-xs text-[#5d7573]">
          {summary ? `refreshed ${fmtWhen(summary.generated_at)} · ${summary.live}/${summary.total_jobs} scheduled jobs live` : ''}
        </span>
      </div>
      <p className="text-sm text-[#8fa8a5] mb-6">Every agent, scheduled job, and report — in one place.</p>

      <AgentRoster />

      {loading && <div className="text-[#8fa8a5]">loading…</div>}
      {err && <div className="text-[#ff5555]">error: {err}</div>}

      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
          <div className="border border-[#1e383b] bg-[#0c1e22] rounded-2xl p-4">
            <div className="text-[10px] uppercase tracking-[0.2em] text-[#5d7573] mb-2">Scheduled jobs</div>
            <div className="text-3xl font-bold text-[#02a0a0]">{summary.live}<span className="text-lg text-[#8fa8a5]">/{summary.total_jobs}</span></div>
            <div className="text-xs text-[#8fa8a5] mt-1">live jobs · {summary.failing} failing</div>
            {summary.failing_names.length > 0 && (
              <div className="text-[11px] text-[#ff6666] mt-2">{summary.failing_names.join(', ')}</div>
            )}
          </div>
          <div className="border border-[#1e383b] bg-[#0c1e22] rounded-2xl p-4 md:col-span-2">
            <div className="text-[10px] uppercase tracking-[0.2em] text-[#5d7573] mb-2">Next up</div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-sm">
              {summary.next_up.map(j => (
                <div key={j.name} className="flex justify-between gap-3">
                  <span className="text-[#d9ece9] truncate">{j.name}</span>
                  <span className="text-[#4ecdc4] whitespace-nowrap">{fmtWhen(j.next_run_at)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {cats.length > 0 && (
        <div className="flex flex-wrap gap-1.5 sm:gap-2 mb-6">
          <button onClick={() => setActiveCat(null)}
            className={`px-2 sm:px-3 py-1.5 text-[11px] sm:text-xs uppercase tracking-wider border ${!activeCat ? 'border-[#02a0a0] text-[#02a0a0] bg-[#10262b]' : 'border-[#1e383b] text-[#8fa8a5] hover:text-[#d9ece9]'}`}>
            All ({cats.reduce((a, c) => a + c.total, 0)})
          </button>
          {cats.map(c => (
            <button key={c.category} onClick={() => setActiveCat(c.category)}
              className={`px-2 sm:px-3 py-1.5 text-[11px] sm:text-xs uppercase tracking-wider border ${activeCat === c.category ? 'border-[#02a0a0] text-[#02a0a0] bg-[#10262b]' : c.failing > 0 ? 'border-[#ff6666] text-[#ff8888]' : 'border-[#1e383b] text-[#8fa8a5] hover:text-[#d9ece9]'}`}>
              {c.category} ({c.live}/{c.total}{c.failing > 0 ? ` · ${c.failing}!` : ''})
            </button>
          ))}
        </div>
      )}

      <div className="border border-[#1e383b] bg-[#0c1e22] divide-y divide-[#1e383b]">
        {jobs.map(j => (
          <div key={j.id}>
            <button onClick={() => setExpanded(e => ({ ...e, [j.id]: !e[j.id] }))} className="w-full text-left px-3 sm:px-4 py-3 hover:bg-[#10262b] transition-colors">
              <div className="flex items-center gap-2 sm:gap-3">
                <span className={`w-2 h-2 rounded-full shrink-0 ${!j.enabled ? 'bg-[#5d7573]' : j.failure_streak > 0 || (j.last_status && !['ok', 'success'].includes(j.last_status)) ? 'bg-[#ff4444]' : 'bg-[#02a0a0]'}`} />
                <span className="text-sm text-[#d9ece9] flex-1 min-w-0 truncate">{j.name}</span>
                <span className="shrink-0"><CadenceChip text={j.cadence} /></span>
                <span className="text-[11px] sm:text-xs text-[#5d7573] sm:w-20 text-right shrink-0">{fmtWhen(j.last_run_at)}</span>
                <span className="text-[11px] sm:text-xs text-[#4ecdc4] sm:w-24 text-right shrink-0">→ {fmtWhen(j.next_run_at)}</span>
              </div>
              {!j.enabled && j.paused_reason && (
                <div className="text-[11px] text-[#5d7573] mt-1 pl-5">paused — {j.paused_reason}</div>
              )}
            </button>
            {expanded[j.id] && !j.latest?.body && (
              <p className="px-5 pb-4 text-xs text-[#5d7573]">No saved report for this job.</p>
            )}
            {expanded[j.id] && j.latest?.body && (
              <div className="px-5 pb-4">
                <pre className="text-xs text-[#b7d2cd] whitespace-pre-wrap bg-[#091a1d] border border-[#1e383b] p-3 max-h-80 overflow-y-auto">{j.latest.body}</pre>
                <div className="text-[10px] text-[#5d7573] mt-1">{j.latest.file} · {fmtWhen(j.latest.mtime)}</div>
              </div>
            )}
          </div>
        ))}
      </div>

      <h2 className="text-lg font-bold text-[#8fa8a5] tracking-wider mt-8 mb-3">LATEST BRIEFINGS</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {reports.map(r => (
          <button key={r.file} onClick={() => setOpenReport(r)} className="text-left border border-[#1e383b] bg-[#0c1e22] p-3 sm:p-4 hover:border-[#02a0a0] transition-colors">
            <div className="flex justify-between items-baseline gap-2 mb-1">
              <span className="text-sm text-[#d9ece9] truncate">{r.job}</span>
              <span className="text-[10px] text-[#5d7573] whitespace-nowrap">{fmtWhen(r.mtime)}</span>
            </div>
            <div className="text-xs text-[#8fa8a5] line-clamp-3 whitespace-pre-wrap">{r.body.slice(0, 220)}…</div>
          </button>
        ))}
      </div>

      {openReport && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-2 sm:p-6" onClick={() => setOpenReport(null)}>
          <div className="bg-[#0c1e22] border border-[#1e383b] max-w-2xl w-full max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center px-3 sm:px-4 py-3 border-b border-[#1e383b]">
              <span className="text-sm text-[#02a0a0] truncate pr-2">{openReport.job}</span>
              <button onClick={() => setOpenReport(null)} className="text-[#8fa8a5] hover:text-white text-2xl leading-none px-2 shrink-0">×</button>
            </div>
            <pre className="text-xs text-[#b7d2cd] whitespace-pre-wrap px-3 sm:p-4 py-3 overflow-y-auto break-words">{openReport.body}</pre>
          </div>
        </div>
      )}
    </div>
  );
}