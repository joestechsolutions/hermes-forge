import { useEffect, useState } from 'react';
import { SystemMetrics } from '../api';

export function useWebSocketMetrics(url: string) {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(url);
    ws.onopen = () => setConnected(true);
    ws.onmessage = (event) => {
      try {
        setMetrics(JSON.parse(event.data));
      } catch (e) {
        console.error('Failed to parse metrics', e);
      }
    };
    ws.onclose = () => setConnected(false);
    return () => ws.close();
  }, [url]);

  return { metrics, connected };
}
