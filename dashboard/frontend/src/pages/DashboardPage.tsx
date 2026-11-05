import { useEffect, useState } from 'react';
import { fetchServices, ServiceStatus, restartService, startService, stopService } from '../api';
import { useWebSocketMetrics } from '../hooks/useWebSocketMetrics';
import LogsViewer from '../components/LogsViewer';

const METRICS_WS = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/metrics`;

function MetricCard({ label, value, percent }: { label: string; value: string; percent?: number }) {
  const barColor = percent !== undefined ? percent > 80 ? '#ff4444' : percent > 50 ? '#ffbd65' : '#02a0a0' : '#02a0a0';
  return <div className="bg-[#10262b] border border-[#1e383b] rounded-2xl px-3 py-3 min-w-[140px] sm:min-w-[160px] max-w-full shadow-[0_10px_24px_rgba(0,0,0,0.16)]">
    <div className="text-[#5d7573] text-[10px] uppercase tracking-widest">{label}</div>
    <div className="text-[#d9ece9] text-sm mt-0.5">{value}</div>
    {percent !== undefined && <div className="mt-1 h-1 bg-[#071317] rounded-full overflow-hidden"><div className="h-full rounded-full" style={{ width: `${percent}%`, backgroundColor: barColor }} /></div>}
  </div>;
}

export default function DashboardPage() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [selectedService, setSelectedService] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [primaryModel, setPrimaryModel] = useState<string | null>(null);
  const [modelCheckedAt, setModelCheckedAt] = useState<Date | null>(null);
  const { metrics, connected, updatedAt } = useWebSocketMetrics(METRICS_WS);

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      try {
        const data = await fetchServices();
        if (!cancelled) { setServices(data); setError(null); }
      } catch { if (!cancelled) setError('Service status is temporarily unavailable.'); }
    };
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch('/api/v1/models', { cache: 'no-store' });
        if (!r.ok) throw new Error();
        const data = await r.json();
        if (!cancelled) { setPrimaryModel(data.name); setModelCheckedAt(new Date()); }
      } catch { if (!cancelled) setPrimaryModel(null); }
    };
    load();
    const timer = setInterval(load, 15_000);
    return () => { cancelled = true; clearInterval(timer); };
  }, []);

  const action = async (fn: () => Promise<any>, confirmation?: string) => {
    if (confirmation && !window.confirm(confirmation)) return;
    try {
      await fn();
      const data = await fetchServices();
      setServices(data);
      setError(null);
    } catch { setError('Action could not be completed. No success was recorded.'); }
  };
  const memPercent = metrics?.memory.percent ?? 0;
  const diskPercent = metrics?.disk.percent ?? 0;
  const cpuPercent = metrics?.cpu_percent ?? 0;
  const gpuPercent = metrics?.gpu?.utilization;
  const memStr = metrics ? `${memPercent}% (${Math.round(metrics.memory.used / 1073741824)}G / ${Math.round(metrics.memory.total / 1073741824)}G)` : '—';
  const diskStr = metrics ? `${diskPercent}% (${Math.round(metrics.disk.used / 1073741824)}G / ${Math.round(metrics.disk.total / 1073741824)}G)` : '—';
  const gpuStr = metrics?.gpu ? `${metrics.gpu.utilization}% (${Math.round(metrics.gpu.memory_used)}M / ${Math.round(metrics.gpu.memory_total)}M)` : 'N/A';

  return <div>
    <div className="flex items-start justify-between gap-4 mb-6">
      <div><h1 className="text-lg text-[#d9ece9] tracking-wider uppercase">Dashboard</h1><p className="text-[#5d7573] text-[11px] mt-0.5">System overview &amp; service management</p></div>
      <span className={`text-[10px] px-2 py-1 rounded border ${connected ? 'text-[#02a0a0] border-[#02a0a0]/30' : 'text-[#ff4444] border-[#ff4444]/30'}`}>{connected ? '● LIVE · 3s' : '○ OFFLINE'}</span>
    </div>
    <section className="bg-[#10262b] border border-[#02a0a0]/35 rounded-2xl p-5 mb-5 shadow-[0_14px_36px_rgba(0,0,0,0.18)]">
      <div className="text-[#5d7573] text-[10px] uppercase tracking-wider">Configured primary model</div>
      <div className="text-[#4ecdc4] font-bold mt-1 break-all">{primaryModel ?? 'Configuration unavailable'}</div>
      <div className="text-[#5d7573] text-[10px] mt-1">{modelCheckedAt ? `Live config checked ${modelCheckedAt.toLocaleTimeString()}` : 'Checking configuration…'}</div>
    </section>
    {error && <div role="alert" className="border border-[#ffbd65]/40 bg-[#10262b] p-3 text-xs text-[#ffbd65] mb-4">{error}</div>}
    <div className="flex flex-wrap gap-2 mb-6">
      <MetricCard label="CPU" value={metrics ? `${cpuPercent.toFixed(1)}%` : '—'} percent={metrics ? cpuPercent : undefined} />
      <MetricCard label="Memory" value={memStr} percent={metrics ? memPercent : undefined} />
      <MetricCard label="Disk" value={diskStr} percent={metrics ? diskPercent : undefined} />
      <MetricCard label="GPU" value={gpuStr} percent={gpuPercent} />
    </div>
    {updatedAt && <p className="text-[#5d7573] text-[10px] -mt-3 mb-5">Metrics last updated {updatedAt.toLocaleTimeString()}</p>}
    <h2 className="text-[#8fa8a5] text-xs uppercase tracking-widest mb-3">Services ({services.length})</h2>
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
      {services.map(service => <article key={service.name} className="bg-[#10262b] border border-[#1e383b] rounded-2xl p-4">
        <button className="w-full text-left" onClick={() => setSelectedService(service.name)}><span className="text-[#d9ece9] text-sm font-bold">{service.name}</span><span className="block text-[#8fa8a5] text-xs mt-2">{service.state}</span></button>
        {service.port && <div className="text-[#5d7573] text-[11px] mt-2">Port: {service.port}</div>}
        {service.uptime && <div className="text-[#5d7573] text-[11px] mt-1">Started: {new Date(service.uptime).toLocaleString()}</div>}
        {service.kind !== 'docker' && <div className="flex gap-2 mt-3">
          <button className="px-3 py-1 text-[11px] bg-[#02a0a0] text-[#071317] rounded disabled:opacity-30" onClick={() => action(() => startService(service.name))} disabled={!['inactive', 'stopped', 'failed'].includes(service.state)}>START</button>
          <button className="px-3 py-1 text-[11px] bg-[#ff4444] text-white rounded disabled:opacity-30" onClick={() => action(() => stopService(service.name), `Stop ${service.name}? This may interrupt its work.`)} disabled={!['active', 'running', 'activating'].includes(service.state)}>STOP</button>
          <button className="px-3 py-1 text-[11px] bg-[#ffbd65] text-[#071317] rounded disabled:opacity-30" onClick={() => action(() => restartService(service.name), `Restart ${service.name}?`)} disabled={!['active', 'running', 'failed'].includes(service.state)}>RESTART</button>
        </div>}
      </article>)}
    </div>
    {selectedService && <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setSelectedService(null)}><div className="bg-[#0c1e22] border border-[#1e383b] rounded-lg w-[calc(100vw-1rem)] max-w-4xl max-h-[85vh] flex flex-col overflow-hidden" onClick={e => e.stopPropagation()}><div className="flex justify-between p-4 border-b border-[#1e383b]"><h2 className="text-sm">{selectedService} Logs</h2><button aria-label="Close logs" onClick={() => setSelectedService(null)}>×</button></div><div className="overflow-auto p-2"><LogsViewer service={selectedService} /></div></div></div>}
  </div>;
}
