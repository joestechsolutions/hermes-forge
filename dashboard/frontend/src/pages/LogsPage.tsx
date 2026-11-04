import { useEffect, useState } from 'react';
import LogsViewer from '../components/LogsViewer';
import { ServiceStatus, fetchServices } from '../api';

export default function LogsPage() {
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [selectedService, setSelectedService] = useState<string>('');

  useEffect(() => {
    fetchServices().then((data) => {
      setServices(data);
      setSelectedService(current => current || (data.length > 0 ? data[0].name : ''));
    }).catch(() => {});
    const timer = setInterval(() => fetchServices().then(setServices).catch(() => {}), 15_000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-lg text-[#d9ece9] tracking-wider uppercase">Logs</h1>
        <p className="text-[#5d7573] text-[11px] mt-0.5">
          Real-time service log output
        </p>
      </div>

      {/* Service selector */}
      <div className="flex items-center gap-3 mb-4">
        <label className="text-[#8fa8a5] text-[11px] uppercase tracking-wider">Service:</label>
        <select
          className="bg-[#10262b] border border-[#1e383b] rounded px-3 py-1.5 text-[#d9ece9] text-sm focus:outline-none focus:border-[#02a0a0]"
          value={selectedService}
          onChange={(e) => setSelectedService(e.target.value)}
        >
          {services.length === 0 && <option value="">— No services —</option>}
          {services.map((s) => (
            <option key={s.name} value={s.name}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      {/* Log output area */}
      {selectedService ? (
        <div className="bg-[#0c1e22] border border-[#1e383b] rounded-2xl overflow-hidden">
          <div className="px-3 py-2 border-b border-[#1e383b] flex items-center justify-between">
            <span className="text-[#8fa8a5] text-[10px] uppercase tracking-wider">
              {selectedService} log stream
            </span>
            <span className="text-[#02a0a0] text-[10px]">REFRESHES EVERY 5s</span>
          </div>
          <div className="h-[60vh] overflow-auto p-2">
            <LogsViewer service={selectedService} />
          </div>
        </div>
      ) : (
        <div className="bg-[#10262b] border border-[#1e383b] rounded-lg p-6 text-center">
          <div className="text-[#5d7573] text-sm">No services available</div>
        </div>
      )}
    </div>
  );
}