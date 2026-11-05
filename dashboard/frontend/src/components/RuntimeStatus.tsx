import { useEffect, useState } from 'react';

export default function RuntimeStatus() {
  const [status, setStatus] = useState<'checking' | 'running' | 'unavailable'>('checking');
  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      try {
        const response = await fetch('/api/v1/agents/status', { cache: 'no-store' });
        const data = await response.json();
        const gateway = Array.isArray(data) ? data.find(x => x.agent === 'hermes') : null;
        if (!cancelled) setStatus(response.ok && gateway?.status === 'active' ? 'running' : 'unavailable');
      } catch { if (!cancelled) setStatus('unavailable'); }
    };
    check();
    const timer = setInterval(check, 15_000);
    return () => { cancelled = true; clearInterval(timer); };
  }, []);
  return <div className="flex items-center gap-2 mb-1">
    <span className={`w-2 h-2 rounded-full ${status === 'running' ? 'bg-[#02a0a0]' : status === 'unavailable' ? 'bg-[#ffbd65]' : 'bg-[#5d7573]'}`} />
    <span className="text-[#8fa8a5] text-xs">{status === 'running' ? 'JTS Ops · Gateway running' : status === 'unavailable' ? 'JTS Ops · Status unavailable' : 'JTS Ops · Checking…'}</span>
  </div>;
}
