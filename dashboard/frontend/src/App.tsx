import { useEffect, useState } from 'react';
import { fetchServices, ServiceStatus, restartService, startService, stopService } from './api';
import { useWebSocketMetrics } from './hooks/useWebSocketMetrics';
import ServiceCard from './components/ServiceCard';
import MetricsBar from './components/MetricsBar';
import LogsViewer from './components/LogsViewer';

const METRICS_WS = `ws://${window.location.host}/ws/metrics`;

export default function App() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [_loading, setLoading] = useState(true);
  const [_error, setError] = useState<string | null>(null);
  const { metrics, connected } = useWebSocketMetrics(METRICS_WS);

  const refreshServices = async () => {
    try {
      const data = await fetchServices();
      setServices(data);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshServices();
    const interval = setInterval(refreshServices, 5000);
    return () => clearInterval(interval);
  }, []);

  const action = async (_name: string, fn: () => Promise<any>) => {
    await fn();
    setTimeout(refreshServices, 1000);
  };

  return (
    <div className="min-h-screen bg-hermes-bg p-4">
      <h1 className="text-2xl font-bold mb-4">Hermes Infrastructure Dashboard</h1>
      <MetricsBar metrics={metrics} connected={connected} />
      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {services.map(service => (
          <ServiceCard
            key={service.name}
            service={service}
            selected={selected === service.name}
            onStart={() => action(service.name, () => startService(service.name))}
            onStop={() => action(service.name, () => stopService(service.name))}
            onRestart={() => action(service.name, () => restartService(service.name))}
            onSelect={() => setSelected(service.name === selected ? null : service.name)}
          />
        ))}
      </div>
      {selected && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => setSelected(null)}>
          <div className="bg-hermes-card border border-hermes-border rounded-lg p-4 w-full max-w-4xl max-h-[90vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-2">
              <h2 className="text-xl font-bold">{selected} Logs</h2>
              <button className="px-3 py-1 bg-hermes-primary text-black rounded" onClick={() => setSelected(null)}>Close</button>
            </div>
            <LogsViewer service={selected} />
          </div>
        </div>
      )}
    </div>
  );
}
