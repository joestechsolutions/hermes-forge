import { useEffect, useState } from 'react';

interface ModelInfo {
  name: string;
  status: string;
  provider?: string;
  description?: string;
  role?: string;
}

interface ModelData {
  name: string | null;
  provider: string | null;
  source: string;
  models: ModelInfo[];
  enabled_scheduled_jobs: number | null;
}

export default function ModelsPage() {
  const [data, setData] = useState<ModelData | null>(null);
  const [error, setError] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchModels = async () => {
      try {
        const resp = await fetch('/api/v1/models', { cache: 'no-store' });
        if (!resp.ok) throw new Error('unavailable');
        const next = await resp.json();
        if (!cancelled) {
          setData(next);
          setError(false);
          setUpdatedAt(new Date());
        }
      } catch {
        if (!cancelled) setError(true);
      }
    };
    fetchModels();
    const timer = setInterval(fetchModels, 15_000);
    return () => { cancelled = true; clearInterval(timer); };
  }, []);

  return (
    <div>
      <div className="mb-6 flex justify-between items-start gap-4">
        <div>
          <h1 className="text-lg text-[#d9ece9] tracking-wider uppercase">Models</h1>
          <p className="text-[#5d7573] text-[11px] mt-1">Live configuration, refreshed every 15 seconds</p>
        </div>
        <span className={`text-[10px] ${error ? 'text-[#ffbd65]' : 'text-[#02a0a0]'}`}>
          {error ? 'UPDATE UNAVAILABLE' : updatedAt ? `UPDATED ${updatedAt.toLocaleTimeString()}` : 'CHECKING…'}
        </span>
      </div>
      <section className="bg-[#10262b] border border-[#02a0a0]/50 rounded-2xl p-5 mb-5 shadow-[0_14px_36px_rgba(0,0,0,0.18)]">
        <div className="text-[#5d7573] text-[10px] uppercase tracking-wider">Primary conversation model</div>
        <h2 className="text-[#d9ece9] font-mono font-bold text-xl mt-2 break-words">{data?.name ?? 'Checking live configuration…'}</h2>
        <p className="text-[#4ecdc4] text-xs mt-2">Provider: {data?.provider ?? 'Unavailable'}</p>
        <p className="text-[#8fa8a5] text-xs mt-2">Source: {data?.source ?? 'Unavailable'}</p>
      </section>
      {data?.enabled_scheduled_jobs !== null && data?.enabled_scheduled_jobs !== undefined && (
        <p className="text-[#8fa8a5] text-xs mb-4">{data.enabled_scheduled_jobs} enabled scheduled jobs · model pins shown below</p>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {data?.models.map(model => (
          <article key={`${model.name}-${model.provider}`} className="bg-[#10262b] border border-[#1e383b] rounded-2xl p-4">
            <div className="flex justify-between items-start gap-2">
              <h3 className="text-[#d9ece9] text-sm font-bold break-all">{model.name}</h3>
              <span className="text-[10px] text-[#02a0a0] border border-[#02a0a0]/20 px-2 py-0.5 shrink-0">{model.status}</span>
            </div>
            <p className="text-[#8fa8a5] text-xs mt-2">{model.role}</p>
            <p className="text-[#5d7573] text-[11px] mt-1">{model.provider}</p>
            <p className="text-[#5d7573] text-[11px] mt-2">{model.description}</p>
          </article>
        ))}
      </div>
    </div>
  );
}
