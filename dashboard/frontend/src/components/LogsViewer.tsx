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
    <div className="h-64 bg-hermes-card border border-hermes-border rounded p-2 overflow-auto font-mono text-xs text-gray-300">
      {loading && <div className="p-2">Loading logs...</div>}
      {error && <div className="p-2 text-red-500">{error}</div>}
      {!loading && logs.length === 0 && <div className="p-2">No logs available.</div>}
      {logs.map((line, i) => (
        <div key={i}>{line}</div>
      ))}
    </div>
  );
}
