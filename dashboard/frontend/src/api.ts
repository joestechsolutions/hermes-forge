// API client for Hermes Dashboard backend
const API_BASE = '/api/v1';

export interface ServiceStatus {
  name: string;
  state: string;
  port?: number;
  uptime?: string;
  last_log?: string;
}

export interface SystemMetrics {
  cpu_percent: number;
  memory: { total: number; available: number; used: number; free: number; percent: number };
  disk: { total: number; used: number; free: number; percent: number };
  gpu?: { utilization: number; memory_used: number; memory_total: number };
  timestamp: string;
}

export async function fetchServices(): Promise<ServiceStatus[]> {
  const resp = await fetch(`${API_BASE}/services`);
  if (!resp.ok) throw new Error('Failed to fetch services');
  return resp.json();
}

export async function restartService(name: string) {
  const resp = await fetch(`${API_BASE}/services/${name}/restart`, { method: 'POST' });
  if (!resp.ok) throw new Error('Failed to restart service');
  return resp.json();
}

export async function startService(name: string) {
  const resp = await fetch(`${API_BASE}/services/${name}/start`, { method: 'POST' });
  if (!resp.ok) throw new Error('Failed to start service');
  return resp.json();
}

export async function stopService(name: string) {
  const resp = await fetch(`${API_BASE}/services/${name}/stop`, { method: 'POST' });
  if (!resp.ok) throw new Error('Failed to stop service');
  return resp.json();
}

export async function fetchLogs(service: string, lines: number = 100): Promise<{ logs: string[] }> {
  const resp = await fetch(`${API_BASE}/logs/${service}?lines=${lines}`);
  if (!resp.ok) throw new Error('Failed to fetch logs');
  return resp.json();
}

export async function fetchSnapshots() {
  const resp = await fetch(`${API_BASE}/snapshots`);
  if (!resp.ok) throw new Error('Failed to fetch snapshots');
  return resp.json();
}

export async function createSnapshot(name?: string) {
  const resp = await fetch(`${API_BASE}/snapshots`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  });
  if (!resp.ok) throw new Error('Failed to create snapshot');
  return resp.json();
}

export async function restoreSnapshot(snapshotName: string) {
  const resp = await fetch(`${API_BASE}/snapshots/${snapshotName}/restore`, { method: 'POST' });
  if (!resp.ok) throw new Error('Failed to restore snapshot');
  return resp.json();
}

export async function fetchSecurityStatus() {
  const resp = await fetch(`${API_BASE}/security/status`);
  if (!resp.ok) throw new Error('Failed to fetch security status');
  return resp.json();
}

export async function validateConfigs() {
  const resp = await fetch(`${API_BASE}/config/validate`);
  if (!resp.ok) throw new Error('Failed to validate configs');
  return resp.json();
}
