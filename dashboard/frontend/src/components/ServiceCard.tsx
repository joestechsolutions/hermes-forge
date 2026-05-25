import { ServiceStatus } from '../api';

interface Props {
  service: ServiceStatus;
  onStart: () => void;
  onStop: () => void;
  onRestart: () => void;
  onSelect: () => void;
  selected: boolean;
}

export default function ServiceCard({ service, onStart, onStop, onRestart, onSelect, selected }: Props) {
  const stateColors: Record<string, string> = {
    running: 'bg-green-600',
    failed: 'bg-red-600',
    stopped: 'bg-gray-600',
    unknown: 'bg-yellow-600'
  };
  const color = stateColors[service.state] || stateColors.unknown;
  return (
    <div
      className={`p-4 rounded-lg border ${selected ? 'border-hermes-primary' : 'border-hermes-border'} bg-hermes-card cursor-pointer hover:border-hermes-accent transition-colors`}
      onClick={onSelect}
    >
      <div className="flex justify-between items-center mb-2">
        <h3 className="font-bold text-lg">{service.name}</h3>
        <span className={`px-2 py-1 text-xs rounded-full text-white ${color}`}>{service.state}</span>
      </div>
      {service.port && <p className="text-sm text-gray-400">Port: {service.port}</p>}
      {service.uptime && <p className="text-sm text-gray-400">Uptime: {service.uptime}</p>}
      {service.last_log && (
        <p className="text-xs text-gray-500 mt-2 truncate" title={service.last_log}>{service.last_log}</p>
      )}
      <div className="mt-3 flex gap-2">
        <button
          className="px-3 py-1 bg-hermes-primary text-black rounded text-sm hover:opacity-90"
          onClick={(e) => { e.stopPropagation(); onStart(); }}
          disabled={service.state === 'running'}
        >
          Start
        </button>
        <button
          className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:opacity-90"
          onClick={(e) => { e.stopPropagation(); onStop(); }}
          disabled={service.state === 'stopped' || service.state === 'failed'}
        >
          Stop
        </button>
        <button
          className="px-3 py-1 bg-yellow-600 text-white rounded text-sm hover:opacity-90"
          onClick={(e) => { e.stopPropagation(); onRestart(); }}
        >
          Restart
        </button>
      </div>
    </div>
  );
}
