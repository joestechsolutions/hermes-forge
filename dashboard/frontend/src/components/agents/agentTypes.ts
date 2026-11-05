export type AgentStatus = 'ready' | 'active' | 'completed' | 'needs-attention';

export interface AgentSummary {
  id: string;
  name: string;
  role: string;
  description: string;
  status: AgentStatus;
  current_work: string;
  last_work_at: string | null;
  latest_activity_title: string | null;
  active_now: boolean;
  activity_available: boolean;
  scheduled_jobs: number;
  active_jobs: number;
  failing_jobs: number;
  next_run_at: string | null;
}

export interface Roster {
  agents: AgentSummary[];
  count: number;
  generated_at: string;
}

export interface AgentSession {
  title: string;
  activity: string | null;
  last_activity_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  message_count: number;
  tool_call_count: number;
  model: string | null;
  active: boolean;
}

export interface AgentJob {
  id: string;
  name: string;
  skill: string | null;
  model: string | null;
  enabled: boolean;
  state: string | null;
  cadence: string;
  last_status: string | null;
  last_run_at: string | null;
  next_run_at: string | null;
  failure_streak: number;
  paused_reason: string | null;
  latest_output: { file: string; mtime: string; body: string } | null;
}

export interface AgentDetailData {
  agent: AgentSummary;
  active_now: boolean;
  current_title: string | null;
  activity_available: boolean;
  sessions: AgentSession[];
  jobs: AgentJob[];
  generated_at: string;
}

export function relative(iso: string | null, empty = 'Not recorded'): string {
  if (!iso) return empty;
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return empty;
  const delta = then - Date.now();
  const minutes = Math.floor(Math.abs(delta) / 60000);
  if (minutes < 1) return delta >= 0 ? 'in <1m' : 'just now';
  const value = minutes < 60 ? `${minutes}m` : minutes < 1440 ? `${Math.round(minutes / 60)}h` : `${Math.round(minutes / 1440)}d`;
  return delta >= 0 ? `in ${value}` : `${value} ago`;
}

export function clock(iso: string | null): string {
  if (!iso) return '—';
  const date = new Date(iso);
  return Number.isFinite(date.getTime()) ? date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit' }) : '—';
}

export function statusLabel(agent: AgentSummary): string {
  if (agent.status === 'needs-attention') return 'Needs attention';
  if (agent.active_now) return 'Working now';
  if (agent.status === 'completed') return 'Latest result';
  return 'Ready';
}

export function statusClass(agent: AgentSummary): string {
  if (agent.status === 'needs-attention') return 'text-[#ffbd65] border-[#ffbd65]/50 bg-[#ffbd65]/5';
  if (agent.active_now) return 'text-[#4ecdc4] border-[#4ecdc4]/50 bg-[#4ecdc4]/5';
  return 'text-[#8fa8a5] border-[#1e383b] bg-[#10262b]';
}
