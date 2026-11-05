import { useEffect, useState } from 'react';
import { fetchLogs } from '../api';

interface Props {
  service: string;
}

export default function LogsViewer({ service }: Props) {
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadLogs = async (serviceName: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchLogs(serviceName, 200);
      setLogs(data.logs);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (service) {
      loadLogs(service);
      const interval = setInterval(() => loadLogs(service), 5000);
      return () => clearInterval(interval);
    }
  }, [service]);

  return (
    <div className="bg-[#071317] border border-[#1e383b] rounded p-2 overflow-auto font-mono text-[12px] text-[#8fa8a5]">
      {loading && <div className="p-2 text-[#5d7573]">Loading logs...</div>}
      {error && <div className="p-2 text-[#ff4444]">{error}</div>}
      {!loading && logs.length === 0 && <div className="p-2 text-[#5d7573]">No logs available.</div>}
      {logs.map((line, i) => (
        <div key={i} className="leading-relaxed hover:bg-[#10262b]/50">{line}</div>
      ))}
    </div>
  );
}