import { SystemMetrics } from '../api';

interface Props {
  metrics: SystemMetrics | null;
  connected: boolean;
}

export default function MetricsBar({ metrics, connected }: Props) {
  if (!metrics) return <div className="p-4">Loading metrics...</div>;
  const memPercent = Math.round((metrics.memory.used / metrics.memory.total) * 100);
  const diskPercent = Math.round((metrics.disk.used / metrics.disk.total) * 100);
  const gpuUtil = metrics.gpu ? `${metrics.gpu.utilization}%` : 'N/A';
  const gpuMem = metrics.gpu ? `${Math.round(metrics.gpu.memory_used/1024/1024)}MB / ${Math.round(metrics.gpu.memory_total/1024/1024)}MB` : 'N/A';
  return (
    <div className="p-4 border-b border-hermes-border bg-hermes-bg">
      <div className="flex items-center gap-4 mb-2">
        <span className="text-sm">CPU: <strong>{metrics.cpu_percent.toFixed(1)}%</strong></span>
        <span className="text-sm">Mem: <strong>{memPercent}%</strong> ({Math.round(metrics.memory.used/1024/1024/1024)}GB / {Math.round(metrics.memory.total/1024/1024/1024)}GB)</span>
        <span className="text-sm">Disk: <strong>{diskPercent}%</strong> ({Math.round(metrics.disk.used/1024/1024/1024)}GB / {Math.round(metrics.disk.total/1024/1024/1024)}GB)</span>
        <span className="text-sm">GPU: <strong>{gpuUtil}</strong> {gpuMem}</span>
        <span className={`ml-auto px-2 py-1 rounded text-xs ${connected ? 'bg-green-600' : 'bg-red-600'}`}>
          {connected ? 'Live' : 'Offline'}
        </span>
      </div>
    </div>
  );
}
